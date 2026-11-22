"""Render a full-page hold, a camera move to a real detail, and a reading hold."""
import argparse
import math
import os
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageOps


def camera_frame(image, size, detail, progress):
    width, height = size
    x, y, crop_width, crop_height = detail
    full_scale = min(width / image.width, height / image.height)
    detail_scale = min(width / crop_width, height / crop_height)
    ease = progress * progress * (3 - 2 * progress)
    scale = full_scale * (detail_scale / full_scale) ** ease
    center_x = image.width / 2 + (x + crop_width / 2 - image.width / 2) * ease
    center_y = image.height / 2 + (y + crop_height / 2 - image.height / 2) * ease
    inverse = 1 / scale
    transform = (inverse, 0, center_x - width * inverse / 2,
                 0, inverse, center_y - height * inverse / 2)
    return image.transform((width, height), Image.Transform.AFFINE, transform,
                           resample=Image.Resampling.BICUBIC, fillcolor=(0, 0, 0)).tobytes()


def render(args, image, frames, temp_path):
    width, height = args.size
    cmd = [args.ffmpeg, '-v', 'error', '-n', '-f', 'rawvideo',
           '-pixel_format', 'rgb24', '-video_size', f'{width}x{height}',
           '-framerate', str(args.fps), '-i', 'pipe:0', '-an', '-c:v', 'libx264',
           '-preset', 'fast', '-crf', '17', '-pix_fmt', 'yuv420p',
           '-movflags', '+faststart', str(temp_path)]
    establish, move, read = frames
    with subprocess.Popen(cmd, stdin=subprocess.PIPE) as encoder:
        try:
            with encoder.stdin as stream:
                first = camera_frame(image, args.size, args.detail, 0)
                for _ in range(establish):
                    stream.write(first)
                for index in range(1, move + 1):
                    stream.write(camera_frame(image, args.size, args.detail, index / move))
                last = camera_frame(image, args.size, args.detail, 1)
                for _ in range(read):
                    stream.write(last)
        except BrokenPipeError:
            encoder.wait()
            raise RuntimeError(f'FFmpeg stopped while rendering (exit {encoder.returncode})') from None
        if encoder.wait():
            raise RuntimeError(f'FFmpeg exited with {encoder.returncode}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--detail', nargs=4, type=int, required=True, metavar=('X', 'Y', 'W', 'H'))
    parser.add_argument('--size', nargs=2, type=int, default=(1080, 1280), metavar=('WIDTH', 'HEIGHT'))
    parser.add_argument('--fps', type=int, default=25)
    parser.add_argument('--establish', type=float, default=0.9, help='Full image hold in seconds')
    parser.add_argument('--move', type=float, default=0.6, help='Camera move in seconds')
    parser.add_argument('--read', type=float, default=1.5, help='Final reading hold in seconds')
    parser.add_argument('--ffmpeg', default='ffmpeg')
    args = parser.parse_args()
    if args.output.suffix.lower() != '.mp4' or args.output.exists():
        parser.error('Choose a new .mp4 output file')
    if args.fps < 1 or any(n <= 0 or n % 2 for n in args.size):
        parser.error('Use a positive frame rate and positive even output dimensions')
    durations = (args.establish, args.move, args.read)
    if any(not math.isfinite(t) or t <= 0 for t in durations):
        parser.error('Durations must be positive and finite')
    frames = [round(t * args.fps) for t in durations]
    if min(frames) < 1:
        parser.error('Each phase must last at least one frame')
    try:
        with Image.open(args.image) as source:
            oriented = ImageOps.exif_transpose(source).convert('RGBA')
            image = Image.new('RGB', oriented.size)
            image.paste(oriented, mask=oriented.getchannel('A'))
        x, y, w, h = args.detail
        if min(x, y) < 0 or min(w, h) < 1 or x + w > image.width or y + h > image.height:
            parser.error(f'Detail rectangle must fit within the oriented {image.width}x{image.height} image')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=args.output.parent) as temp_dir:
            temp_path = Path(temp_dir) / 'clip.mp4'
            render(args, image, frames, temp_path)
            # Publish a completed render without replacing a concurrent writer's file.
            if os.name == 'nt':
                os.rename(temp_path, args.output)
            else:
                os.link(temp_path, args.output)
    except (OSError, RuntimeError) as error:
        parser.exit(1, f'{parser.prog}: {error}\n')
    print(f'{args.output} ({sum(frames)} frames at {args.fps} fps)')


if __name__ == '__main__':
    main()
