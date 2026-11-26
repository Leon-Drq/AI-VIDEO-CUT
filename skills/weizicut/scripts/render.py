"""Render one locked, editorially prepared weizicut project to MP4 and SRT."""
import argparse
from contextlib import ExitStack
from functools import lru_cache
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile

import cv2
from PIL import Image, ImageDraw, ImageFont, ImageOps
from lock_cut import probe
from visuals import SIZE, WHITE, GOLD, LANCZOS, backdrop, crop_fraction, draw_host, ease, mount

FPS = 30


class Video:
    def __init__(self, path):
        self.cap = cv2.VideoCapture(str(path))
        if not self.cap.isOpened():
            raise ValueError(f"Unreadable video: {path}")
        self.path = path
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.count = round(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.index = -1
        self.last = None

    def get(self, n):
        if n < 0 or n >= self.count:
            raise ValueError(f"Missing frame {n} of {self.path.name}")
        if n == self.index:
            return self.last
        if n != self.index+1:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, n)
        ok, bgr = self.cap.read()
        if not ok:
            raise ValueError(f"Decode failed at frame {n} of {self.path.name}")
        self.index = n
        self.last = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        return self.last


def intervals(rows, duration, label, exclusive=False):
    previous = 0
    for row in rows:
        start, end = row["start"], row["end"]
        if not (0 <= start < end <= duration+.0001) or (exclusive and start < previous):
            raise ValueError(f"Invalid or overlapping {label} interval: {start}, {end}")
        previous = end


def rect_at(row, t, default):
    rect = row.get("box", default)
    last = row["start"]
    for at, target in row.get("moves", []):
        if at <= last or at > row["end"]:
            raise ValueError("Box movement times must increase, inside the shot")
        if t < at:
            p = ease((t-last)/(at-last))
            return [round(a+(b-a)*p) for a,b in zip(rect,target)]
        rect, last = target, at
    return list(rect)


@lru_cache(maxsize=80)
def font(path, size):
    return ImageFont.truetype(path, size)


def fit_font(path, text, initial, width):
    f = font(path, initial)
    size = initial
    while f.getlength(text)>width and size>20:
        size -= 2
        f = font(path, size)
    return f


def subtitles(image, row, font_path):
    draw = ImageDraw.Draw(image)
    lines = row["text"].splitlines()
    if not lines or len(lines)>2:
        raise ValueError("Split captions into one or two editorial lines")
    f = fit_font(font_path, max(lines, key=lambda s: font(font_path,64).getlength(s)), 64, 930)
    if f.size < 46:
        raise ValueError(f"Caption too dense for mobile: {row['text']}")
    highlight = row.get("highlight", "")
    if highlight and not any(highlight in line for line in lines):
        raise ValueError(f"Highlight must occur in one caption line: {highlight}")
    y = 1640 if len(lines)==1 else 1580
    for line in lines:
        x = (SIZE[0]-f.getlength(line))/2
        draw.text((x,y), line, font=f, fill=WHITE, stroke_width=3, stroke_fill="#26221E")
        if highlight in line and highlight:
            pre = line.split(highlight,1)[0]
            draw.text((x+f.getlength(pre),y), highlight, font=f, fill=GOLD, stroke_width=3, stroke_fill="#26221E")
        y += 78


def timecode(value):
    n = round(value*1000)
    return f"{n//3600000:02}:{n//60000%60:02}:{n//1000%60:02},{n%1000:03}"


