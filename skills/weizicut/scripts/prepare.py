"""Local Mandarin word timing and recurrent presenter matting for a locked edit."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile


def transcript(args, destination):
    from faster_whisper import WhisperModel
    model = WhisperModel(str(Path(args.model).resolve(strict=True)), device=args.device,
                         compute_type="float16" if args.device=="cuda" else "int8")
    segments, _ = model.transcribe(str(args.input), language="zh", word_timestamps=True, vad_filter=False)
    rows = [dict(start=s.start,end=s.end,text=s.text,words=[
        dict(start=w.start,end=w.end,text=w.word) for w in (s.words or [])]) for s in segments]
    if not rows:
        raise ValueError("No voice segments were transcribed")
    destination.write_text(json.dumps(rows,ensure_ascii=False,indent=2), "utf-8")


def matte(args, destination):
    import cv2
    import numpy as np
    import onnxruntime as ort

    cut = json.loads(Path(args.cut_map).read_text("utf-8-sig"))
    resets = {item["first_frame"] for item in cut["keep"]}
    cap = cv2.VideoCapture(str(args.input))
    try:
        total = round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if cut["fps"]!=30 or total!=cut["frames"] or abs(cap.get(cv2.CAP_PROP_FPS)-30)>.001:
            raise ValueError("Use the matching locked presenter and cut map")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        session = ort.InferenceSession(str(Path(args.model).resolve(strict=True)),options,
                                       providers=["CPUExecutionProvider"])
        width = 720
        height = round(width*cap.get(cv2.CAP_PROP_FRAME_HEIGHT)/cap.get(cv2.CAP_PROP_FRAME_WIDTH)/2)*2
        cmd = [args.ffmpeg,"-v","error","-f","rawvideo","-pixel_format","gray","-video_size",f"{width}x{height}",
               "-framerate","30","-i","pipe:0","-c:v","ffv1","-pix_fmt","gray",str(destination)]
        with subprocess.Popen(cmd,stdin=subprocess.PIPE) as pipe:
            try:
                for n in range(total):
                    ok, frame = cap.read()
                    if not ok:
                        raise ValueError(f"Missing presenter frame {n}")
                    if n==0 or n in resets:
                        memory = [np.zeros((1,1,1,1),np.float32) for _ in range(4)]
                    rgb = cv2.cvtColor(cv2.resize(frame,(width,height),interpolation=cv2.INTER_AREA),cv2.COLOR_BGR2RGB)
                    feed = {f"r{i+1}i":v for i,v in enumerate(memory)}
                    feed.update(src=rgb.transpose(2,0,1)[None].astype(np.float32)/255,
                                downsample_ratio=np.array([.5],np.float32))
                    _,alpha,*memory = session.run(None,feed)
                    if alpha.shape != (1,1,height,width) or len(memory)!=4:
                        raise ValueError("Expected a recurrent RVM six-output model")
                    pipe.stdin.write(np.uint8(np.clip(alpha[0,0]*255,0,255)).tobytes())
            finally:
                pipe.stdin.close()
            if pipe.wait():
                raise RuntimeError("Matte encoding failed")
    finally:
        cap.release()


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action",required=True)
    speech = commands.add_parser("transcribe")
    speech.add_argument("--device",choices=["cpu","cuda"],default="cpu")
    person = commands.add_parser("matte")
    person.add_argument("--cut-map",required=True)
    person.add_argument("--ffmpeg",default="ffmpeg")
    for command in (speech,person):
        command.add_argument("--input",type=Path,required=True)
        command.add_argument("--model",required=True)
        command.add_argument("--out",type=Path,required=True)
    args = parser.parse_args()
    suffix = ".mkv" if args.action=="matte" else ".json"
    if args.out.suffix.lower()!=suffix or args.out.exists():
        raise ValueError(f"Choose a new output with suffix {suffix}")
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.out.parent) as staging:
        temp = Path(staging)/("prepared"+suffix)
        (matte if args.action=="matte" else transcript)(args,temp)
        temp.rename(args.out)
