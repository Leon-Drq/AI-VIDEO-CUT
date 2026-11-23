"""SoloLoopCut: prepare sources, validate a semantic EDL, render and inspect MP4."""
from pathlib import Path
from fractions import Fraction
import argparse,hashlib,io,json,math,os,re,shutil,subprocess,sys

ROOT=Path(__file__).resolve().parents[1];ASSETS=ROOT/'assets'
MEDIA={'.mp4','.mov','.mkv','.m4v','.webm','.avi','.mts'}
SKIP={'对标','参考','reference','references','renders','render','成片','exports','segments','sources','tools'}

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,data):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def run(args):
    p=subprocess.run([str(x) for x in args],capture_output=True)
    if p.returncode:raise RuntimeError(p.stderr.decode('utf-8',errors='replace')[-5000:])
    return p.stdout
def find_tool(name,value=None):
    suffix='.exe' if os.name=='nt' else ''
    candidates=[value,os.environ.get('SOLOLOOP_'+name.upper()),shutil.which(name),f'D:/口播/tools/ffmpeg-full/ffmpeg-8.1.2-essentials_build/bin/{name}{suffix}']
    for x in candidates:
        if x and Path(x).is_file():return str(Path(x).resolve())
    raise FileNotFoundError(f'{name} missing; use --{name}, SOLOLOOP_{name.upper()} or PATH')
def tools(a):
    ff=find_tool('ffmpeg',a.ffmpeg);fp=a.ffprobe or str(Path(ff).with_name('ffprobe.exe' if Path(ff).suffix=='.exe' else 'ffprobe'))
    return ff,find_tool('ffprobe',fp)
def probe(p,fp):return json.loads(run([fp,'-v','error','-show_streams','-show_format','-of','json',p]))
def duration(e):return sum(c['frames'] for c in e['cuts'])/e.get('fps',30)
def source_map(p):return {s['id']:s for s in read(p/'source-inventory.json')}
def audio_metrics(ff,path):
    p=subprocess.run([ff,'-hide_banner','-i',str(path),'-af','loudnorm=I=-15:TP=-2:LRA=7:print_format=json','-vn','-f','null','-'],capture_output=True)
    if p.returncode:raise RuntimeError(p.stderr.decode('utf-8',errors='replace')[-2500:])
    match=re.search(r'\{\s*"input_i"[\s\S]*?\}',p.stderr.decode('utf-8',errors='replace'))
    if not match:raise RuntimeError('Audio loudness measurement unavailable')
    return json.loads(match.group())

def normalize_loudness(ff,source,dest):
    working=Path(source);dest=Path(dest);history=[]
    for attempt in range(2):
        m=audio_metrics(ff,working)
        if not all(math.isfinite(float(m[k])) for k in ['input_i','input_tp','input_lra','input_thresh','target_offset']):
            shutil.copyfile(working,dest);return {'status':'silent or unmeasurable','passes':history,'measurement':m}
        af=('loudnorm=I=-15:TP=-2:LRA=7:linear=true'
            f':measured_I={m["input_i"]}:measured_TP={m["input_tp"]}:measured_LRA={m["input_lra"]}'
            f':measured_thresh={m["input_thresh"]}:offset={m["target_offset"]}')
        stage=dest.with_name(dest.stem+f'.stage-{attempt+1}.wav')
        run([ff,'-y','-v','error','-i',working,'-af',af,'-ar','48000','-ac','2','-c:a','pcm_f32le',stage])
        actual=audio_metrics(ff,stage);history.append({'input':m,'actual_wav':actual});working=stage
        if -15.5<=float(actual['input_i'])<=-14.5 and float(actual['input_tp'])<=-1.7:break
    shutil.copyfile(working,dest);return {'status':'two-pass with measured output','passes':history,'aac_headroom_dbtp':-2}

def calibrate_encoded_audio(ff,video,mix):
    before=audio_metrics(ff,video);level,peak=float(before['input_i']),float(before['input_tp'])
    if not math.isfinite(level) or not math.isfinite(peak):return {'status':'silent','before':before}
    if -16<=level<=-14 and peak<=-1.3:return {'status':'within target','before':before}
    gain=min(-15-level,-1.7-peak);temp=Path(video).with_name(Path(video).stem+'.audio-check.mp4')
    run([ff,'-y','-v','error','-i',video,'-i',mix,'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','256k','-af',f'volume={gain}dB','-ar','48000','-ac','2','-map_metadata','-1','-movflags','+faststart',temp])
    after=audio_metrics(ff,temp);os.replace(temp,video)
    return {'status':'measured AAC correction, video copied','gain_db':gain,'before':before,'after':after}

