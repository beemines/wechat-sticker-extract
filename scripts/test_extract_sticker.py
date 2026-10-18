"""Offline behavior checks; uses only synthetic stickers and SQLite records."""
from pathlib import Path
import hashlib
import importlib.util
import io
import sqlite3
import sys
import unittest
from PIL import Image

SCRIPT = Path(__file__).with_name('extract_sticker.py')

def load_helper():
    if not SCRIPT.exists():
        return None
    spec=importlib.util.spec_from_file_location('sticker_helper',SCRIPT)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), 'Reusable extraction helper has not been implemented')
        self.helper=load_helper()

    def test_original_gif_requires_animation_and_exact_hash(self):
        buffer=io.BytesIO()
        a=Image.new('RGB',(16,16),'red');b=Image.new('RGB',(16,16),'blue')
        a.save(buffer,format='GIF',save_all=True,append_images=[b],duration=[50,70],loop=0)
        data=buffer.getvalue();digest=hashlib.md5(data).hexdigest()
        report=self.helper.validate_original(data,digest)
        self.assertEqual((report['format'],report['frames'],report['duration_ms']),('gif',2,120))
        with self.assertRaisesRegex(ValueError,'MD5'):
            self.helper.validate_original(data,'0'*32)
        still=io.BytesIO();a.save(still,format='PNG')
        with self.assertRaisesRegex(ValueError,'animated'):
            self.helper.validate_original(still.getvalue(),hashlib.md5(still.getvalue()).hexdigest())

    def test_older_message_selection_does_not_export_the_newest_sticker(self):
        con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row
        table='Msg_'+'a'*32
        con.execute('CREATE TABLE '+table+' (local_id INTEGER,local_type INTEGER,create_time INTEGER,message_content TEXT,WCDB_CT_message_content INTEGER)')
        old='<msg><emoji md5="'+'1'*32+'" cdnurl="https://a.qpic.cn/old" /></msg>'
        new='<msg><emoji md5="'+'2'*32+'" cdnurl="https://a.qpic.cn/new" /></msg>'
        con.executemany('INSERT INTO '+table+' VALUES (?,?,?,?,?)',[(4,47,1000,old,0),(5,47,2000,new,0),(6,1,2500,'private ordinary text',0)])
        rows=self.helper.sticker_rows(con,table,local_id=4)
        self.assertEqual(len(rows),1)
        self.assertEqual(self.helper.emoji_attributes(rows[0]['message_content'])['md5'],'1'*32)
        self.assertEqual(len(self.helper.sticker_rows(con,table,after=1100,before=2100)),1)
        self.assertEqual(len(self.helper.sticker_rows(con,table,local_id=6)),0)
        con.close()

    def test_compressed_attachment_and_download_host_boundary(self):
        try:import zstandard
        except ImportError:
            self.skipTest('Install zstandard to exercise compressed-message parsing')
        xml=b'<msg><emoji md5="0123456789abcdef0123456789abcdef" aeskey="not-to-be-logged" /></msg>'
        attrs=self.helper.emoji_attributes(zstandard.ZstdCompressor().compress(xml))
        self.assertEqual(attrs['md5'],'0123456789abcdef0123456789abcdef')
        self.assertTrue(self.helper.allowed_resource_url('https://emoji.qpic.cn/file'))
        self.assertFalse(self.helper.allowed_resource_url('https://qpic.cn.evil.example/file'))
        self.assertFalse(self.helper.allowed_resource_url('file:///C:/private'))

if __name__=='__main__':unittest.main(verbosity=2)
