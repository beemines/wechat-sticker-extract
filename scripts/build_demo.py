"""Rebuild the short, privacy-safe UI walkthrough. Interfaces are redrawn, not a live recording.
Requires Pillow, FFmpeg and a Chinese system font. Does not access WeChat or the network.
"""
from pathlib import Path
import argparse, bisect, hashlib, json, shutil, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageSequence

ROOT=Path(__file__).resolve().parents[1]
W,H=1440,900
FONTS={}
REGULAR=BOLD=None
GIFS=[]
TIMELINES=[]
WINDOW_SHOT=None
INK='#202124';MUTED='#74777D';BLUE='#2368DB';GREEN='#07B75C'

def font(size,bold=False):
    key=(size,bold)
    if key not in FONTS:FONTS[key]=ImageFont.truetype(str(BOLD if bold else REGULAR),size)
    return FONTS[key]

def text(d,xy,value,size=19,color=INK,bold=False):d.text(xy,value,font=font(size,bold),fill=color)
def box(d,rect,fill,outline=None,radius=10):d.rounded_rectangle(rect,radius,fill=fill,outline=outline)
def paste_gif(im,index,xy,size=180,phase=0):
    timeline=TIMELINES[index]
    position=bisect.bisect_right(timeline,(phase*1000)%timeline[-1])
    frame=GIFS[index][position].resize((size,size),Image.Resampling.LANCZOS)
    im.paste(frame,xy,frame)

def frame(title,step):
    im=Image.new('RGB',(W,H),'#EDF1F5');d=ImageDraw.Draw(im)
    text(d,(54,28),title,29,bold=True)
    text(d,(1130,36),'界面重绘 · 非实录',17,MUTED)
    text(d,(55,852),f'{step} / 3',17,MUTED)
    return im

def window(d,rect,title,fill='#FAFAFA'):
    x,y,x2,y2=rect
    box(d,(x+2,y+7,x2+2,y2+7),'#DAE0E7',radius=12)
    box(d,rect,fill,'#CFD4DC',12)
    text(d,(x+20,y+11),title,18)
    for offset,char in [(112,'—'),(70,'□'),(30,'×')]:text(d,(x2-offset,y+9),char,21,MUTED)
    d.line((x,y+43,x2,y+43),fill='#E6E7EB')

def screenshot_window():
    im=Image.new('RGB',(960,520),'#F5F5F5');d=ImageDraw.Draw(im)
    window(d,(0,0,959,519),'微信',fill='#F5F5F5')
    paste_gif(im,0,(110,122),300,0)
    paste_gif(im,1,(550,122),300,0)
    return im


def wechat_scene(phase=0):
    im=frame('截一张窗口图，里面有这两个表情就行',1);d=ImageDraw.Draw(im)
    im.paste(WINDOW_SHOT.resize((1140,618),Image.Resampling.LANCZOS),(150,146))
    text(d,(923,852),'只上传这一张截图',17,MUTED)
    return im


def codex_scene(phase=0):
    im=frame('上传这一张窗口截图：帮我获取这两个表情',2);d=ImageDraw.Draw(im)
    window(d,(100,96,1340,816),'Codex')
    d.rectangle((101,140,352,814),fill='#F1F0EE')
    text(d,(126,163),'新任务',20,bold=True)
    text(d,(126,217),'搜索任务',18,MUTED)
    text(d,(126,282),'最近',16,MUTED)
    box(d,(112,318,339,360),'#E4E3E0',radius=8);text(d,(125,328),'提取微信表情',18)
    text(d,(126,398),'项目',16,MUTED)
    text(d,(126,440),'wechat-sticker-extract',16)
    text(d,(387,159),'提取微信表情',22,bold=True)
    box(d,(628,214,1275,424),'#F0EFED',radius=18)
    text(d,(650,234),'帮我获取这两个表情',23)
    box(d,(650,282,888,403),'#E7E7E7','#D5D5D5',6)
    im.paste(WINDOW_SHOT.resize((222,120),Image.Resampling.LANCZOS),(658,283))
    text(d,(912,321),'窗口截图.png',18,MUTED)
    text(d,(395,457),'已保存两张 GIF。',23,bold=True)
    text(d,(395,505),'03_魔法少女.gif    240 × 240    64 帧',21)
    text(d,(395,545),'04_蓝毛剪刀.gif    240 × 240    64 帧',21)
    for i,x in enumerate([407,610]):paste_gif(im,i,(x,582),100,phase)
    text(d,(395,703),'已保存到 wechat_emoji 文件夹。',20,BLUE)
    box(d,(390,746,1294,801),'white','#DCDDDC',14);text(d,(412,762),'发送消息…',18,'#A1A1A1')
    text(d,(837,852),'账号、聊天、时间信息均为演示数据',17,MUTED)
    return im

def explorer_scene(phase=0):
    im=frame('打开文件夹，拿到可以直接分享的 GIF',3);d=ImageDraw.Draw(im)
    window(d,(65,108,1375,814),'wechat_emoji  —  文件资源管理器','white')
    text(d,(87,166),'←     →     ↑',22,MUTED)
    box(d,(265,159,1130,202),'#F4F5F7',radius=7)
    text(d,(285,170),'此电脑   >   项目   >   wechat_emoji',18)
    text(d,(87,226),'新建     剪切     复制     重命名     分享     ···',18)
    d.line((66,264,1374,264),fill='#E6E8EB')
    d.rectangle((66,265,269,783),fill='#FAFAFB')
    for j,name in enumerate(['主页','桌面','下载','文档','图片','wechat_emoji']):
        y=286+j*54
        if j==5:box(d,(77,y-2,257,y+38),'#E6F0FC',radius=6)
        text(d,(96,y+3),name,18)
    box(d,(298,291,550,582),'#EAF2FF','#BCD2F7',8)
    box(d,(575,291,827,582),'#EAF2FF','#BCD2F7',8)
    for i,x in enumerate([314,591]):
        paste_gif(im,i,(x,310),220,phase)
        name=['03_魔法少女.gif','04_蓝毛剪刀.gif'][i]
        text(d,(x+110-d.textlength(name,font=font(19))/2,545),name,19)
    d.line((853,265,853,783),fill='#E5E7EB')
    text(d,(893,293),'预览',20,bold=True)
    paste_gif(im,0,(930,352),300,phase)
    text(d,(925,690),'GIF  ·  64 帧  ·  4.27 秒',18,MUTED)
    text(d,(304,654),'核验记录另存为 .verification.json',17,MUTED)
    text(d,(86,786),'2 个动图',15,MUTED)
    text(d,(890,852),'预览在播放；原文件没有重新编码',17,MUTED)
    return im

