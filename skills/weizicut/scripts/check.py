"""Review the actual encoded export: mobile frames, stream timing and sound/black alerts."""
import argparse
import json
from pathlib import Path
import re
import subprocess

import cv2
from PIL import Image, ImageDraw
from lock_cut import probe


def inspect(args):
    path = Path(args.video).resolve(strict=True)
    info = probe(path,args.ffprobe)["streams"]
    video,audio = (next(s for s in info if s["codec_type"]==k) for k in ("video","audio"))
    frames = int(video["nb_frames"])
    duration = float(video["duration"])
    if (video["width"],video["height"],video["r_frame_rate"])!=(1080,1920,"30/1"):
        raise ValueError("Unexpected frame size or frame rate")
    if abs(float(audio["duration"])-duration)>1/30:
        raise ValueError("Voice and picture have different durations")
    proc = subprocess.run([args.ffmpeg,"-hide_banner","-nostats","-xerror","-i",str(path),
                           "-vf","blackdetect=d=0.20:pix_th=0.06",
                           "-af","silencedetect=n=-45dB:d=0.7,ebur128=peak=true","-f","null","-"],
                          check=True,capture_output=True)
    log = proc.stderr.decode("utf-8",errors="replace")
    alerts = [s.strip() for s in log.splitlines() if re.search("black_start:|silence_start:",s)]
    regular = [duration*i/8 for i in range(8)]
    points = sorted(set(min(frames-1,round(t*30)) for t in [0,.17,.5,1.5,2.5,*regular,*args.at,duration]))
    cap = cv2.VideoCapture(str(path))
    sheet = Image.new("RGB",(216*4,410*((len(points)+3)//4)),"#17191A")
    draw = ImageDraw.Draw(sheet)
    try:
        for i,n in enumerate(points):
            cap.set(cv2.CAP_PROP_POS_FRAMES,n)
            ok,bgr = cap.read()
            if not ok:
                raise ValueError(f"Preview decode failed at frame {n}")
            thumb = cv2.resize(bgr,(216,384),interpolation=cv2.INTER_AREA)
            x,y = i%4*216,i//4*410
            sheet.paste(Image.fromarray(cv2.cvtColor(thumb,cv2.COLOR_BGR2RGB)),(x,y))
            draw.text((x+5,y+388),f"{n/30:.2f}s",fill="white")
    finally:
        cap.release()
    folder = Path(args.out)
    folder.mkdir(parents=True,exist_ok=False)
    sheet.save(folder/"contact.jpg",quality=93)
    (folder/"sound-and-picture.json").write_text(json.dumps({
        "frames":frames,"seconds":duration,"checked_frames":points,"review_alerts":alerts,
        "loudness":log.rsplit("Summary:",1)[-1].split("[out#")[0].strip()
    },ensure_ascii=False,indent=2),"utf-8")


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video")
    parser.add_argument("--at",nargs="*",type=float,default=[])
    parser.add_argument("--out",required=True)
    parser.add_argument("--ffmpeg",default="ffmpeg")
    parser.add_argument("--ffprobe",default="ffprobe")
    inspect(parser.parse_args())