class Project:
    def __init__(self, config, stack):
        self.folder = config.parent
        self.data = json.loads(config.read_text("utf-8-sig"))
        self.stack = stack
        self.videos = {}
        self.source = self.video(self.data["presenter"])
        self.mask = self.video(self.data["matte"])
        if any(abs(v.fps-FPS)>.001 for v in (self.source,self.mask)) or self.source.count != self.mask.count:
            raise ValueError("Use a 30 fps cut and a matte made from that exact cut")
        for v in (self.source,self.mask):
            w,h = (v.cap.get(k) for k in (cv2.CAP_PROP_FRAME_WIDTH,cv2.CAP_PROP_FRAME_HEIGHT))
            if abs(w/h-9/16)>.003:
                raise ValueError("Prepare a 9:16 presenter and identically framed matte")
        self.duration = self.source.count/FPS
        self.face = self.data["face_roi"]
        self.font = str(self.path(self.data["font"]))
        self.scenes = self.data["scenes"]
        self.items = self.data["materials"]
        self.caps = self.data["captions"]
        for rows,label,exclusive in [(self.scenes,"scene",True),(self.caps,"caption",True),(self.items,"material",False)]:
            intervals(rows,self.duration,label,exclusive)
        for item in self.items:
            covered = item["start"]
            for scene in self.scenes:
                if scene["start"] <= covered < scene["end"]:
                    covered = scene["end"]
                if covered >= item["end"]:
                    break
            if covered < item["end"]:
                raise ValueError(f"Material falls outside its composed scenes: {item['file']}")
        if not self.caps:
            raise ValueError("Supply proofread captions for this talking head")
        self.stills = {}

    def path(self, name):
        return (self.folder / name).resolve(strict=True)

    def video(self, name):
        path = self.path(name)
        if path not in self.videos:
            self.videos[path] = Video(path)
            self.stack.callback(self.videos[path].cap.release)
        return self.videos[path]

    def material(self, canvas, row, t):
        path = self.path(row["file"])
        if row.get("video", False):
            clip = self.video(row["file"])
            frame = math.floor(((t-row["start"])+row.get("offset",0))*clip.fps+1e-6)
            image = clip.get(frame)
        else:
            if path not in self.stills:
                with Image.open(path) as source:
                    self.stills[path] = ImageOps.exif_transpose(source).convert("RGB")
            image = self.stills[path]
        crop = row.get("crop", [0,0,1,1])
        if "detail" in row:
            at, settled, target = row["detail"]
            if not row["start"] <= at < settled <= row["end"]:
                raise ValueError("Detail movement must fit inside the material interval")
            p = ease((t-at)/(settled-at))
            crop = [a+(b-a)*p for a,b in zip(crop,target)]
        if crop != [0,0,1,1]:
            image = crop_fraction(image, crop)
        x,y,w,h = rect_at(row,t,[56,560,968,870])
        if row.get("full_bleed"):
            canvas.paste(ImageOps.fit(image,(w,h),LANCZOS), (x,y))
            return
        image = ImageOps.contain(image,(w,h),LANCZOS)
        card, lift = mount(image, row["kind"], t-row["start"])
        canvas.paste(card,(round(x+(w-card.width)/2),round(y+(h-card.height)/2+lift)),card)
        if row.get("credit") and t-row["start"] >= .20:
            text = row["credit"]
            pos = row.get("credit_xy", [x, y+h+20])
            ImageDraw.Draw(canvas).text(tuple(pos),text,font=fit_font(self.font,text,39,min(w,1000)),
                                        fill="#DFDBD1",stroke_width=1,stroke_fill="#1C2022")

    def frame(self, n):
        t = n/FPS
        frame = self.source.get(n)
        active = next((s for s in self.scenes if s["start"]<=t<s["end"]), None)
        if active is None:
            canvas = frame.copy()
        else:
            canvas = backdrop(t)
            mode = active["host"]
            for item in self.items:
                if item["start"]<=t<item["end"]:
                    self.material(canvas,item,t)
            heading = active.get("title",[])
            for i, line in enumerate(heading):
                size = 236 if mode=="large" else 124
                limit = 990 if mode=="large" else (920 if mode=="sticker" else 715)
                f = fit_font(self.font,line,size,limit)
                x = (1080-f.getlength(line))//2 if mode=="large" else 56
                y = (288 if len(heading)==1 else 155) if mode=="large" else 112
                ImageDraw.Draw(canvas).text((x,y+i*144),line,font=f,fill=WHITE if i==0 else GOLD)
            default_box = {"pip":[795,126,224,224],"sticker":[435,720,645,1200],"large":[0,0,*SIZE]}[mode]
            x,y,w,h = rect_at(active,t,default_box)
            if "push_at" in active:
                p = ease((t-active["push_at"])/.30)
                z = 1+.055*p
                x,y,w,h = round(x+(1-z)*w*.5),round(y+(1-z)*h*.29),round(w*z),round(h*z)
            mask = self.mask.get(n).convert("L")
            roi = active.get("roi", self.face if mode=="pip" else [0,0,1,1])
            draw_host(canvas,frame,mask,mode,[x,y,w,h],roi,t-active["start"])
        cue = next((s for s in self.caps if s["start"]<=t<s["end"]),None)
        if cue:
            subtitles(canvas,cue,self.font)
        return canvas