def overview():
    im=Image.new('RGB',(1440,640),'#F4F6F8');d=ImageDraw.Draw(im)
    text(d,(46,27),'一张窗口截图  →  两个 GIF',30,bold=True)
    text(d,(1160,39),'界面重绘 · 非实录',16,MUTED)
    im.paste(WINDOW_SHOT.resize((650,352),Image.Resampling.LANCZOS),(40,158))
    window(d,(750,94,1400,585),'文件资源管理器 · wechat_emoji')
    for i,x in enumerate([788,1080]):
        box(d,(x,179,x+270,487),'#EBF2FC',radius=7)
        paste_gif(im,i,(x+25,195),220,.1)
        name=['03_魔法少女.gif','04_蓝毛剪刀.gif'][i]
        text(d,(x+135-d.textlength(name,font=font(19))/2,455),name,19)
    text(d,(793,535),'240 × 240  ·  64 帧  ·  循环播放',18,MUTED)
    text(d,(46,606),'界面为重绘示意，使用现有角色 GIF 展示操作流程。',16,MUTED)
    return im

def pick_font(explicit,bold=False):
    if explicit:return Path(explicit)
    choices=([r'C:\Windows\Fonts\msyhbd.ttc'] if bold else [r'C:\Windows\Fonts\msyh.ttc'])+['/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc','/System/Library/Fonts/PingFang.ttc']
    for p in choices:
        if Path(p).exists():return Path(p)
    raise FileNotFoundError('Use --font and --bold-font to supply Chinese fonts')

def main():
    global REGULAR,BOLD,GIFS,TIMELINES,WINDOW_SHOT
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--ffmpeg',default=shutil.which('ffmpeg'));ap.add_argument('--font');ap.add_argument('--bold-font')
    ap.add_argument('--assets-dir',type=Path,default=ROOT/'docs/assets');ap.add_argument('--qa-dir',type=Path)
    args=ap.parse_args();REGULAR=pick_font(args.font);BOLD=pick_font(args.bold_font,True)
    assets=args.assets_dir;assets.mkdir(parents=True,exist_ok=True)
    reports=[]
    for name in ['magical-girl.gif','blue-scissors.gif']:
        p=assets/name
        with Image.open(p) as image:
            frames=[];duration=0;timeline=[]
            for frame_ in ImageSequence.Iterator(image):
                frames.append(frame_.convert('RGBA'));duration+=frame_.info.get('duration',100);timeline.append(duration)
            GIFS.append(frames);TIMELINES.append(timeline);reports.append({'file':name,'frames':len(frames),'duration_ms':duration,'md5':hashlib.md5(p.read_bytes()).hexdigest()})
    WINDOW_SHOT=screenshot_window()
    WINDOW_SHOT.save(assets/'window-shot.png')
    scenes=[wechat_scene,codex_scene,explorer_scene]
    overview().save(assets/'demo-overview.png')
    for scene,name in zip(scenes,['demo-chat','demo-request','demo-result']):scene(.1).save(assets/(name+'.png'))
    preview=[]
    for scene in scenes:
        for n in range(43):preview.append(scene(n/10).resize((960,600),Image.Resampling.LANCZOS))
    preview[0].save(assets/'workflow-preview.gif',save_all=True,append_images=preview[1:],duration=100,loop=0,optimize=True)
    if not args.ffmpeg:raise FileNotFoundError('Supply --ffmpeg to render video')
    output=assets/'workflow-demo.mp4';fps=20
    cmd=[args.ffmpeg,'-y','-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(fps),'-i','pipe:0','-an','-c:v','libx264','-crf','20','-preset','fast','-pix_fmt','yuv420p','-movflags','+faststart',str(output)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        for i,scene in enumerate(scenes):
            print(f'Rendering UI scene {i+1}/3',flush=True)
            for n in range(6*fps):proc.stdin.write(scene(n/fps).tobytes())
        proc.stdin.close();error=proc.stderr.read().decode('utf-8',errors='replace');code=proc.wait()
        if code:raise RuntimeError(error)
    finally:
        if proc.poll() is None:proc.kill();proc.wait()
    if args.qa_dir:
        args.qa_dir.mkdir(parents=True,exist_ok=True)
        sheet=Image.new('RGB',(960,1800),'white')
        for i,scene in enumerate(scenes):sheet.paste(scene(.1).resize((960,600)),(0,i*600))
        sheet.save(args.qa_dir/'realistic-ui-contact-sheet.png')
    manifest={'kind':'redrawn interfaces, not live recording; existing character GIFs as workflow examples','video':{'width':W,'height':H,'fps':fps,'duration_seconds':18,'audio':False},'samples':reports,'assets':[p.name for p in sorted(assets.iterdir()) if p.is_file() and p.name!='manifest.json']}
    (assets/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('UI walkthrough ready.')

if __name__=='__main__':main()
