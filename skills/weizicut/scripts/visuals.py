"""Reusable portrait-video artwork. Inputs and Pillow canvases use RGB."""
from functools import lru_cache
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

SIZE = (1080, 1920)
WHITE = "#FFF9ED"
GOLD = "#FCC96E"
LANCZOS = Image.Resampling.LANCZOS


def ease(progress):
    p = max(0., min(1., progress))
    return p * p * (3 - 2 * p)


@lru_cache(maxsize=1)
def graphite():
    y, x = np.indices((960, 540))
    grain = np.random.default_rng(51).normal(0, .8, x.shape)
    shade = 10 + 4*np.exp(-((x-480)/270)**2-((y-105)/270)**2) + grain
    rgb = np.uint8(np.stack([shade*.94, shade*1.07, shade*1.18], axis=-1))
    for i in range(32, 540, 48):
        cv2.line(rgb, (i, 0), (i, 959), (19, 23, 26), 1, cv2.LINE_AA)
    for i in range(4, 960, 48):
        cv2.line(rgb, (0, i), (539, i), (19, 23, 26), 1, cv2.LINE_AA)
    return rgb


def line(canvas, x, y, color):
    points = np.int32(np.stack(np.broadcast_arrays(x, y), axis=1)*8)
    cv2.polylines(canvas, [points], False, color, 1, cv2.LINE_AA, 3)


def backdrop(t):
    buf = graphite().copy()
    def globe_arc(lon, lat):
        x = np.cos(lat)*np.cos(lon)
        y = np.sin(lat)
        z = np.cos(lat)*np.sin(lon)
        yp = .95*y-.31*z
        sx = 528+279*(.943*x-.333*yp)
        sy = 92+279*(.333*x+.943*yp)
        visible = np.flatnonzero(.95*z+.31*y > .04)
        for section in np.split(visible, np.flatnonzero(np.diff(visible)!=1)+1):
            if len(section)>1:
                line(buf, sx[section], sy[section], (31, 42, 48))
    lon = np.linspace(-math.pi, math.pi, 145)
    lat = np.linspace(-math.pi/2, math.pi/2, 90)
    for phi in np.linspace(-1.36, 1.36, 11):
        globe_arc(lon+t*.065, phi)
    for angle in np.arange(16)*2*math.pi/16:
        globe_arc(angle+t*.065, lat)
    x = np.linspace(-48, 588, 185)
    def mesh(row, px):
        v = row/16
        return 797+119*v-.30*px+43*np.sin(px/138-t*.30+v*1.35)+26*np.sin(px/92+t*.20+v*.70)
    for row in range(17):
        line(buf, x, mesh(row, x), (29, 41, 46))
        if row in (2, 8, 14):
            px = (t*(20+row*.22)+row*66)%720-80
            arc = np.linspace(px-15, px, 12)
            line(buf, arc, mesh(row, arc), (72, 88, 92))
    for px in range(-45, 605, 31):
        rows = np.arange(17)
        xs = px+9*rows/16
        line(buf, xs, mesh(rows, xs), (26, 37, 43))
    return Image.fromarray(cv2.resize(buf, SIZE, interpolation=cv2.INTER_CUBIC))


