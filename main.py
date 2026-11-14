#!/usr/bin/env python3
"""food-picture-01 entry: a golden crispy fried-chicken plate, drawn procedurally.

Python 3.12/3.13, standard library only. It draws a mouth-watering plate of
KAKANG-style fried chicken -- crispy golden drumsticks and a thigh on a white
ceramic plate, a fan of fries, a ramekin of glossy ketchup, a lemon wedge and
parsley, steam rising, on a red-white gingham liner over a warm wooden table --
into an 800x800 RGB framebuffer, and writes it with a hand-built PNG encoder
(zlib + struct, no Pillow).

Run: mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
Output: <out>/entry.png, 800x800 RGB PNG, byte-identical on every run.
"""

import math
import os
import struct
import zlib

W, H = 800, 800
OUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")


# ---------------------------------------------------------------------------
# Deterministic pseudo-random numbers (fixed-seed LCG; no time, no os.urandom).
# ---------------------------------------------------------------------------
def lcg(seed):
    state = seed & 0xFFFFFFFF

    def nxt():
        nonlocal state
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        return state / 4294967296.0

    return nxt


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


# ---------------------------------------------------------------------------
# Framebuffer: list of bytearray rows, 3 bytes (RGB) per pixel.
# ---------------------------------------------------------------------------
def new_canvas():
    top = (98, 62, 34)
    bottom = (46, 27, 14)
    rows = []
    for y in range(H):
        t = y / (H - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        rows.append(bytearray(bytes((r, g, b))) * W)
    return rows


def hspan(rows, y, x0, x1, rgb, a=255):
    """Blend a horizontal span of row y from x0 to x1 (exclusive)."""
    if y < 0 or y >= H:
        return
    x0 = max(0, int(x0))
    x1 = min(W, int(x1))
    if x1 <= x0:
        return
    row = rows[y]
    if a >= 255:
        row[x0 * 3:x1 * 3] = bytes(rgb) * (x1 - x0)
    elif a > 0:
        r, g, b = rgb
        for x in range(x0, x1):
            i = x * 3
            row[i] = (r * a + row[i] * (255 - a)) // 255
            row[i + 1] = (g * a + row[i + 1] * (255 - a)) // 255
            row[i + 2] = (b * a + row[i + 2] * (255 - a)) // 255


def disc(rows, cx, cy, r, rgb, a=255):
    """Filled circle with a 1px soft feather at the rim."""
    r = float(r)
    y0 = max(0, int(cy - r - 2))
    y1 = min(H - 1, int(cy + r + 2))
    for y in range(y0, y1 + 1):
        dy = y - cy
        inside = r * r - dy * dy
        if inside < 0:
            continue
        half = math.sqrt(inside)
        hspan(rows, y, cx - half, cx + half, rgb, a)
        hspan(rows, y, cx - half - 1, cx - half, rgb, a // 3)
        hspan(rows, y, cx + half, cx + half + 1, rgb, a // 3)


def ellipse_rot(rows, cx, cy, rx, ry, deg, rgb, a=255):
    """Filled rotated ellipse; alpha fades over a thin band at the rim."""
    th = math.radians(deg)
    co, si = math.cos(th), math.sin(th)
    ex = math.sqrt((rx * co) ** 2 + (ry * si) ** 2)
    ey = math.sqrt((rx * si) ** 2 + (ry * co) ** 2)
    x0 = max(0, int(cx - ex - 2))
    x1 = min(W - 1, int(cx + ex + 2))
    y0 = max(0, int(cy - ey - 2))
    y1 = min(H - 1, int(cy + ey + 2))
    for y in range(y0, y1 + 1):
        dy = y - cy
        row = rows[y]
        for x in range(x0, x1 + 1):
            dx = x - cx
            u = dx * co + dy * si
            v = -dx * si + dy * co
            d = (u / rx) ** 2 + (v / ry) ** 2
            if d > 1.08:
                continue
            if d <= 0.94:
                aa = a
            else:
                aa = int(a * (1.08 - d) / 0.14)
            i = x * 3
            r, g, b = rgb
            row[i] = (r * aa + row[i] * (255 - aa)) // 255
            row[i + 1] = (g * aa + row[i + 1] * (255 - aa)) // 255
            row[i + 2] = (b * aa + row[i + 2] * (255 - aa)) // 255


def thick_line(rows, x0, y0, x1, y1, w, rgb, a=255):
    """A line drawn by stamping discs along it (round caps included)."""
    length = math.hypot(x1 - x0, y1 - y0)
    steps = max(1, int(length / max(1.0, w * 0.4)))
    for i in range(steps + 1):
        t = i / steps
        disc(rows, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, w / 2.0, rgb, a)


def speckle(rows, cx, cy, rx, ry, deg, n, seed, palette, rmin=1.0, rmax=3.0):
    """Deterministic crispy speckles scattered inside a rotated ellipse."""
    rnd = lcg(seed)
    th = math.radians(deg)
    co, si = math.cos(th), math.sin(th)
    for _ in range(n):
        while True:
            u = rnd() * 2 - 1
            v = rnd() * 2 - 1
            if u * u + v * v <= 1:
                break
        u *= 0.92
        v *= 0.92
        x = cx + u * rx * co - v * ry * si
        y = cy + u * rx * si + v * ry * co
        c = palette[int(rnd() * len(palette))]
        disc(rows, x, y, rmin + rnd() * (rmax - rmin), c, 200)


def gingham(rows, x0, y0, x1, y1, cell, c1, c2, corner=40):
    """Red-white gingham check inside a rounded rectangle."""
    for y in range(max(0, y0), min(H, y1)):
        xa, xb = x0, x1
        if y < y0 + corner:
            dy = (y0 + corner) - y
            dx = math.sqrt(max(0, corner * corner - dy * dy))
            xa = x0 + corner - dx
            xb = x1 - corner + dx
        elif y >= y1 - corner:
            dy = y - (y1 - corner)
            dx = math.sqrt(max(0, corner * corner - dy * dy))
            xa = x0 + corner - dx
            xb = x1 - corner + dx
        row_band = (y // cell) % 2
        x = int(xa)
        while x < int(xb):
            c = c1 if ((x // cell) % 2 == row_band) else c2
            hspan(rows, y, x, min(int(xb), x + cell), c)
            x += cell


def vignette(rows, strength=46):
    """Darken the corners a little so the eye stays on the plate."""
    cx, cy = W / 2.0, H / 2.0
    maxd2 = cx * cx + cy * cy
    cut2 = (0.55 * 0.55) * maxd2
    for y in range(H):
        dy = y - cy
        row = rows[y]
        for x in range(W):
            dx = x - cx
            d2 = dx * dx + dy * dy
            if d2 < cut2:
                continue
            t = min(1.0, (math.sqrt(d2 / maxd2) - 0.55) / 0.45)
            a = int(strength * t * t)
            i = x * 3
            row[i] = row[i] * (255 - a) // 255
            row[i + 1] = row[i + 1] * (255 - a) // 255
            row[i + 2] = row[i + 2] * (255 - a) // 255


def steam(rows, x, y_top, y_bot, amp, phase, seed):
    """Soft translucent wisps rising from the hot chicken."""
    steps = max(1, int((y_bot - y_top) // 2))
    for i in range(steps + 1):
        t = i / steps
        y = y_bot - t * (y_bot - y_top)
        cx = x + amp * math.sin(t * 9.0 + phase) * (0.4 + 0.6 * t)
        w = 8 + 18 * t
        a = int(48 * (1 - t) * (0.7 + 0.3 * math.sin(t * 20.0 + phase)))
        if a > 0:
            disc(rows, cx, y, w, (255, 250, 244), a)


# ---------------------------------------------------------------------------
# Food pieces.
# ---------------------------------------------------------------------------
CRISP_DARK = (146, 82, 22)
CRISP_DEEP = (118, 60, 16)
CRISP_GOLD = (224, 152, 60)
CRISP_LIGHT = (240, 180, 94)
CHICKEN_BASE = (198, 122, 42)
CHICKEN_RIM = (150, 84, 24)


def chicken_piece(rows, cx, cy, rx, ry, rot, seed, bone=None):
    """One crispy fried-chicken piece; bone is ((x0,y0),(x1,y1)) or None."""
    ellipse_rot(rows, cx + 8, cy + 14, rx, ry, rot, (58, 30, 12), 70)
    ellipse_rot(rows, cx, cy, rx + 7, ry + 7, rot, CHICKEN_RIM)
    ellipse_rot(rows, cx, cy, rx, ry, rot, CHICKEN_BASE)
    speckle(rows, cx, cy, rx, ry, rot, 230, seed,
            [CRISP_DARK, CRISP_DEEP, CRISP_GOLD, CRISP_LIGHT], 1.0, 3.2)
    rnd = lcg(seed + 7)
    for _ in range(11):
        ang = rnd() * 6.283185307
        rr = 0.55 * rnd()
        bx = cx + math.cos(ang) * rx * rr * 0.8
        by = cy + math.sin(ang) * ry * rr * 0.8 - ry * 0.18
        c = CRISP_DARK if rnd() < 0.6 else CRISP_GOLD
        disc(rows, bx, by, 4 + rnd() * 5, c, 210)
    ellipse_rot(rows, cx - rx * 0.30, cy - ry * 0.38, rx * 0.46, ry * 0.30,
                rot - 12, (244, 190, 96), 90)
    rnd2 = lcg(seed + 13)
    for _ in range(3):
        gx = cx - rx * 0.45 + rnd2() * rx * 0.5
        gy = cy - ry * 0.5 + rnd2() * ry * 0.3
        disc(rows, gx, gy, 3 + rnd2() * 3, (252, 216, 142), 170)
    if bone is not None:
        (bx0, by0), (bx1, by1) = bone
        thick_line(rows, bx0, by0, bx1, by1, 13, (246, 238, 222))
        disc(rows, bx1, by1, 12, (246, 238, 222))
        disc(rows, bx1 + 8, by1 + 5, 8, (238, 228, 208))


def fries(rows, cx, cy, seed):
    """A fan of golden fries behind the chicken."""
    rnd = lcg(seed)
    for i in range(7):
        ang = math.radians(-58 + i * 19 + (rnd() - 0.5) * 6)
        length = 150 + rnd() * 42
        x1 = cx + math.sin(ang) * length
        y1 = cy - math.cos(ang) * length
        thick_line(rows, cx, cy, x1, y1, 20, (186, 128, 36))
        thick_line(rows, cx, cy, x1, y1, 15, (234, 180, 68))
        for _ in range(6):
            t = rnd()
            sx = cx + (x1 - cx) * t + (rnd() - 0.5) * 10
            sy = cy + (y1 - cy) * t + (rnd() - 0.5) * 10
            disc(rows, sx, sy, 1.2, (255, 252, 240), 220)


def ramekin(rows, cx, cy):
    """Small white ramekin of glossy red ketchup."""
    disc(rows, cx + 4, cy + 6, 66, (58, 30, 12), 70)
    disc(rows, cx, cy, 64, (250, 248, 244))
    disc(rows, cx, cy, 52, (196, 30, 22))
    ellipse_rot(rows, cx - 14, cy - 16, 26, 14, -18, (240, 96, 74), 130)
    disc(rows, cx - 24, cy - 22, 5, (252, 150, 128), 200)


def lemon_wedge(rows, cx, cy):
    """A lemon wedge for a pop of yellow."""
    disc(rows, cx + 3, cy + 4, 47, (58, 30, 12), 60)
    disc(rows, cx, cy, 46, (246, 214, 78))
    disc(rows, cx, cy, 36, (252, 232, 130))
    for k in range(3):
        ang = math.radians(-70 + k * 55)
        thick_line(rows, cx, cy,
                   cx + math.cos(ang) * 34, cy + math.sin(ang) * 34,
                   3, (230, 196, 60))


def parsley(rows, x, y, rot):
    """A small parsley sprig: three leaves fanning from one point."""
    for k in range(3):
        ang = math.radians(rot + (k - 1) * 38)
        ellipse_rot(rows, x + math.cos(ang) * 14, y + math.sin(ang) * 10,
                    16, 8, math.degrees(ang), (52, 122, 48))
    disc(rows, x, y, 4, (40, 100, 40))


# ---------------------------------------------------------------------------
# Composition.
# ---------------------------------------------------------------------------
def draw():
    rows = new_canvas()
    rnd = lcg(20261114)

    # Wooden table: faint plank lines and grain speckle.
    for y in (180, 380, 580):
        for dy in range(3):
            hspan(rows, y + dy, 0, W, (38, 21, 11), 46)
    for _ in range(500):
        gx = rnd() * W
        gy = rnd() * H
        disc(rows, gx, gy, 1.0 + rnd() * 1.5, (70, 42, 20), 26)

    # Red-white gingham liner (the KAKANG brand echo) peeking past the plate.
    gingham(rows, 70, 150, 730, 770, 44, (196, 38, 34), (250, 242, 232))

    # Ceramic plate with a soft drop shadow and a shallow well.
    ellipse_rot(rows, 400, 456, 302, 294, 0, (58, 30, 12), 70)
    disc(rows, 400, 440, 295, (250, 248, 243))
    disc(rows, 400, 440, 262, (243, 239, 232))
    ellipse_rot(rows, 400, 648, 200, 42, 0, (120, 100, 84), 26)

    # Fries fanning up behind the chicken, upper right of the plate.
    fries(rows, 590, 340, 101)

    # Chicken: one big thigh and two drumsticks, overlapping.
    chicken_piece(rows, 370, 430, 150, 108, -18, 11)
    chicken_piece(rows, 300, 540, 120, 88, 38, 23,
                  bone=((206, 612), (150, 652)))
    chicken_piece(rows, 520, 510, 118, 86, -32, 37,
                  bone=((582, 566), (632, 606)))

    # Ketchup ramekin, lemon wedge, parsley.
    ramekin(rows, 255, 615)
    lemon_wedge(rows, 585, 625)
    parsley(rows, 180, 350, -30)
    parsley(rows, 655, 385, 140)
    parsley(rows, 430, 668, 80)

    # Steam rising off the hot chicken, up over the dark table so it reads.
    steam(rows, 320, 95, 280, 16, 0.4, 201)
    steam(rows, 385, 85, 270, 18, 2.1, 202)
    steam(rows, 450, 95, 280, 15, 4.0, 203)
    steam(rows, 510, 105, 290, 14, 5.3, 204)

    # Warm top light, then a gentle vignette to hold the eye on the plate.
    for y in range(200):
        hspan(rows, y, 0, W, (255, 240, 210), int(10 * (1 - y / 200.0)))
    vignette(rows, 46)
    return rows


# ---------------------------------------------------------------------------
# Hand-built PNG encoder (zlib + struct, no Pillow).
# ---------------------------------------------------------------------------
def chunk(typ, data):
    out = struct.pack(">I", len(data)) + typ + data
    return out + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)


def write_png(path, rows):
    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    comp = zlib.compress(raw, 9)
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp) + chunk(b"IEND", b""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


def main():
    rows = draw()
    out = os.path.join(OUT_DIR, "entry.png")
    size = write_png(out, rows)
    print("wrote %s (%d bytes, %dx%d)" % (out, size, W, H))


if __name__ == "__main__":
    main()