def gather(inputs,project):
    result=[]
    for value in inputs:
        p=Path(value).resolve()
        if p.is_file():
            if p.suffix.lower() in MEDIA:result.append(p)
        elif p.is_dir():
            for base,dirs,files in os.walk(p):
                b=Path(base)
                if b==project or (b/'.sololoopcut-project').exists():dirs[:]=[];continue
                dirs[:]=[d for d in dirs if d.lower() not in SKIP and not d.startswith('.') and '成片工程' not in d and 'sololoopcut-' not in d.lower()]
                result.extend(b/f for f in sorted(files) if Path(f).suffix.lower() in MEDIA)
        else:raise FileNotFoundError(p)
    return list(dict.fromkeys(result))

def crop_box(s,c,w,h):
    sw,sh=s['display_width'],s['display_height']
    if 'crop' in c:return tuple(int(v)//2*2 for v in c['crop'])
    if c.get('fit','contain' if sw/sh>1.2 else 'cover')=='contain':return 0,0,sw,sh
    zoom=c.get('zoom',1.0) if min(sw,sh)>1080 else 1.0
    cw=min(sw,sh*w/h)/zoom;ch=cw*h/w;cw,ch=int(cw)//2*2,int(ch)//2*2
    fx,fy=c.get('focus',[.5,.58]);x=min(sw-cw,max(0,round(fx*sw-cw/2)));y=min(sh-ch,max(0,round(fy*sh-ch/2)))
    return x//2*2,y//2*2,cw,ch

def colour_filter(s,c,w,h):
    x,y,cw,ch=crop_box(s,c,w,h);contain=c.get('fit','contain' if s['display_width']/s['display_height']>1.2 else 'cover')=='contain'
    if contain:
        scale=min(w/cw,h/ch);ow=max(2,round(cw*scale)//2*2);oh=max(2,round(ch*scale)//2*2)
    else:ow,oh=w,h
    g=c.get('grade',{});hdr=s.get('color_transfer') in ['arib-std-b67','smpte2084'];parts=[f'crop={cw}:{ch}:{x}:{y}']
    if hdr:parts.extend([f'zscale=w={ow}:h={oh}:f=lanczos:t=linear:npl=100','format=gbrpf32le','zscale=p=bt709',f'tonemap=hable:desat={g.get("desat",0)}:peak={g.get("peak",10)}','zscale=t=bt709:m=bt709:r=tv:dither=error_diffusion','format=yuv444p10le'])
    else:parts.extend([f'scale={ow}:{oh}:flags=lanczos:out_color_matrix=bt709:out_range=tv','format=yuv444p10le'])
    sat=g.get('saturation',.95 if hdr else 1.0);gamma=g.get('gamma',1.02 if hdr else 1.0)
    if sat!=1 or gamma!=1:parts.append(f'eq=saturation={sat}:gamma={gamma}')
    sharp=g.get('sharpen',.25 if min(s['display_width'],s['display_height'])<=1080 else .15)
    if sharp:parts.append(f'unsharp=3:3:{sharp}:3:3:0')
    if contain:parts.append(f'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black')
    parts.extend(['setsar=1','setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709','format=yuv444p10le'])
    return ','.join(parts)

def prepare(a):
    ff,fp=tools(a);p=Path(a.project).resolve()
    if p.exists() and any(p.iterdir()):raise ValueError('Choose a new empty project; existing work is preserved')
    inputs=gather(a.inputs,p)
    if not inputs:raise ValueError('No input media found')
    p.mkdir(parents=True,exist_ok=True);(p/'.sololoopcut-project').write_text('SoloLoopCut\n',encoding='utf-8');inv=[]
    for i,path in enumerate(inputs,1):
        meta=probe(path,fp);v=next((s for s in meta['streams'] if s['codec_type']=='video'),None)
        if not v:continue
        audio=next((s for s in meta['streams'] if s['codec_type']=='audio'),None);rot=float(v.get('tags',{}).get('rotate',0))
        for side in v.get('side_data_list',[]):
            if 'rotation' in side:rot=float(side['rotation'])
        w,h=v['width'],v['height']
        if round(abs(rot))%180==90:w,h=h,w
        sid=f'source-{i:02d}';folder=p/'sources'/sid;folder.mkdir(parents=True);write(folder/'probe.json',meta)
        s={'id':sid,'path':str(path),'size_bytes':path.stat().st_size,'duration':float(v.get('duration',meta['format']['duration'])),'display_width':w,'display_height':h,'rotation':rot,'fps':v.get('avg_frame_rate',v.get('r_frame_rate')),'pix_fmt':v.get('pix_fmt'),'color_transfer':v.get('color_transfer'),'color_primaries':v.get('color_primaries'),'color_space':v.get('color_space'),'color_range':v.get('color_range'),'has_audio':bool(audio),'audio_start':float(audio.get('start_time',0)) if audio else None,'side_data':v.get('side_data_list',[])}
        inv.append(s)
        if audio:run([ff,'-y','-v','error','-i',path,'-vn','-af','aresample=async=1:first_pts=0','-ar','48000','-ac','2','-c:a','pcm_f32le',folder/'audio.wav'])
        if not a.skip_previews:
            for n,ratio in enumerate([.05,.35,.65,.9]):run([ff,'-y','-v','error','-ss',max(0,min(s['duration']-.1,s['duration']*ratio)),'-i',path,'-vf',colour_filter(s,{'fit':'contain'},540,720),'-frames:v','1',folder/f'preview-{n}.jpg'])
        print(f"prepared {sid}: {w}x{h} {s['duration']:.2f}s {s['color_transfer']}",flush=True)
    if not inv:raise ValueError('No video streams')
    write(p/'source-inventory.json',inv);write(p/'edit.json',{'name':'SoloLoopCut','width':1080,'height':1440,'fps':30,'version':1,'music':True,'cuts':[],'captions':[],'elements':[],'topics':[],'chapters':[]})
    write(p/'project.json',{'skill':'sololoopcut','sources':[x['path'] for x in inv],'target_seconds':45,'status':'awaiting semantic EDL'})
    print('Project ready; editor must fill edit.json from viewed footage and verified transcripts:',p,flush=True)

def validate(p):
    from overlay import Graphics
    e=read(p/'edit.json');sources=source_map(p);errors=[];warnings=[];w,h,fps=e.get('width',1080),e.get('height',1440),e.get('fps',30)
    if not e.get('cuts'):errors.append('No cuts: create a semantic EDL')
    if min(w,h,fps)<=0 or w%2 or h%2:errors.append('Invalid even canvas/frame rate')
    for i,c in enumerate(e.get('cuts',[])):
        s=sources.get(c.get('source_id'))
        if not s:errors.append(f'cut {i}: unknown source');continue
        if not Path(s['path']).is_file():errors.append(f'cut {i}: source file missing')
        n=c.get('frames',0);start=c.get('source_in',-1)
        if not isinstance(n,int) or n<=0:errors.append(f'cut {i}: frames must be positive integer');continue
        if start<0 or start+n/fps>s['duration']+.035:errors.append(f'cut {i}: source interval out of range')
        if c.get('voice',True) and not s['has_audio']:errors.append(f'cut {i}: voice requested without audio')
        if c.get('zoom',1)>1 and min(s['display_width'],s['display_height'])<=1080:warnings.append(f'cut {i}: 1080p digital zoom ignored')
        if s.get('color_transfer')=='smpte2084' and c.get('grade',{}).get('peak') is None:errors.append(f'cut {i}: verify PQ peak explicitly')
        x,y,cw,ch=crop_box(s,c,w,h)
        if min(x,y)<0 or min(cw,ch)<2 or x+cw>s['display_width'] or y+ch>s['display_height']:errors.append(f'cut {i}: invalid crop')
        elif 'crop' in c and c.get('fit','cover')=='cover' and abs(cw/ch-w/h)>.003:errors.append(f'cut {i}: crop aspect would distort subjects')
        if not s.get('color_transfer') or not s.get('color_primaries'):warnings.append(f'cut {i}: incomplete colour metadata; inspect SDR/709 interpretation')
    if errors:return e,sources,errors,warnings
    dur=duration(e);g=Graphics(e,read(ASSETS/'style.json'),ASSETS,dur)
    for kind in ['captions','elements','topics','chapters']:
        for obj in e.get(kind,[]):
            if not 0<=obj.get('start',-1)<obj.get('end',0)<=dur+.001:errors.append(f'{kind}: invalid time interval')
            if kind=='captions':
                try:g.wrap_caption(obj['text'])
                except ValueError as ex:errors.append(str(ex))
    last=0
    for c in e.get('chapters',[]):
        if c['start']<last-.001:errors.append('chapters overlap or are unordered')
        last=c['end']
    for el in e.get('elements',[]):
        x,y=el.get('x',62),el.get('y',720)
        if x<0 or y<57 or x>=1080 or y>=1360:errors.append('graphic outside safe canvas')
        if el.get('type')=='card' and (x+el.get('width',580)>1040 or y+el.get('height',138)>1050):errors.append('card outside safe area/caption zone')
    for key in ['audio_from','music_file','logo']:
        if e.get(key) and not Path(e[key]).is_file():errors.append(key+' file missing')
    if not e.get('captions'):warnings.append('No captions; verify intentional')
    if any(s.get('color_transfer') in ['arib-std-b67','smpte2084'] for s in sources.values()):warnings.append('Inspect encoded HDR highlights and skin; default mapping is a starting point')
    return e,sources,errors,warnings

def concat_file(path,files,durations=None):
    lines=['ffconcat version 1.0']
    for i,p in enumerate(files):
        name=str(Path(p).resolve()).replace('\\','/').replace("'","'\\''");lines.append("file '"+name+"'")
        if durations is not None:lines.append(f'duration {durations[i]:.12f}')
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')

def render(a):
    from overlay import Graphics
    ff,fp=tools(a);p=Path(a.project).resolve();e,sources,errors,warnings=validate(p)
    if errors:raise ValueError('\n'.join(errors))
    fps=e.get('fps',30);w,h=e.get('width',1080),e.get('height',1440);dur=duration(e);n=sum(c['frames'] for c in e['cuts'])
    seg,audio,out=p/'segments',p/'audio',p/'renders'
    for d in [seg,audio,out]:d.mkdir(parents=True,exist_ok=True)
    videos=[];voices=[];durations=[]
    for i,c in enumerate(e['cuts']):
        s=sources[c['source_id']];length=c['frames']/fps;start=c['source_in'];dest=seg/f'{i:03d}.mkv'
        vf=colour_filter(s,c,w,h)+f',fps={fps},setpts=N/({fps}*TB)'
        run([ff,'-y','-v','error','-threads','3','-ss',start,'-i',s['path'],'-an','-vf',vf,'-frames:v',c['frames'],'-c:v','ffv1','-level','3','-g','1','-slicecrc','1','-threads','3','-pix_fmt','yuv444p10le','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-color_range','tv','-map_metadata','-1',dest])
        videos.append(dest);durations.append(length)
        if not e.get('audio_from'):
            wav=audio/f'{i:03d}.wav'
            if c.get('voice',True):
                src=p/'sources'/s['id']/'audio.wav'
                if not src.is_file():raise FileNotFoundError('Prepare audio first: '+str(src))
                run([ff,'-y','-v','error','-ss',start,'-i',src,'-t',length,'-af',f'atrim=duration={length},asetpts=PTS-STARTPTS,volume={c.get("gain_db",0)}dB,afade=t=in:d=0.005,afade=t=out:st={max(0,length-.008)}:d=0.008','-ar','48000','-ac','2','-c:a','pcm_f32le',wav])
            else:run([ff,'-y','-v','error','-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t',length,'-c:a','pcm_f32le',wav])
            voices.append(wav)
        print(f'rendered cut {i+1}/{len(e["cuts"])}',flush=True)
    vc=p/'picture.ffconcat';concat_file(vc,videos,durations);copy_audio=bool(e.get('audio_from'))
    if copy_audio:
        mix=Path(e['audio_from']);old=probe(mix,fp)
        if not any(s['codec_type']=='audio' for s in old['streams']):raise ValueError('audio_from has no audio')
        if abs(float(old['format']['duration'])-dur)>.08:raise ValueError('audio_from must preserve the audio timeline and duration')
    else:
        ac=p/'voice.ffconcat';concat_file(ac,voices);voice=audio/'dialogue.wav'
        run([ff,'-y','-v','error','-f','concat','-safe','0','-i',ac,'-af','highpass=f=80,acompressor=threshold=0.14:ratio=2:attack=8:release=120:makeup=1','-t',dur,'-ar','48000','-ac','2','-c:a','pcm_f32le',voice])
        mix=audio/'mix.wav';pre=audio/'premaster.wav'
        if e.get('music',True):
            score=Path(e['music_file']).resolve() if e.get('music_file') else audio/'score.wav'
            if not e.get('music_file'):run([sys.executable,ROOT/'scripts/score.py','--duration',dur,'--out',score])
            graph=f'[0:a]asplit[d][key];[1:a]volume={e.get("music_gain",.24)},afade=t=in:d=0.3,afade=t=out:st={max(0,dur-1)}:d=1[m];[m][key]sidechaincompress=threshold=0.025:ratio=8:attack=8:release=220[duck];[d][duck]amix=inputs=2:normalize=0[a]'
            run([ff,'-y','-v','error','-i',voice,'-stream_loop','-1','-i',score,'-filter_complex',graph,'-map','[a]','-t',dur,'-ar','48000','-ac','2','-c:a','pcm_f32le',pre])
        else:shutil.copyfile(voice,pre)
        write(audio/'normalization.json',normalize_loudness(ff,pre,mix))
    version=e.get('version',1);dest=out/f'SoloLoopCut-v{version}.mp4'
    while dest.exists():version+=1;dest=out/f'SoloLoopCut-v{version}.mp4'
    g=Graphics(e,read(ASSETS/'style.json'),ASSETS,dur);log=p/'render.log'
    args=[ff,'-y','-hide_banner','-loglevel','warning','-threads','4','-f','concat','-safe','0','-i',str(vc),'-f','rawvideo','-pixel_format','rgba','-video_size',f'{w}x{h}','-framerate',str(fps),'-i','pipe:0','-i',str(mix),'-filter_complex',f'[0:v]settb=1/{fps},setpts=N[base];[base][1:v]overlay=0:0:shortest=1:format=auto,scale=out_color_matrix=bt709:out_range=tv,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709,format=yuv420p[v]','-map','[v]','-map','2:a:0','-c:v','libx264','-preset',e.get('preset','slow'),'-crf',str(e.get('crf',16)),'-threads','6','-pix_fmt','yuv420p','-profile:v','high','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-color_range','tv']
    args+=['-c:a','copy'] if copy_audio else ['-c:a','aac','-b:a','256k','-ar','48000','-ac','2']
    args+=['-frames:v',str(n),'-r',str(fps),'-fps_mode','cfr','-map_metadata','-1','-movflags','+faststart',str(dest)]
    with log.open('wb') as f:
        proc=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=f)
        try:
            for i in range(n):
                proc.stdin.write(g.at(i/fps).tobytes())
                if i%150==0:print(f'composite {i}/{n}',flush=True)
            proc.stdin.close();rc=proc.wait()
        except Exception:proc.kill();raise
    if rc:raise RuntimeError(log.read_text(errors='replace')[-5000:])
    if not copy_audio:write(audio/'post-encode-check.json',calibrate_encoded_audio(ff,dest,mix))
    def stamp(t):
        ms=round(t*1000);hh,ms=divmod(ms,3600000);mm,ms=divmod(ms,60000);ss,ms=divmod(ms,1000);return f'{hh:02}:{mm:02}:{ss:02},{ms:03}'
    (p/'captions.srt').write_text('\n\n'.join(f'{i}\n{stamp(c["start"])} --> {stamp(c["end"])}\n{c["text"]}' for i,c in enumerate(e.get('captions',[]),1))+'\n',encoding='utf-8')
    write(p/'render-result.json',{'file':str(dest),'duration':dur,'frames':n,'version':version,'warnings':warnings,'audio_copied':copy_audio})
    print(json.dumps({'final':str(dest),'duration':dur,'frames':n},ensure_ascii=False),flush=True)

def qa(a):
    from PIL import Image,ImageDraw,ImageFont
    ff,fp=tools(a);p=Path(a.project).resolve();r=read(p/'render-result.json');dest=Path(r['file']);e,_,errors,warnings=validate(p)
    info=probe(dest,fp);v=next(s for s in info['streams'] if s['codec_type']=='video');audio=next((s for s in info['streams'] if s['codec_type']=='audio'),None)
    if (v['width'],v['height'])!=(e.get('width',1080),e.get('height',1440)):errors.append('wrong canvas')
    if int(v.get('nb_frames',0))!=r['frames']:errors.append('wrong frame count')
    if abs(float(Fraction(v['r_frame_rate']))-e.get('fps',30))>.001:errors.append('wrong fps')
    if abs(float(info['format']['duration'])-duration(e))>.08:errors.append('wrong duration')
    if any(v.get(k)!='bt709' for k in ['color_space','color_transfer','color_primaries']) or v.get('color_range')!='tv':errors.append('wrong colour tags/range')
    if not audio:errors.append('missing audio')
    try:run([ff,'-v','error','-i',dest,'-f','null','-'])
    except RuntimeError as ex:errors.append('decode failed: '+str(ex))
    scan=subprocess.run([ff,'-hide_banner','-i',str(dest),'-vf','blackdetect=d=0.1:pix_th=0.1,freezedetect=n=-50dB:d=1.5','-an','-f','null','-'],capture_output=True)
    candidates=[x for x in scan.stderr.decode('utf-8',errors='replace').splitlines() if 'black_start:' in x or 'freeze_start:' in x];metrics=audio_metrics(ff,dest)
    if not -16<=float(metrics['input_i'])<=-14:warnings.append('loudness outside target')
    if float(metrics['input_tp'])>-1.3:warnings.append('true peak above -1.3 dBTP')
    if e.get('audio_from'):
        def ah(f):return run([ff,'-v','error','-i',f,'-map','0:a:0','-c:a','copy','-f','hash','-hash','sha256','pipe:1'])
        if ah(e['audio_from'])!=ah(dest):errors.append('copied audio packet hash differs')
    out=p/'qa';out.mkdir(exist_ok=True);write(out/'probe.json',info);end=duration(e);fps=e.get('fps',30)
    ts={max(0,min(end-1/fps,t)) for t in [0,.4,.8,1.5,2.8,end-3,end-2,end-1,end-.1]};pos=0
    for c in e['cuts']:
        for dt in [-1/fps,0,.1]:ts.add(max(0,min(end-1/fps,pos+dt)))
        ts.add(pos+c['frames']/fps/2);pos+=c['frames']/fps
    for key in ['elements','captions']:
        for item in e.get(key,[]):ts.add((item['start']+item['end'])/2)
    ts=sorted(ts);thumbs=[]
    for t in ts:
        data=run([ff,'-v','error','-ss',t,'-i',dest,'-frames:v','1','-vf','scale=216:288','-f','image2pipe','-c:v','mjpeg','pipe:1'])
        thumbs.append(Image.open(io.BytesIO(data)).convert('RGB'))
    font=ImageFont.load_default()
    for page in range(math.ceil(len(ts)/24)):
        chunk=list(zip(ts,thumbs))[page*24:(page+1)*24];sheet=Image.new('RGB',(1296,math.ceil(len(chunk)/6)*312),'#111111');d=ImageDraw.Draw(sheet)
        for i,(t,im) in enumerate(chunk):
            x,y=i%6*216,i//6*312;sheet.paste(im,(x,y+24));d.text((x+4,y+3),f'{t:.3f}s',font=font,fill='white')
        sheet.save(out/f'contact-{page+1}.jpg',quality=93)
    report={'technical_status':'FAIL' if errors else 'PASS','errors':errors,'warnings':warnings,'picture_candidates':candidates,'loudness':metrics,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'file':str(dest),'manual_status':'REQUIRED: inspect encoded frames, facts, caption timing and audio when audition is available. This script does not claim human playback.'}
    write(out/'qa.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)
    if errors:raise SystemExit(1)

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    for name in ['prepare','validate','render','qa']:
        q=sub.add_parser(name);q.add_argument('--ffmpeg');q.add_argument('--ffprobe')
        if name=='prepare':q.add_argument('inputs',nargs='+');q.add_argument('--project',required=True);q.add_argument('--skip-previews',action='store_true')
        else:q.add_argument('project')
    a=p.parse_args()
    if a.command=='prepare':prepare(a)
    elif a.command=='validate':
        e,_,errors,warnings=validate(Path(a.project).resolve());print(json.dumps({'errors':errors,'warnings':warnings,'duration':duration(e) if e.get('cuts') and not errors else None},ensure_ascii=False));raise SystemExit(bool(errors))
    elif a.command=='render':render(a)
    else:qa(a)

if __name__=='__main__':main()