def voice_chain(project, program):
    # Measure the actual recording after channel conversion. This keeps quiet new speakers intelligible
    # without bringing the separately calibrated paper sounds up by the same amount.
    base = ("aresample=48000,aformat=channel_layouts=stereo,highpass=f=65,"
            "acompressor=threshold=0.12:ratio=2.5:attack=8:release=90")
    target = "loudnorm=I=-15:LRA=9:TP=-2"
    measure = subprocess.run([program,"-hide_banner","-nostats","-i",str(project.source.path),"-vn",
                              "-af",base+","+target+":print_format=json","-f","null","-"],
                             check=True,capture_output=True)
    report = re.search(r'\{\s*"input_i"[^}]+\}',measure.stderr.decode("utf-8",errors="replace"))
    if not report:
        raise ValueError("Unable to measure the narration")
    values = json.loads(report.group())
    if not math.isfinite(float(values["input_i"])):
        raise ValueError("No measurable narration: check the locked voice track")
    return (base+","+target+f":measured_I={values['input_i']}:measured_TP={values['input_tp']}"
            f":measured_LRA={values['input_lra']}:measured_thresh={values['input_thresh']}"
            f":offset={values['target_offset']}:linear=true,aresample=48000")


def mix(project, silent, result, program):
    cmd = [program,"-v","error","-nostdin","-i",str(silent),"-i",str(project.source.path)]
    filters = ["[1:a:0]"+voice_chain(project,program)+"[voice]"]
    sources = ["[voice]"]
    for i,s in enumerate(project.data.get("sounds", [])):
        at = s["at"]
        length = s["duration"]
        if not 0<=at<project.duration or length<=0 or s.get("offset",0)<0:
            raise ValueError(f"Invalid sound at {at}")
        cmd.extend(["-i",str(project.path(s["file"]))])
        delay = round(at*48000)
        length = min(length, project.duration-at)
        filters.append(f"[{i+2}:a]atrim=start={s.get('offset',0)}:duration={length},asetpts=PTS-STARTPTS,"
                       f"aresample=48000,aformat=channel_layouts=stereo,volume={s['gain_db']}dB,"
                       f"afade=t=in:d=0.006,afade=t=out:st={max(0,length-.015)}:d=0.015,"
                       f"adelay={delay}S:all=1[fx{i}]")
        sources.append(f"[fx{i}]")
    filters.append("".join(sources)+f"amix=inputs={len(sources)}:duration=first:normalize=0,"
                   "alimiter=limit=0.85:level=0:latency=1[out]")
    subprocess.run(cmd+["-filter_complex",";".join(filters),"-map","0:v:0","-map","[out]","-t",str(project.duration),
                        "-c:v","copy","-c:a","aac","-b:a","256k","-movflags","+faststart",str(result)],check=True)


def render(args):
    output = Path(args.out).resolve()
    if output.exists():
        raise FileExistsError(f"Choose a new delivery folder: {output}")
    output.parent.mkdir(parents=True,exist_ok=True)
    with ExitStack() as stack, tempfile.TemporaryDirectory(dir=output.parent) as stage:
        project = Project(Path(args.project).resolve(strict=True),stack)
        temp = Path(stage)
        delivery = temp/"delivery"
        delivery.mkdir()
        silent = temp/"picture.mp4"
        cmd = [args.ffmpeg,"-v","error","-f","rawvideo","-pix_fmt","rgb24","-s","1080x1920","-r","30",
               "-i","pipe:0","-an","-vf","scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
               "-c:v","libx264","-threads","6","-preset","veryfast","-crf","17","-colorspace","bt709",
               "-color_primaries","bt709","-color_trc","bt709",str(silent)]
        with subprocess.Popen(cmd,stdin=subprocess.PIPE) as pipe:
            try:
                for n in range(project.source.count):
                    pipe.stdin.write(project.frame(n).tobytes())
            finally:
                pipe.stdin.close()
            if pipe.wait():
                raise RuntimeError("Picture encode failed")
        movie = delivery/"成片.mp4"
        mix(project,silent,movie,args.ffmpeg)
        ss = probe(movie,args.ffprobe)["streams"]
        v,a = (next(s for s in ss if s["codec_type"]==k) for k in ("video","audio"))
        if int(v["nb_frames"])!=project.source.count or abs(float(v["duration"])-float(a["duration"]))>1/FPS:
            raise ValueError("Exported tracks disagree with locked edit")
        subprocess.run([args.ffmpeg,"-v","error","-xerror","-i",str(movie),"-f","null","-"],check=True)
        rows = [f"{i}\n{timecode(c['start'])} --> {timecode(c['end'])}\n{c['text']}" for i,c in enumerate(project.caps,1)]
        (delivery/"字幕.srt").write_text("\n\n".join(rows)+"\n","utf-8-sig")
        delivery.rename(output)


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("--out",required=True)
    parser.add_argument("--ffmpeg",default="ffmpeg")
    parser.add_argument("--ffprobe",default="ffprobe")
    cv2.setNumThreads(3)
    render(parser.parse_args())
