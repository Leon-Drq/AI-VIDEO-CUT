"""Create a new, non-overwriting B-roll edit workspace. Python standard library only."""
import argparse
import json
import math
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source', type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--ffprobe', default=shutil.which('ffprobe'))
    ap.add_argument('--width', type=int)
    ap.add_argument('--height', type=int)
    ap.add_argument('--fps', type=float)
    args = ap.parse_args()
    source = args.source.resolve()
    if not source.is_file():
        ap.error('Source file does not exist')
    if args.out.exists():
        ap.error('Output already exists; select a new version directory')
    if not args.ffprobe:
        ap.error('ffprobe not found; pass --ffprobe with its executable path')
    if bool(args.width) != bool(args.height):
        ap.error('Supply both --width and --height')
    try:
        result = subprocess.run([args.ffprobe, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(source)], capture_output=True, text=True, encoding='utf8', errors='replace', check=True)
        metadata = json.loads(result.stdout)
        video = next(s for s in metadata['streams'] if s.get('codec_type') == 'video')
        duration = float(metadata['format']['duration'])
        fps = args.fps if args.fps is not None else float(Fraction(video.get('avg_frame_rate') or video['r_frame_rate']))
        width = args.width if args.width is not None else video['width']
        height = args.height if args.height is not None else video['height']
        if not all(math.isfinite(n) and n > 0 for n in [duration, fps, width, height]):
            raise ValueError('Invalid duration, fps or dimensions')
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError, StopIteration, ZeroDivisionError) as exc:
        ap.error(f'Cannot probe source: {exc}')
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=False)
    for name in ['analysis', 'assets/broll', 'assets/generated', 'renders', 'verify']:
        (root / name).mkdir(parents=True)
    def write(name, value):
        (root / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    write('analysis/source-probe.json', metadata)
    write('project.json', {'source': str(source), 'duration': duration, 'fps': fps, 'width': width, 'height': height, 'audio_policy': 'preserve unless explicitly changed', 'caption_languages': [], 'status': 'draft', 'source_preserved': True})
    write('shot-map.json', {'duration': duration, 'fps': fps, 'items': []})
    write('assets/sources.json', {'sources': []})
    print(str(root))


if __name__ == '__main__':
    main()
