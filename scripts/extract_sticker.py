"""Extract a specifically selected original Windows WeChat sticker.
Only in-memory database snapshots are used; credentials and URLs are not logged.
"""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import gc
import hashlib
import io
import json
import re
import sqlite3
import struct
import sys
import time
import urllib.request
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

SCRIPTS=Path(__file__).resolve().parent

def allowed_resource_url(url):
    parsed=urlparse(url)
    host=(parsed.hostname or '').lower()
    return parsed.scheme in ('http','https') and any(host==base or host.endswith('.'+base) for base in ('qpic.cn','qq.com'))

def emoji_attributes(content):
    if isinstance(content,bytes):
        if content.startswith(b'\x28\xb5\x2f\xfd'):
            import zstandard
            content=zstandard.ZstdDecompressor().decompress(content,max_output_size=4*1024*1024)
        content=content.decode('utf-8')
    root=ET.fromstring(content[content.index('<'):])
    emoji=root if root.tag=='emoji' else root.find('.//emoji')
    if emoji is None:
        raise ValueError('Selected message has no emoji attachment')
    return dict(emoji.attrib)

def sticker_rows(con,table,*,local_id=None,after=None,before=None,limit=32):
    if re.fullmatch(r'Msg_[0-9a-f]{32}',table) is None:
        raise ValueError('Invalid selected conversation table')
    where=['local_type=47'];parameters=[]
    for column,value,operator in [('local_id',local_id,'='),('create_time',after,'>='),('create_time',before,'<=')]:
        if value is not None:
            where.append(column+operator+'?');parameters.append(value)
    parameters.append(limit)
    return con.execute('SELECT local_id,create_time,message_content FROM "'+table+'" WHERE '+' AND '.join(where)+' ORDER BY create_time DESC LIMIT ?',parameters).fetchall()

def validate_original(data,expected_md5):
    from PIL import Image
    if not re.fullmatch('[0-9a-fA-F]{32}',expected_md5 or ''):
        raise ValueError('Expected attachment MD5 is missing or invalid')
    if hashlib.md5(data).hexdigest()!=expected_md5.lower():
        raise ValueError('Original resource MD5 mismatch')
    with Image.open(io.BytesIO(data)) as image:
        count=getattr(image,'n_frames',1)
        if count<2:
            raise ValueError('Resource is not animated; do not substitute a thumbnail')
        duration=0;loop=image.info.get('loop')
        for frame in range(count):
            image.seek(frame);image.load();duration+=image.info.get('duration',0)
        fmt=image.format.lower()
        if fmt not in ('gif','webp','png'):
            raise ValueError('Unsupported original animated image format')
        return dict(format=fmt,size=list(image.size),frames=count,duration_ms=duration,
                    loop=loop,bytes=len(data),md5=expected_md5.lower(),
                    sha256=hashlib.sha256(data).hexdigest(),attachment_md5_matches=True)

