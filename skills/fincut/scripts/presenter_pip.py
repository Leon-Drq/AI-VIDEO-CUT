"""Overlay source-synchronous circles only on half-open edit-time ranges."""
import argparse
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw


def video(path, probe):
    cmd = [probe, '-v', 'error', '-select_streams', 'v:0', '-show_entries',
           'stream=width,height,duration,sample_aspect_ratio:stream_side_data=rotation:format=duration',
           '-of', 'json', str(path)]
    data = json.loads(subprocess.check_output(cmd))
    stream = data['streams'][0]
    if stream.get('sample_aspect_ratio') not in (None, 'N/A', '1:1') or any(
        int(item.get('rotation', 0)) % 360 for item in stream.get('side_data_list', [])
    ):
        raise ValueError('Normalize rotation and sample aspect ratio before compositing')
    return stream['width'], stream['height'], float(stream.get('duration') or data['format']['duration'])


def interval_filter(text, limit):
    result = []
    previous = 0.
    for item in text.split(','):
        start, end = map(float, item.strip().split('-'))
        if not (math.isfinite(start) and math.isfinite(end) and previous <= start < end <= limit + .001):
            raise ValueError('Use sorted, non-overlapping ranges within both video tracks')
        result.append(f'gte(t,{start})*lt(t,{end})')
        previous = end
    return '+'.join(result)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'presenter', 'output'):
        p.add_argument(name, type=Path)
    p.add_argument('--crop', required=True, help='Source x,y,square-size in pixels')
    p.add_argument('--ranges', required=True, help='Seconds, e.g. 1.2-3.4,5.0-8.0')
    p.add_argument('--corner', choices=('tr', 'br'), default='tr')
    p.add_argument('--ffmpeg', default='ffmpeg')
    p.add_argument('--ffprobe')
    a = p.parse_args()
    encoder = shutil.which(a.ffmpeg)
    if not encoder:
        p.error('Set --ffmpeg to the FFmpeg executable')
    probe = a.ffprobe or str(Path(encoder).with_name('ffprobe'+Path(encoder).suffix))
    if a.output.suffix.lower() != '.mp4' or a.output.exists():
        p.error('Provide a new MP4 output path')
    bw, bh, base_duration = video(a.base, probe)
    sw, sh, speaker_duration = video(a.presenter, probe)
    x, y, size = map(int, a.crop.split(','))
    if min(x,y) < 0 or size < 2 or x+size > sw or y+size > sh:
        p.error('Face crop extends beyond the presenter image')
    enable = interval_filter(a.ranges, min(base_duration, speaker_duration))
    diameter = max(8, 2*round(bw*202/1080/2))
    right = round(bw*58/1080)
    vert = round(bh*(.05625 if a.corner == 'tr' else .17))
    py = vert if a.corner == 'tr' else bh-vert-diameter
    # Match time zero on the two prepared video tracks. The base supplies all audio.
    with tempfile.TemporaryDirectory() as tmp:
        mask = Image.new('L', (diameter*3, diameter*3))
        ImageDraw.Draw(mask).ellipse((1,1,mask.width-2,mask.height-2), fill=255)
        alpha = Path(tmp)/'circle.png'
        mask.resize((diameter,diameter), Image.Resampling.LANCZOS).save(alpha)
        graph = (f'[1:v:0]setpts=PTS-STARTPTS,crop={size}:{size}:{x}:{y}:exact=1,'
                 f'scale={diameter}:{diameter},setsar=1,format=rgb24[head];'
                 '[2:v:0]format=gray[mask];[head][mask]alphamerge[round];'
                 f"[0:v:0]setpts=PTS-STARTPTS[main];[main][round]overlay=x={bw-right-diameter}:"
                 f"y={py}:eof_action=pass:enable='{enable}'[out]")
        cmd = [encoder, '-hide_banner','-v','error','-n','-i',str(a.base),'-i',str(a.presenter),
               '-i',str(alpha),'-filter_complex',graph,'-map','[out]','-map','0:a:0?',
               '-c:v','libx264','-preset','veryfast','-crf','17','-pix_fmt','yuv420p',
               '-c:a','aac','-b:a','192k','-movflags','+faststart',str(a.output)]
        # Publish only after FFmpeg has successfully closed the container.
        with tempfile.TemporaryDirectory(dir=a.output.parent) as stage:
            encoded = Path(stage)/'result.mp4'
            subprocess.run([*cmd[:-1],str(encoded)],check=True)
            with encoded.open('rb') as source, a.output.open('xb') as dest:
                shutil.copyfileobj(source,dest)


if __name__ == '__main__':
    main()