def sticker(rgb, alpha, radius):
    # Preserve original soft hair in the foreground, build the hard paper edge from its silhouette.
    alpha = np.asarray(alpha.convert("L"))
    edge = cv2.medianBlur(np.uint8(alpha > 112)*255, 5)
    contours, _ = cv2.findContours(edge, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    shape = np.zeros_like(alpha)
    for contour in contours:
        if cv2.contourArea(contour) >= max(30, alpha.size*.0004):
            cv2.drawContours(shape, [contour], -1, 255, -1)
    pad = radius*3
    padded = np.pad(shape, pad)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius*2+1,)*2)
    rim = cv2.GaussianBlur(cv2.dilate(padded, kernel), (0, 0), .72)
    # Do not draw a vertical white cut across an arm that extends beyond the camera frame.
    rim[np.flatnonzero(shape[:, 0])+pad, :pad+1] = 0
    rim[np.flatnonzero(shape[:, -1])+pad, pad+shape.shape[1]-1:] = 0
    paper = Image.new("RGBA", (padded.shape[1], padded.shape[0]))
    shadow = Image.fromarray(rim).filter(ImageFilter.GaussianBlur(radius*.55)).point(lambda p: int(p*.72))
    paper.paste((5, 7, 9, 255), (radius//2, radius//2, paper.width+radius//2, paper.height+radius//2), shadow)
    paper.paste((255, 249, 236, 255), (0, 0, *paper.size), Image.fromarray(rim))
    foreground = rgb.convert("RGBA")
    foreground.putalpha(Image.fromarray(alpha))
    paper.alpha_composite(foreground, (pad, pad))
    return paper, pad


def crop_fraction(im, roi):
    x, y, right, bottom = roi
    if not (0 <= x < right <= 1 and 0 <= y < bottom <= 1):
        raise ValueError(f"Invalid normalized crop {roi}")
    return im.crop((round(x*im.width), round(y*im.height), round(right*im.width), round(bottom*im.height)))


def draw_host(canvas, rgb, matte, style, rect, roi, elapsed):
    x, y, w, h = rect
    if style == "pip":
        # Use exactly the same crop and scale for the two synchronized tracks.
        if w != h:
            raise ValueError("Use a square box for a circular presenter window")
        rim = max(3, round(w*.034))
        side = w-rim*2
        face = ImageOps.fit(crop_fraction(rgb, roi), (side, side), LANCZOS)
        mask = ImageOps.fit(crop_fraction(matte, roi), (side, side), LANCZOS)
        person, pad = sticker(face, mask, max(3, round(w*.018)))
        coin = Image.new("RGBA", (w, h), WHITE)
        inner = Image.new("RGBA", (side, side), "#30393D")
        inner.alpha_composite(person, (-pad, -pad))
        circle = Image.new("L", (side*2, side*2))
        ImageDraw.Draw(circle).ellipse((0, 0, side*2-1, side*2-1), fill=255)
        coin.paste(inner, (rim, rim), circle.resize((side, side), LANCZOS))
        canvas.paste(coin, (x,y), circle.resize((w, h), LANCZOS))
        return
    photo = crop_fraction(rgb, roi)
    mask = crop_fraction(matte, roi)
    q = min(1., max(0., elapsed/.32))
    scale = 1+.045*math.exp(-4*q)*math.sin(2*math.pi*q)
    ratio = min(w/photo.width, h/photo.height)*scale
    size = (max(1, round(photo.width*ratio)), max(1, round(photo.height*ratio)))
    person, pad = sticker(photo.resize(size, LANCZOS), mask.resize(size, LANCZOS), max(5, round(size[0]*.014)))
    canvas.paste(person, (round(x+(w-size[0])/2)-pad, round(y+h-size[1]+(1-ease(q))*20)-pad), person)


def mount(image, kind, elapsed):
    p = ease(elapsed/(.40 if kind == "paper" else .28))
    edge = {"paper":8, "photo":13, "screen":3}[kind]
    color = {"paper":"#F3EFDF", "photo":"#FFFBF2", "screen":"#626E72"}[kind]
    w,h = image.size
    tile = Image.new("RGBA", (w+2*edge,h+2*edge))
    radius = 2 if kind=="paper" else 10
    draw = ImageDraw.Draw(tile)
    draw.rounded_rectangle((0,0,tile.width-1,tile.height-1), radius, fill=color)
    inner = Image.new("L", (w,h))
    ImageDraw.Draw(inner).rounded_rectangle((0,0,w-1,h-1), max(1,radius-edge//2), fill=255)
    tile.paste(image.convert("RGB"), (edge,edge), inner)
    if kind=="paper":
        fold = min(25, max(9,w//30))
        draw.polygon([(tile.width-fold,0),(tile.width,fold),(tile.width-fold,fold)], fill="#D6D0C1")
        if p<1:
            a = np.asarray(tile)
            hinge = int(tile.height*.55)
            leaf = a[hinge:].copy()
            lh,lw = leaf.shape[:2]
            shade = (1-p)*(.10+.28*np.exp(-np.arange(lh)[:,None,None]/(lh*.30)))
            leaf[:,:,:3] = leaf[:,:,:3]*(1-shade)
            source = np.float32([[0,0],[lw-1,0],[lw-1,lh-1],[0,lh-1]])
            inset = (1-p)*lw*.074
            bottom = (lh-1)*(.24+.76*p)
            target = np.float32([[0,0],[lw-1,0],[lw-1-inset,bottom],[inset,bottom]])
            tile.paste(Image.fromarray(cv2.warpPerspective(leaf, cv2.getPerspectiveTransform(source,target),
                                                           (lw,lh), flags=cv2.INTER_CUBIC)), (0,hinge))
    angle = {"paper":-2.0, "photo":1.1, "screen":0}[kind] - (1-p)*(4 if kind!="screen" else 0)
    tile = tile.rotate(angle, Image.Resampling.BICUBIC, expand=True)
    pad = 22
    result = Image.new("RGBA", (tile.width+2*pad,tile.height+2*pad))
    shadow = Image.new("L", result.size)
    shadow.paste(tile.getchannel("A"), (pad+3,pad+7))
    result.paste((2,4,6,255), (0,0,*result.size), shadow.filter(ImageFilter.GaussianBlur(8)).point(lambda a:int(a*.6)))
    result.alpha_composite(tile, (pad,pad))
    return result, round(60*(1-p))