def open_memory_db(account_dir,relative):
    # Imports are lazy so offline validation never touches a running process.
    sys.path.insert(0,str(SCRIPTS/'vendor'))
    from wechat_meme_export import memory
    from wechat_meme_export.decrypt import PAGE_SIZE,detect_page_reserve,decrypt_page
    memory.EXACT_SALT_ADAPTERS[(4,1,15,53)]='4.1.15.53-target-salt-verified'
    storage=(account_dir/'db_storage').resolve()
    source=(storage/relative).resolve()
    if not source.is_relative_to(storage):
        raise ValueError('Database path must stay inside the chosen account')
    encrypted=source.read_bytes()
    if len(encrypted)<PAGE_SIZE or len(encrypted)%PAGE_SIZE:
        raise ValueError('Selected database has invalid page boundaries')
    first=encrypted[:PAGE_SIZE];reader=memory.ProcessMemoryReader();key=None
    deadline=time.monotonic()+25
    for pid in memory.get_weixin_pids():
        if reader.get_weixin_module(pid) is None:continue
        handle=reader.open_process(memory.PROCESS_QUERY_INFORMATION|memory.PROCESS_VM_READ,False,pid)
        if not handle:continue
        try:
            scan=memory.ProcessScan()
            reader.scan_wcdb_config_key(pid,handle,first,deadline,set(),scan)
            if scan.keys:
                key=bytes.fromhex(next(iter(scan.keys)))[:32];break
        finally:reader.close_handle(handle)
        if time.monotonic()>=deadline:break
    if key is None:
        raise RuntimeError('Selected DB key unavailable: check logged-in account, read permission and supported WeChat version; no broad memory fallback was run')
    reserve=detect_page_reserve(first,key)
    if reserve is None:raise ValueError('Selected database failed first-page authentication')
    plain=bytearray()
    for index in range(len(encrypted)//PAGE_SIZE):
        page=encrypted[index*PAGE_SIZE:(index+1)*PAGE_SIZE]
        plain.extend(page if not any(page) else decrypt_page(page,index,key,reserve))
    wal_path=source.with_name(source.name+'-wal')
    if wal_path.exists():
        wal=wal_path.read_bytes()
        if len(wal)>=32:
            magic,page_size=struct.unpack_from('>I',wal)[0],struct.unpack_from('>I',wal,8)[0]
            if magic not in (0x377f0682,0x377f0683) or page_size!=PAGE_SIZE:
                raise ValueError('Unsupported WAL format')
            frames=[];committed=0;pages=0
            for offset in range(32,len(wal)-PAGE_SIZE-23,PAGE_SIZE+24):
                page_no,commit_size=struct.unpack_from('>II',wal,offset)
                if wal[offset+8:offset+16]!=wal[16:24] or page_no<1:break
                frames.append((page_no,wal[offset+24:offset+24+PAGE_SIZE]))
                if commit_size:committed=len(frames);pages=commit_size
            if pages:
                if pages*PAGE_SIZE>1024*1024*1024:raise ValueError('WAL snapshot exceeds 1 GiB safety limit')
                if len(plain)<pages*PAGE_SIZE:plain.extend(b'\0'*(pages*PAGE_SIZE-len(plain)))
                for page_no,page in frames[:committed]:
                    if page_no<=pages:plain[(page_no-1)*PAGE_SIZE:page_no*PAGE_SIZE]=decrypt_page(page,page_no-1,key,reserve)
                del plain[pages*PAGE_SIZE:]
    # Memory snapshots must not reference an external WAL. Source files stay untouched.
    plain[18:20]=b'\1\1'
    con=sqlite3.connect(':memory:');con.deserialize(bytes(plain));con.row_factory=sqlite3.Row
    del key,encrypted,plain
    return con

def selected_username(args):
    if args.username:return args.username
    con=open_memory_db(args.account_dir,'contact/contact.db')
    try:
        if args.contains:
            rows=con.execute('SELECT username,remark,nick_name FROM contact WHERE instr(remark,?)>0 OR instr(nick_name,?)>0',(args.chat,args.chat)).fetchall()
        else:
            rows=con.execute('SELECT username,remark,nick_name FROM contact WHERE remark=? OR nick_name=?',(args.chat,args.chat)).fetchall()
        if len(rows)!=1:
            labels=[r['remark'] or r['nick_name'] for r in rows[:10]]
            raise ValueError('Chat selection must be unique; matching labels: '+json.dumps(labels,ensure_ascii=False))
        return rows[0]['username']
    finally:con.close()

def collect_records(args):
    table='Msg_'+hashlib.md5(selected_username(args).encode()).hexdigest()
    if args.message_db:
        if re.fullmatch(r'message_\d+\.db',args.message_db) is None:raise ValueError('Expected message_N.db basename')
        files=[args.account_dir/'db_storage/message'/args.message_db]
    else:
        files=sorted(p for p in (args.account_dir/'db_storage/message').glob('message_*.db') if re.fullmatch(r'message_\d+\.db',p.name))
    records=[]
    for source in files:
        con=open_memory_db(args.account_dir,'message/'+source.name)
        try:
            exists=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()
            if not exists:continue
            for row in sticker_rows(con,table,local_id=args.local_id,after=args.after,before=args.before,limit=args.limit):
                attrs=emoji_attributes(row['message_content'])
                records.append(dict(database=source.name,local_id=row['local_id'],timestamp=row['create_time'],attrs=attrs))
        finally:con.close();gc.collect()
    return records

class StickerRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        if not allowed_resource_url(newurl):raise ValueError('Sticker redirect left the expected resource hosts')
        return super().redirect_request(request,fp,code,msg,headers,newurl)

def original_bytes(attrs):
    sys.path.insert(0,str(SCRIPTS/'vendor'))
    from wechat_meme_export.exporter import aes_decrypt_variants,strip_pkcs7
    expected=attrs.get('md5','')
    errors=[];opener=urllib.request.build_opener(StickerRedirect())
    # Thumbnail URLs are deliberately excluded.
    for field in ('cdnurl','externurl','encrypturl'):
        url=attrs.get(field)
        if not url:continue
        if not allowed_resource_url(url):raise ValueError('Unexpected original resource host')
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
            with opener.open(request,timeout=25) as response:
                data=response.read(32*1024*1024+1)
            if len(data)>32*1024*1024:raise ValueError('Sticker resource exceeds 32 MiB')
            candidates=[data]
            if attrs.get('aeskey'):
                decoded=aes_decrypt_variants(data,attrs['aeskey'])
                if decoded:candidates.extend([decoded[0],strip_pkcs7(decoded[0])])
            for candidate in candidates:
                if hashlib.md5(candidate).hexdigest()==expected.lower():
                    return candidate,validate_original(candidate,expected)
            errors.append(field+':no authenticated animated original')
        except Exception as error:
            # URLs can contain private access tokens; never log their values or exception reprs.
            errors.append(field+':'+type(error).__name__)
    raise RuntimeError('Original sticker retrieval failed ('+'; '.join(errors)+')')

def parse_time(value):
    parsed=datetime.fromisoformat(value)
    if parsed.tzinfo is None:raise argparse.ArgumentTypeError('Include a timezone offset, for example +08:00')
    return int(parsed.timestamp())

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deps-dir',type=Path,action='append',default=[],help='Additional existing site-packages directory; no packages are installed automatically')
    modes=parser.add_subparsers(dest='mode',required=True)
    for mode in ('list','export'):
        sub=modes.add_parser(mode)
        sub.add_argument('--account-dir',type=Path,required=True,help='Chosen wxid_* account directory containing db_storage')
        chat=sub.add_mutually_exclusive_group(required=True)
        chat.add_argument('--chat',help='Exact contact remark or nickname')
        chat.add_argument('--username',help='Known exact WeChat username; avoids contact lookup')
        sub.add_argument('--contains',action='store_true',help='Explicitly allow a unique substring match for --chat')
        sub.add_argument('--message-db',help='Optional known message_N.db partition')
        sub.add_argument('--after',type=parse_time);sub.add_argument('--before',type=parse_time)
        sub.add_argument('--limit',type=int,default=32,help='Maximum sticker records inspected per partition (1..200)')
        if mode=='list':sub.add_argument('--local-id',type=int)
        else:
            target=sub.add_mutually_exclusive_group(required=True)
            target.add_argument('--md5',help='Expected original attachment MD5 from the chosen message')
            target.add_argument('--local-id',type=int,help='Use with --message-db to identify an older message exactly')
            target.add_argument('--latest',action='store_true',help='Only when the user actually requested the latest sticker')
            sub.add_argument('--output-dir',type=Path,required=True)
            sub.add_argument('--name',help='Output filename stem; actual original extension is preserved')
            sub.add_argument('--preview-dir',type=Path,help='Optional separate visual-QA preview location')
    verify=modes.add_parser('verify');verify.add_argument('--file',type=Path,required=True);verify.add_argument('--md5',required=True)
    args=parser.parse_args(argv)
    for directory in args.deps_dir:sys.path.append(str(directory))
    if args.mode=='verify':
        report=validate_original(args.file.read_bytes(),args.md5);report['file']=str(args.file.resolve())
        print(json.dumps(report,ensure_ascii=True));return
    if not 1<=args.limit<=200:parser.error('--limit must be 1..200')
    if args.local_id is not None and not args.message_db:parser.error('--local-id requires --message-db')
    records=collect_records(args)
    if args.mode=='list':
        for record in sorted(records,key=lambda r:r['timestamp'],reverse=True):
            print(json.dumps({k:v for k,v in record.items() if k!='attrs'}|{'md5':record['attrs'].get('md5'),'time_utc':datetime.fromtimestamp(record['timestamp'],timezone.utc).isoformat(),'width':record['attrs'].get('width'),'height':record['attrs'].get('height')},ensure_ascii=True))
        return
    if args.md5:records=[r for r in records if r['attrs'].get('md5','').lower()==args.md5.lower()]
    if not records:raise ValueError('No matching selected sticker; check chat, partition and time range')
    if not args.latest and len({r['attrs'].get('md5') for r in records})>1:raise ValueError('Message selection matched different stickers')
    record=max(records,key=lambda r:(r['timestamp'],r['local_id']))
    data,report=original_bytes(record['attrs'])
    args.output_dir.mkdir(parents=True,exist_ok=True)
    stem=args.name or ('sticker_'+report['md5'])
    if Path(stem).name!=stem or any(ch in stem for ch in '<>:"/\\|?*'):raise ValueError('--name must be a simple filename stem')
    target=args.output_dir/(stem+'.'+report['format'])
    if target.exists():
        if target.read_bytes()!=data:raise FileExistsError('Refusing to overwrite a different output')
    else:
        with target.open('xb') as stream:stream.write(data)
    validate_original(target.read_bytes(),report['md5'])
    report.update(file=str(target.resolve()),message_database=record['database'],message_local_id=record['local_id'],source='original WeChat sticker attachment',visual_match_checked=False)
    if args.preview_dir:
        from PIL import Image
        args.preview_dir.mkdir(parents=True,exist_ok=True)
        preview=args.preview_dir/(stem+'.png')
        with Image.open(target) as image:image.seek(0);image.convert('RGBA').save(preview)
        report['preview']=str(preview.resolve())
    target.with_suffix(target.suffix+'.verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))

if __name__=='__main__':
    try:main()
    except Exception as error:
        # Controlled local errors explain scope; remote error strings and URLs are excluded.
        message=str(error) if isinstance(error,(ValueError,RuntimeError,FileExistsError)) else type(error).__name__
        print(json.dumps({'error':message},ensure_ascii=True),file=sys.stderr);sys.exit(1)
