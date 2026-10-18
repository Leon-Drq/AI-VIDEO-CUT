"""Local RVM matte generation and original-pixel behind-person typography.

Inputs must be normalized, constant-frame-rate, square-pixel, zero-origin media.
This helper packages an already edited video; it does not choose speech cuts.
"""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def binary(name):
    p = shutil.which(str(name))
    if not p and Path(name).is_file():
        p = str(Path(name).resolve())
    if not p:
        raise ValueError(f'Executable not found: {name}')
    return p


def inspect_video(path, ffprobe):
    doc = json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-show_streams',
        '-show_format', '-of', 'json', str(path)], encoding='utf-8'))
    v = next(s for s in doc['streams'] if s['codec_type'] == 'video')
    rotation = float(v.get('tags', {}).get('rotate', 0))
    for side in v.get('side_data_list', []):
        rotation = float(side.get('rotation', rotation))
    rate = Fraction(v['avg_frame_rate'])
    if rotation % 360 or rate <= 0 or rate != Fraction(v['r_frame_rate']):
        raise ValueError('Normalize rotation and CFR before packaging.')
    if v.get('sample_aspect_ratio', '1:1') not in ('1:1', 'N/A'):
        raise ValueError('Normalize to square pixels before packaging.')
    if abs(float(v.get('start_time', 0))) > 1 / float(rate):
        raise ValueError('Video must start at zero; normalize timestamps first.')
    a = next((s for s in doc['streams'] if s['codec_type'] == 'audio'), None)
    if a and abs(float(a.get('start_time', 0))) > 1 / float(rate):
        raise ValueError('Resolve the audio start offset before packaging.')
    duration = float(v.get('duration') or doc['format']['duration'])
    frames = int(v['nb_frames']) if str(v.get('nb_frames', '')).isdigit() else None
    return {'width':v['width'], 'height':v['height'], 'fps':str(rate),
            'duration':duration, 'frames':frames, 'audio':bool(a)}


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def destination(path, forbidden):
    path = Path(path).resolve()
    if path.exists() or path in [Path(p).resolve() for p in forbidden]:
        raise ValueError(f'Refusing to overwrite: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.stem + '.partial' + path.suffix)
    if temporary.exists():
        raise ValueError(f'Previous partial output exists: {temporary}')
    return path, temporary


def matte(args):
    import onnxruntime as ort
    source = Path(args.input).resolve()
    ff, fp = binary(args.ffmpeg), binary(args.ffprobe)
    info = inspect_video(source, fp)
    out, temporary = destination(args.output, [source, args.model])
    if out.suffix.lower() != '.mkv':
        raise ValueError('Use .mkv for the lossless FFV1 alpha stream.')
    width = min(args.width, info['width']) // 2 * 2
    height = max(2, round(width * info['height'] / info['width'] / 2) * 2)
    cuts = set(int(x) for x in args.cuts.split(',') if x.strip())
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = args.threads
    opts.inter_op_num_threads = 1
    session = ort.InferenceSession(str(Path(args.model).resolve()), sess_options=opts,
                                   providers=['CPUExecutionProvider'])
    names = {v.name for v in session.get_inputs()}
    if names != {'src', 'r1i', 'r2i', 'r3i', 'r4i', 'downsample_ratio'}:
        raise ValueError('Expected the six-input recurrent RVM ONNX interface.')
    cap = cv2.VideoCapture(str(source))
    log = open(out.with_suffix('.log'), 'w', encoding='utf-8')
    proc = subprocess.Popen([ff, '-hide_banner', '-n', '-f', 'rawvideo', '-pix_fmt', 'gray',
        '-s', f'{width}x{height}', '-r', info['fps'], '-i', '-', '-c:v', 'ffv1', '-level', '3',
        '-pix_fmt', 'gray', '-threads', str(args.threads), str(temporary)], stdin=subprocess.PIPE, stderr=log)
    n = 0
    states = None
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if n == 0 or n in cuts:
                states = [np.zeros((1,1,1,1), np.float32) for _ in range(4)]
            rgb = cv2.cvtColor(cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
            feed = {'src':np.transpose(rgb.astype(np.float32)/255, (2,0,1))[None],
                    'downsample_ratio':np.array([args.downsample], np.float32)}
            feed.update({f'r{i+1}i':s for i,s in enumerate(states)})
            values = session.run(None, feed)
            states = values[2:]
            if len(states) != 4:
                raise ValueError('Unexpected RVM recurrent output count.')
            alpha = np.clip(values[1][0,0]*255, 0, 255).astype(np.uint8)
            if alpha.shape != (height, width):
                raise ValueError('Unexpected RVM alpha dimensions.')
            proc.stdin.write(alpha.tobytes())
            n += 1
            if n % 90 == 0:
                print(f'matte: {n} frames', flush=True)
    finally:
        cap.release()
        proc.stdin.close()
        result = proc.wait()
        log.close()
    if result or not n or (info['frames'] is not None and n != info['frames']):
        raise RuntimeError('Matte encode or source frame count failed; inspect partial output and log.')
    temporary.rename(out)
    write_json(out.with_suffix('.json'), {'source':str(source), 'source_sha256':sha256(source),
        'matte':str(out), 'frames':n, 'fps':info['fps'], 'size':[width,height],
        'source_size':[info['width'],info['height']], 'reset_frames':sorted(cuts)})
    print(out, flush=True)


class Typography:
    def __init__(self, font_path):
        self.path, self.cache = font_path, {}

    def font(self, size, weight):
        key = (size, weight)
        if key not in self.cache:
            f = ImageFont.truetype(str(self.path), size)
            try:
                axes = f.get_variation_axes()
            except OSError:
                axes = []
            if axes:
                values = [a['default'] for a in axes]
                for i,a in enumerate(axes):
                    name = a['name'].decode() if isinstance(a['name'], bytes) else a['name']
                    if 'weight' in name.lower():
                        values[i] = min(a['maximum'], max(a['minimum'], weight))
                f.set_variation_by_axes(values)
            self.cache[key] = f
        return self.cache[key]

    def measure(self, text, size, weight, tracking):
        f = self.font(size, weight)
        return sum(f.getlength(c) for c in text) + max(0,len(text)-1)*tracking

    def draw(self, image, text, xy, size, weight, tracking, fill):
        f = self.font(size, weight)
        x,y = xy
        baseline = y-f.getbbox(text, anchor='ls')[1]
        draw = ImageDraw.Draw(image)
        for ch in text:
            draw.text((round(x),round(baseline)),ch,font=f,fill=fill,anchor='ls')
            x += f.getlength(ch)+tracking


def title_sprite(cue, typo):
    size, weight, tracking = cue['size'], cue.get('weight',900), cue.get('tracking',-8)
    text = cue['text']
    tw = math.ceil(typo.measure(text,size,weight,tracking))
    pad = 32
    glyph = Image.new('RGBA', (tw+pad*2,size+pad*3))
    typo.draw(glyph,text,(pad,pad),size,weight,tracking,tuple(cue.get('color',[249,249,247,255])))
    shadow = Image.new('RGBA',glyph.size)
    shadow.putalpha(glyph.getchannel('A').filter(ImageFilter.GaussianBlur(9)).point(lambda v:round(v*.52)))
    output = Image.new('RGBA',glyph.size)
    output.alpha_composite(shadow,(0,8))
    output.alpha_composite(glyph)
    return output, pad, tw


def caption_sprite(text, style, typo, canvas):
    size,weight,tracking = style.get('size',52),style.get('weight',500),style.get('tracking',4)
    pad = style.get('padding',34)
    width = math.ceil(typo.measure(text,size,weight,tracking))+pad*2
    height = style.get('height',88)
    if width > canvas[0]-style.get('margin',60)*2:
        raise ValueError(f'Caption too wide; split the cue: {text}')
    if style.get('y',952)+height > canvas[1]:
        raise ValueError('Caption exceeds canvas height; adjust subtitle_style.y.')
    sprite = Image.new('RGBA',(width,height))
    ImageDraw.Draw(sprite).rounded_rectangle((0,0,width-1,height-1),radius=height//2,
        fill=tuple(style.get('background',[13,16,22,150])),outline=(255,255,255,30),width=1)
    f=typo.font(size,weight)
    bbox=f.getbbox(text,anchor='ls')
    text_h=bbox[3]-bbox[1]
    typo.draw(sprite,text,(pad,(height-text_h)/2-1),size,weight,tracking,
              tuple(style.get('color',[249,249,247,255])))
    return sprite


def render(args):
    config = Path(args.config).resolve()
    cfg = json.loads(config.read_text(encoding='utf-8-sig'))
    def path(key):
        p=Path(cfg[key]);return p.resolve() if p.is_absolute() else (config.parent/p).resolve()
    source, mask_path, font_path = path('input'), path('matte'), path('font')
    ff,fp = binary(args.ffmpeg),binary(args.ffprobe)
    info=inspect_video(source,fp)
    width,height=cfg['canvas']
    if [width,height] != [info['width'],info['height']]:
        raise ValueError('Canvas must match the normalized source; recalculate layout explicitly.')
    if width%2 or height%2:
        raise ValueError('Even canvas dimensions required for yuv420p.')
    manifest=mask_path.with_suffix('.json')
    verified=False
    if manifest.exists():
        m=json.loads(manifest.read_text('utf-8'))
        if m.get('source_sha256') != sha256(source) or Fraction(m['fps']) != Fraction(info['fps']):
            raise ValueError('Matte manifest belongs to a different source or timebase.')
        verified=True
    ranges=cfg.get('presenter_ranges',[])
    titles=cfg.get('titles',[])
    captions=cfg.get('captions',[])
    for cue in ranges+titles+captions:
        if not (0 <= cue['start'] < cue['end'] <= info['duration']+1/float(Fraction(info['fps']))):
            raise ValueError(f'Invalid cue interval: {cue}')
    for cue in titles:
        if not any(r['start']<=cue['start'] and r['end']>=cue['end'] for r in ranges):
            raise ValueError(f'Title not inside a presenter range: {cue["text"]}')
    captions.sort(key=lambda c:c['start'])
    if any(a['end']>b['start'] for a,b in zip(captions,captions[1:])):
        raise ValueError('Overlapping subtitle cues; resolve the reading sequence first.')
    typo=Typography(font_path)
    heading=[]
    for cue in titles:
        sprite,pad,tw=title_sprite(cue,typo)
        if not cue.get('allow_crop',False) and (cue['x']<0 or cue['y']<0 or cue['x']+tw>width or cue['y']+cue['size']>height):
            raise ValueError(f'Title outside canvas: {cue["text"]}')
        heading.append((cue,sprite,pad))
    style=cfg.get('subtitle_style',{})
    subs=[(c,caption_sprite(c['text'],style,typo,(width,height))) for c in captions]
    grade=cfg.get('background',{})
    gains=np.array(grade.get('gains',[.67,.71,.79]),np.float32)
    offsets=np.array(grade.get('offsets',[0,4,12]),np.float32)
    out,temporary=destination(path('output'),[source,mask_path,font_path,config])
    if out.suffix.lower() != '.mp4':
        raise ValueError('Use an .mp4 output path.')
    cap,mc=cv2.VideoCapture(str(source)),cv2.VideoCapture(str(mask_path))
    if not cap.isOpened() or not mc.isOpened():
        raise ValueError('Cannot open source video or matte.')
    fps=Fraction(info['fps'])
    matte_fps=mc.get(cv2.CAP_PROP_FPS)
    if abs(matte_fps-float(fps)) > .001:
        raise ValueError('Matte and source frame rates differ.')
    mw,mh=mc.get(cv2.CAP_PROP_FRAME_WIDTH),mc.get(cv2.CAP_PROP_FRAME_HEIGHT)
    if not mh or abs((mw/mh)/(width/height)-1)>.01:
        raise ValueError('Matte and source aspect ratios differ; check their crop.')
    log=open(out.with_suffix('.log'),'w',encoding='utf-8')
    proc=subprocess.Popen([ff,'-hide_banner','-n','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}',
        '-r',str(fps),'-i','-','-i',str(source),'-map','0:v:0','-map','1:a:0?',
        '-c:v','libx264','-preset',args.preset,'-crf',str(args.crf),'-threads',str(args.threads),
        '-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(temporary)],stdin=subprocess.PIPE,stderr=log)
    n=0
    try:
        while True:
            ok,frame=cap.read()
            if not ok:break
            ma,mask=mc.read()
            if not ma:raise ValueError(f'Matte shorter than source at frame {n}.')
            t=float(n/fps)
            raw=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
            if any(r['start']<=t<r['end'] for r in ranges):
                bg=np.clip(np.asarray(raw).astype(np.float32)*gains+offsets,0,255).astype(np.uint8)
                im=Image.fromarray(bg).convert('RGBA')
                for cue,sprite,pad in heading:
                    if cue['start']<=t<cue['end']:
                        fade=cue.get('fade_in',.22)
                        x=1 if fade<=0 else min(1,max(0,(t-cue['start'])/fade))
                        q=1-(1-x)**3
                        layer=sprite.copy()
                        layer.putalpha(layer.getchannel('A').point(lambda v:round(v*q)))
                        im.alpha_composite(layer,(round(cue['x']-pad),round(cue['y']-pad+cue.get('rise',18)*(1-q))))
                alpha=Image.fromarray(mask[:,:,0]).resize((width,height),Image.Resampling.BILINEAR)
                im.paste(raw,(0,0),alpha)
                im=im.convert('RGB')
            else:
                im=raw
            for cue,sprite in subs:
                if cue['start']<=t<cue['end']:
                    x=(width-sprite.width)//2;y=style.get('y',952)
                    under=im.crop((x,y,x+sprite.width,y+sprite.height)).filter(ImageFilter.GaussianBlur(style.get('blur',4)))
                    rounded=Image.new('L',under.size)
                    ImageDraw.Draw(rounded).rounded_rectangle((0,0,under.width-1,under.height-1),radius=under.height//2,fill=255)
                    im.paste(under,(x,y),rounded)
                    im=im.convert('RGBA');im.alpha_composite(sprite,(x,y));im=im.convert('RGB')
                    break
            proc.stdin.write(im.tobytes());n+=1
            if n%90==0:print(f'render: {n} frames',flush=True)
        extra,_=mc.read()
        if extra:raise ValueError('Matte is longer than source; timebase mismatch.')
    finally:
        cap.release();mc.release();proc.stdin.close();result=proc.wait();log.close()
    if result or not n or (info['frames'] is not None and n!=info['frames']):
        raise RuntimeError('Render or source frame count failed; inspect partial output and log.')
    rendered=inspect_video(temporary,fp)
    if rendered['frames'] != n:
        raise RuntimeError('Encoded frame count mismatch.')
    temporary.rename(out)
    report={'source':str(source),'output':str(out),'frames':n,'fps':str(fps),'duration':float(n/fps),
        'canvas':[width,height],'matte_source_verified':verified,'original_audio_stream_copy':info['audio'],
        'source_sha256':sha256(source),'font':str(font_path),'title_count':len(titles),'caption_count':len(captions),
        'note':'Encoding checks only. Final visual, privacy and listening review remain project QA.'}
    write_json(out.with_suffix('.render.json'),report)
    print(out,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    m=sub.add_parser('matte',help='Generate a lossless recurrent RVM alpha video.')
    m.add_argument('--input',required=True);m.add_argument('--model',required=True);m.add_argument('--output',required=True)
    m.add_argument('--width',type=int,default=960);m.add_argument('--downsample',type=float,default=.5)
    m.add_argument('--cuts',default='',help='Comma-separated zero-based scene cut frame indices.')
    r=sub.add_parser('render',help='Render an already edited clean video using a JSON style plan.')
    r.add_argument('--config',required=True);r.add_argument('--preset',default='fast');r.add_argument('--crf',type=int,default=17)
    for cmd in (m,r):
        cmd.add_argument('--ffmpeg',default='ffmpeg');cmd.add_argument('--ffprobe',default='ffprobe')
        cmd.add_argument('--threads',type=int,default=4)
    args=p.parse_args();cv2.setNumThreads(args.threads)
    if args.command=='matte':
        if args.width<16 or not 0<args.downsample<=1:raise ValueError('Invalid matte resolution or downsample ratio.')
        matte(args)
    else:render(args)


if __name__=='__main__':main()
