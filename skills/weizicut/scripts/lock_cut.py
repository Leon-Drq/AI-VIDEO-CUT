"""Lock voice, picture and an edit map to a common 30 fps clock."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import tempfile


def probe(path, program):
    return json.loads(subprocess.check_output([
        program, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)
    ]))


def lock(args):
    source = Path(args.source).resolve(strict=True)
    output = Path(args.out).resolve()
    if output.exists():
        raise FileExistsError(f"Choose a new output folder: {output}")
    streams = probe(source, args.ffprobe)["streams"]
    video = next(s for s in streams if s["codec_type"] == "video")
    audio = next((s for s in streams if s["codec_type"] == "audio"), None)
    if not audio:
        raise ValueError("The presenter recording needs a voice track")
    duration = float(video.get("duration") or probe(source, args.ffprobe)["format"]["duration"])
    keep = json.loads(Path(args.keep).read_text("utf-8-sig")) if args.keep else [[0, duration]]
    if not keep or not .5 <= args.speed <= 2:
        raise ValueError("Supply keep ranges in seconds and a speed between 0.5 and 2")
    filters, joins, records = [], [], []
    last_end = cursor = 0
    for index, (start, end) in enumerate(keep):
        if not all(map(math.isfinite, (start, end))) or start < last_end or end <= start or end > duration + 1/30:
            raise ValueError(f"Invalid or overlapping source interval: {start}, {end}")
        end = min(end, duration)
        frames = round((end - start) * 30 / args.speed)
        if frames < 1:
            raise ValueError("Cut shorter than an output frame")
        length = frames / 30
        # Pad only the rounding tail and trim to an exact frame and sample count.
        filters.extend([
            f"[0:v]trim=start={start}:end={end},setpts=(PTS-STARTPTS)/{args.speed},"
            f"fps=30,tpad=stop_duration=0.1:stop_mode=clone,trim=end_frame={frames},setpts=PTS-STARTPTS[v{index}]",
            f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,aresample=48000,"
            f"atempo={args.speed},apad,atrim=end_sample={frames*1600},"
            f"afade=t=in:d=0.004,afade=t=out:st={max(0,length-.004)}:d=0.004[a{index}]"
        ])
        joins.append(f"[v{index}][a{index}]")
        records.append(dict(source_start=start, source_end=end, first_frame=cursor, end_frame=cursor+frames))
        cursor += frames
        last_end = end
    filters.append("".join(joins) + f"concat=n={len(keep)}:v=1:a=1[cut][voice]")
    filters.append("[cut]scale=1080:1920:force_original_aspect_ratio=decrease:force_divisible_by=2,"
                   "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1[portrait]")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as staging:
        folder = Path(staging) / "cut"
        folder.mkdir()
        subprocess.run([args.ffmpeg, "-v", "error", "-nostdin", "-i", str(source), "-filter_complex",
                        ";".join(filters), "-map", "[portrait]", "-map", "[voice]", "-c:v", "libx264",
                        "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p", "-c:a", "alac",
                        "-movflags", "+faststart", str(folder / "presenter.mp4")], check=True)
        rendered = next(s for s in probe(folder / "presenter.mp4", args.ffprobe)["streams"] if s["codec_type"] == "video")
        if int(rendered["nb_frames"]) != cursor:
            raise ValueError("Locked video and cut map disagree")
        (folder / "cut-map.json").write_text(json.dumps(dict(fps=30, speed=args.speed, frames=cursor,
                                                      keep=records), indent=2), "utf-8")
        folder.rename(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("--keep", help="JSON array of [source start, source end] in seconds")
    parser.add_argument("--speed", type=float, default=1)
    parser.add_argument("--out", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    lock(parser.parse_args())
