"""Configurable SoloLoop typography; retain original photography and brand assets."""
from pathlib import Path
from functools import lru_cache
import math,os,re
from PIL import Image,ImageDraw,ImageFont,ImageFilter

def ease(x):return 1-(1-max(0,min(1,x)))**3
def rgba(c):
    if isinstance(c,(tuple,list)):return tuple(c)
    c=c.lstrip('#');return tuple(int(c[i:i+2],16) for i in [0,2,4])+(255,)

class Graphics:
    def __init__(self,edit,style,assets,duration):
        self.e,self.s,self.d=edit,style,duration;self.w,self.h=edit.get('width',1080),edit.get('height',1440)
        self.sx,self.sy=self.w/1080,self.h/1440;self.assets=Path(assets)
        self.white=rgba(style.get('palette',{}).get('white','#FFFFFF'));self.orange=rgba(style.get('palette',{}).get('orange','#F59A31'))
        cfg=style.get('logo',{});self.logo=Image.open(edit.get('logo') or self.assets/cfg.get('file','SoloLoop-logo-original.png')).convert('RGBA')
        self.logo.thumbnail((round(cfg.get('width',250)*self.sx),round(110*self.sy)),Image.Resampling.LANCZOS)
        self.lx=self.w-round(cfg.get('right',40)*self.sx)-self.logo.width;self.ly=round(cfg.get('top',77)*self.sy)
        self.shadow=Image.new('RGBA',self.logo.size);self.shadow.putalpha(self.logo.getchannel('A').point(lambda v:round(v*.75)))
        self.shadow=self.shadow.filter(ImageFilter.GaussianBlur(2*self.sx))

    @lru_cache(maxsize=100)
    def font(self,kind,size):
        size=max(8,round(size*self.sx));serif=kind in ['serif','identity'];fs=self.s.get('fonts',{})
        names=[fs.get('serif' if serif else 'sans',''),*(['NotoSerifSC-VF.ttf','SourceHanSerifSC-VF.ttf'] if serif else ['NotoSansSC-VF.ttf','SourceHanSansSC-VF.ttf'])]
        roots=[Path(x) for x in [self.e.get('font_dir'),os.environ.get('SOLOLOOP_FONT_DIR'),'C:/Windows/Fonts','/usr/share/fonts/opentype/noto','/usr/share/fonts/truetype/noto'] if x]
        weight={'black':fs.get('headline_weight',900),'serif':fs.get('caption_weight',600),'identity':fs.get('identity_weight',500),'bold':700,'regular':400}.get(kind,700)
        for root in roots:
            for name in names:
                if not name:continue
                p=root/name
                if not p.is_file():continue
                f=ImageFont.truetype(str(p),size)
                try:f.set_variation_by_axes([weight if a['name'].lower()==b'weight' else a['default'] for a in f.get_variation_axes()])
                except (OSError,AttributeError):pass
                return f
        name=('NotoSerifCJK' if serif else 'NotoSansCJK')+('-Regular.ttc' if kind in ['regular','identity'] else '-Bold.ttc')
        for root in roots:
            if not (root/name).is_file():continue
            first=None
            for index in range(10):
                try:f=ImageFont.truetype(str(root/name),size,index=index)
                except OSError:break
                if first is None:first=f
                if ' SC' in f.getname()[0]:return f
            if first:return first
        raise RuntimeError('Noto/Source Han Chinese fonts missing. Set font_dir or SOLOLOOP_FONT_DIR; no Arial fallback.')

    @lru_cache(maxsize=2000)
    def sprite(self,text,kind,size,color,caption=False):
        f=self.font(kind,size);b=f.getbbox(text,anchor='ls');pad=max(5,round(13*self.sx))
        im=Image.new('RGBA',(math.ceil(f.getlength(text))+2*pad,b[3]-b[1]+2*pad));sh=Image.new('RGBA',im.size)
        ImageDraw.Draw(sh).text((pad-b[0]+3*self.sx,pad-b[1]+4*self.sy),text,font=f,anchor='ls',fill=(24,24,24,180),stroke_width=1)
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(2.5*self.sx)))
        ImageDraw.Draw(im).text((pad-b[0],pad-b[1]),text,font=f,anchor='ls',fill=color,stroke_width=1 if caption else 0,stroke_fill=(110,110,110,160))
        return im,pad,b

    def text(self,im,text,x,y,size=58,kind='black',color=None,alpha=1):
        sp,pad,_=self.sprite(text,kind,size,rgba(color) if color is not None else self.white)
        if alpha<1:
            sp=sp.copy();sp.putalpha(sp.getchannel('A').point(lambda v:round(v*max(0,alpha))))
        im.alpha_composite(sp,(round(x*self.sx-pad),round(y*self.sy-pad)))

    def line(self,im,e,t):
        if not e['start']<=t<e['end']:return
        text=e['text'];size=e.get('size',126);kind=e.get('font','black');f=self.font(kind,size)
        while f.getlength(text)>e.get('max_width',980-e.get('x',62))*self.sx and size>24:size-=2;f=self.font(kind,size)
        x=e.get('x',62);common=f.getbbox(text,anchor='ls')
        for i,ch in enumerate(text):
            dt=t-e['start']-i*e.get('stagger',.035)
            if e['start']==0:dt=max(.14,dt)
            if dt<0:x+=f.getlength(ch)/self.sx;continue
            p=ease(dt/.2);a=p*min(1,max(0,(e['end']-t)/e.get('fade',.15)));dx=0;dy=25*(1-p)
            if e.get('exit')=='scatter' and e['end']-t<.25:
                q=max(0,min(1,(t-(e['end']-.25)-i*.008)/.23));dx=(1 if i%2 else -1)*35*q*q;dy-=65*q*q;a*=1-q
            b=f.getbbox(ch,anchor='ls')
            self.text(im,ch,x+dx,e.get('y',720)+(b[1]-common[1])/self.sy+dy,size,kind,e.get('color'),a)
            x+=f.getlength(ch)/self.sx

    def card(self,im,e,t):
        if not e['start']<=t<e['end']:return
        p=ease((t-e['start'])/.2);a=p*min(1,max(0,(e['end']-t)/.1));w,h=round(e.get('width',580)*self.sx),round(e.get('height',138)*self.sy)
        card=Image.new('RGBA',(w,h));d=ImageDraw.Draw(card);d.rounded_rectangle((0,0,w-1,h-1),radius=round(22*self.sx),fill=tuple(self.s.get('palette',{}).get('panel',[35,39,42,176])))
        size=e.get('size',92);f=self.font('black',size)
        while f.getlength(e['text'])>w-48*self.sx and size>24:size-=2;f=self.font('black',size)
        b=f.getbbox(e['text']);y=23*self.sy if e.get('subtitle') else (h-b[3]+b[1])/2
        d.text((25*self.sx,y-b[1]),e['text'],font=f,fill=self.white)
        if e.get('subtitle'):
            f2=self.font('regular',36);b=f2.getbbox(e['subtitle']);d.text((29*self.sx,h-55*self.sy-b[1]),e['subtitle'],font=f2,fill=self.white)
        if a<1:card.putalpha(card.getchannel('A').point(lambda v:round(v*a)))
        im.alpha_composite(card,(round(e.get('x',55)*self.sx),round((e.get('y',676)+18*(1-p))*self.sy)))

    def wrap_caption(self,text):
        cfg=self.s.get('caption',{});maxw=cfg.get('max_width',944)*self.sx
        for size in range(cfg.get('size',58),cfg.get('min_size',48)-1,-2):
            f=self.font('serif',size);lines=['']
            for token in re.findall(r'[A-Za-z0-9][A-Za-z0-9%.,:/+_-]*|[^A-Za-z0-9]',text):
                if lines[-1] and f.getlength(lines[-1]+token)>maxw:lines.append(token)
                else:lines[-1]+=token
            if len(lines)<=2 and all(f.getlength(x)<=maxw for x in lines):return lines,size
        raise ValueError('Split long caption by semantic units: '+text)

    def caption(self,im,c,t):
        if not c['start']<=t<c['end']:return
        lines,size=self.wrap_caption(c['text']);hi=c.get('highlight','');idx=c['text'].find(hi) if hi else -1;ci=0;cfg=self.s.get('caption',{})
        for row,line in enumerate(lines):
            f=self.font('serif',size);x=(self.w-f.getlength(line))/2;common=f.getbbox(line,anchor='ls')
            for ch in line:
                color=self.orange if idx>=0 and idx<=ci<idx+len(hi) else self.white
                sp,pad,b=self.sprite(ch,'serif',size,color,True)
                y=(cfg.get('y',1058)+row*(size+cfg.get('line_gap',14)))*self.sy+b[1]-common[1]
                im.alpha_composite(sp,(round(x-pad),round(y-pad)));x+=f.getlength(ch);ci+=1

    @lru_cache(maxsize=16)
    def nav(self,active):
        cfg=self.s.get('nav',{});h=round(cfg.get('height',57)*self.sy);im=Image.new('RGBA',(self.w,h),(54,58,61,172));d=ImageDraw.Draw(im)
        chapters=self.e.get('chapters',[]);weights=[max(3,len(c['label']))+1 for c in chapters];total=sum(weights) or 1;x=0
        for i,c in enumerate(chapters):
            w=self.w*weights[i]/total;size=cfg.get('active_size',27) if i==active else cfg.get('idle_size',25);f=self.font('bold' if i==active else 'regular',size)
            while f.getlength(c['label'])>w-12*self.sx and size>16:size-=1;f=self.font('regular',size)
            b=f.getbbox(c['label']);d.text((x+(w-f.getlength(c['label']))/2,13*self.sy-b[1]),c['label'],font=f,fill=self.white if i==active else (185,187,189,235))
            if i:d.line((round(x),0,round(x),h-4),fill=(255,255,255,35))
            x+=w
        return im

    def at(self,t):
        im=Image.new('RGBA',(self.w,self.h))
        for e in self.e.get('elements',[]):(self.card if e.get('type')=='card' else self.line)(im,e,t)
        for e in self.e.get('topics',[]):
            if e['start']<=t<e['end']:
                size=29;f=self.font('bold',size)
                while f.getlength(e['text'])>690*self.sx and size>20:size-=1;f=self.font('bold',size)
                self.text(im,e['text'],(790-f.getlength(e['text'])/self.sx)/2,83,size,'bold')
        active=next((i for i,c in enumerate(self.e.get('chapters',[])) if c['start']<=t<c['end']),-1)
        im.alpha_composite(self.nav(active),(0,0));cfg=self.s.get('nav',{});nh=cfg.get('height',57);ph=cfg.get('progress_height',4)
        ImageDraw.Draw(im).rectangle((0,round((nh-ph)*self.sy),max(1,round(self.w*t/self.d)),round(nh*self.sy)-1),fill=(255,255,255,230))
        im.alpha_composite(self.shadow,(self.lx+1,self.ly+2));im.alpha_composite(self.logo,(self.lx,self.ly))
        for c in self.e.get('captions',[]):self.caption(im,c,t)
        return im
