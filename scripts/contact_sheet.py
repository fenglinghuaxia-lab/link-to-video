#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
把「封面 + 画框切片」拼成一张总览图，做演示/给客户看方案时用。

输出单张 PNG：白底、等高等比缩放、下方带序号标签（封面 / 01 / 02 ...）。

用法:
  python contact_sheet.py --workdir <工作目录> [--cols 5] [--height 560]
                          [--out contact_sheet.png] [--no-cover]

输入: <workdir>/cover.png（可选）+ <workdir>/video_frames/frame_*.png
输出: <workdir>/contact_sheet.png
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
FONT_REG = r"C:\Windows\Fonts\msyh.ttc"

BG = (255, 255, 255)
PAD = 32
GAP = 20
LABEL_H = 34
LABEL_COLOR = (110, 110, 110)
COVER_LABEL_COLOR = (60, 90, 130)


def _font(bold, size):
    for p in (FONT_BOLD if bold else FONT_REG, FONT_REG):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def natural_key(p):
    """frame_10 要排在 frame_2 后面"""
    stem = p.stem
    digits = "".join(ch for ch in stem if ch.isdigit())
    return int(digits) if digits else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--cols", type=int, default=5)
    ap.add_argument("--height", type=int, default=560, help="每个缩略图的高度")
    ap.add_argument("--out", default="contact_sheet.png")
    ap.add_argument("--no-cover", action="store_true", help="不拼封面，只拼切片")
    args = ap.parse_args()

    base = Path(args.workdir)
    items = []

    cover = base / "cover.png"
    if not args.no_cover and cover.exists():
        items.append((cover, "封面"))

    frames = sorted((base / "video_frames").glob("frame_*.png"), key=natural_key)
    for i, f in enumerate(frames, 1):
        items.append((f, f"{i:02d}"))

    if not items:
        raise SystemExit(f"没找到任何图片：{base}/cover.png 或 {base}/video_frames/frame_*.png")

    th = args.height
    thumbs = []
    for p, label in items:
        im = Image.open(p).convert("RGB")
        w = max(1, int(im.width * th / im.height))
        thumbs.append((im.resize((w, th), Image.LANCZOS), label, w))

    cols = min(args.cols, len(thumbs))
    rows = (len(thumbs) + cols - 1) // cols
    cell_h = th + 8 + LABEL_H

    # 每列宽度取该列最宽的缩略图，避免留白参差
    col_w = [0] * cols
    for idx, (_, _, w) in enumerate(thumbs):
        c = idx % cols
        col_w[c] = max(col_w[c], w)
    col_x = []
    x = PAD
    for w in col_w:
        col_x.append(x)
        x += w + GAP

    W = col_x[-1] + col_w[-1] + PAD
    H = PAD + rows * (cell_h + GAP) - GAP + PAD

    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    f_label = _font(True, 22)
    f_head = _font(True, 26)

    d.text((PAD, 10), f"共 {len(thumbs)} 张 · 封面 + {len(frames)} 片画框切片",
           font=f_head, fill=(70, 70, 70))

    top = PAD + 26
    for idx, (im, label, w) in enumerate(thumbs):
        r, c = divmod(idx, cols)
        x = col_x[c] + (col_w[c] - w) // 2
        y = top + r * (cell_h + GAP)
        sheet.paste(im, (x, y))
        color = COVER_LABEL_COLOR if label == "封面" else LABEL_COLOR
        tw = d.textbbox((0, 0), label, font=f_label)[2]
        d.text((x + (w - tw) // 2, y + th + 8), label, font=f_label, fill=color)
        d.rectangle([x - 1, y - 1, x + w, y + th], outline=(225, 225, 225))

    out = base / args.out
    sheet.save(out)
    print(f"总览图: {out}")
    print(f"  {W}x{H}  {cols}列 x {rows}行  缩略图高 {th}px")


if __name__ == "__main__":
    main()
