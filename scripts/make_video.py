# -*- coding: utf-8 -*-
"""
make_video.py - 切片 -> 封面 + Ken Burns 竖版视频(1080x1920) + BGM
用法:
  python make_video.py --dir <workdir> [--bgm <path|random>] [--slide-dur 4.5]
                        [--cover-dur 2.5] [--cover-title "标题"] [--cover-subtitle "副标题"]
                        [--out <out.mp4>] [--theme dark|light|warm]
产出: <workdir>/cover.png, <out.mp4>(默认 <workdir>/output.mp4)
依赖: PIL, imageio_ffmpeg(自带ffmpeg)
"""
import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
BGM_DIR = Path(__file__).resolve().parent.parent / "assets" / "bgm"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
FONT_REG = r"C:\Windows\Fonts\msyh.ttc"

THEMES = {
    "dark": {"top": (12, 18, 32), "bottom": (28, 39, 62), "accent": (96, 165, 250), "text": (241, 245, 249)},
    "light": {"top": (248, 250, 252), "bottom": (224, 231, 241), "accent": (37, 99, 235), "text": (15, 23, 42)},
    "warm": {"top": (41, 25, 18), "bottom": (94, 55, 32), "accent": (245, 158, 11), "text": (253, 246, 237)},
}


def pick_bgm(choice: str):
    if choice and choice != "random":
        p = Path(choice)
        if not p.exists():
            sys.exit(f"[video] BGM 文件不存在: {p}")
        return p
    if not BGM_DIR.exists():
        return None
    files = [f for f in BGM_DIR.iterdir() if f.suffix.lower() in (".mp3", ".m4a", ".ogg", ".wav", ".flac")]
    if not files:
        return None
    return random.choice(files)


def wrap_text(draw, text, font, max_w):
    lines, line = [], ""
    for ch in text:
        t = line + ch
        if draw.textlength(t, font=font) <= max_w:
            line = t
        else:
            lines.append(line)
            line = ch
    if line:
        lines.append(line)
    return lines


def make_cover(outdir: Path, title: str, subtitle: str, author: str, theme: str, bg: Path):
    """封面: 背景取首图高斯模糊压暗 + 标题排版"""
    th = THEMES.get(theme, THEMES["dark"])
    img = Image.new("RGB", (W, H), th["top"])
    if bg.exists():
        try:
            b = Image.open(bg).convert("RGB")
            # cover-fit 裁到 1080x1920
            r = max(W / b.width, H / b.height)
            b = b.resize((int(b.width * r) + 1, int(b.height * r) + 1))
            b = b.crop(((b.width - W) // 2, (b.height - H) // 2, (b.width - W) // 2 + W, (b.height - H) // 2 + H))
            b = b.filter(ImageFilter.GaussianBlur(14))
            dark = Image.new("RGB", (W, H), th["top"])
            img = Image.blend(b, dark, 0.72)
        except Exception:
            pass
    d = ImageDraw.Draw(img)
    # 渐变遮罩(上深下浅)
    grad = Image.new("L", (1, H))
    for y in range(H):
        grad.putpixel((0, y), int(200 * (1 - y / H) + 30))
    overlay = Image.new("RGB", (W, H), th["bottom"])
    img = Image.composite(overlay, img, grad.resize((W, H)))
    d = ImageDraw.Draw(img)

    f_quote = ImageFont.truetype(FONT_BOLD, 120)
    f_title = ImageFont.truetype(FONT_BOLD, 88)
    f_sub = ImageFont.truetype(FONT_REG, 46)
    f_small = ImageFont.truetype(FONT_REG, 38)

    # 顶部引号装饰
    d.text((90, 300), "\u201c", font=f_quote, fill=th["accent"])

    lines = wrap_text(d, title, f_title, W - 180)
    y = 560
    for ln in lines[:6]:
        d.text((90, y), ln, font=f_title, fill=th["text"])
        y += 118
    # accent 短线
    d.rounded_rectangle((90, y + 40, 290, y + 50), radius=5, fill=th["accent"])

    if subtitle:
        sy = y + 110
        for ln in wrap_text(d, subtitle, f_sub, W - 180)[:3]:
            d.text((90, sy), ln, font=f_sub, fill=th["text"])
            sy += 64

    # 底部信息
    if author:
        d.text((90, H - 220), f"@{author}", font=f_small, fill=th["accent"])
    d.text((90, H - 150), "完整全文见知乎原文", font=f_small, fill=th["text"])
    img.save(outdir / "cover.png")
    print(f"[video] 封面已生成: {outdir / 'cover.png'}")


def build_filter(n_slides, slide_dur, cover_dur, slides_h):
    """每个输入一条链: 缩放到1080宽 -> 高不足1920则补白, 超过则竖向匀速平移 -> concat"""
    parts, labels = [], []
    total_inputs = 1 + n_slides  # 0=cover
    for i in range(total_inputs):
        dur = cover_dur if i == 0 else slide_dur
        filters = [f"scale={W}:-2", "setsar=1"]
        scaled_h = slides_h[i]
        if scaled_h <= H:
            filters.append(f"pad={W}:{H}:0:({H}-ih)/2:color=white")
        else:
            # 竖向平移: 从顶部开始滚到底部
            y = f"min(ih-{H}\\,max(0\\,(ih-{H})*t/{dur:.2f}))"
            filters.append(f"crop={W}:{H}:0:{y}")
        filters.append(f"trim=duration={dur:.2f}")
        filters.append("setpts=PTS-STARTPTS")
        filters.append("fps=30")
        lab = f"v{i}"
        parts.append(f"[{i}:v]" + ",".join(filters) + f"[{lab}]")
        labels.append(f"[{lab}]")
    concat = "".join(labels) + f"concat=n={total_inputs}:v=1:a=0[v]"
    return ";".join(parts) + ";" + concat


def probe_scaled_heights(files, ffprobe_img=None):
    """用 PIL 读取图片原始高度, 计算 scale=1080 宽后的高度"""
    hs = []
    for f in files:
        with Image.open(f) as im:
            hs.append(int(im.height * W / im.width))
    return hs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--bgm", default="random")
    ap.add_argument("--slide-dur", type=float, default=4.5)
    ap.add_argument("--cover-dur", type=float, default=2.5)
    ap.add_argument("--cover-title", default=None)
    ap.add_argument("--cover-subtitle", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--theme", default="dark", choices=list(THEMES.keys()))
    args = ap.parse_args()

    d = Path(args.dir)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    slice_files = sorted(d.glob("slice_*.png"), key=lambda p: int(p.stem.split("_")[1]))
    if not slice_files:
        sys.exit("[video] 未找到切片, 先运行 capture.py")

    title = args.cover_title or meta.get("title") or "知乎好文"
    author = meta.get("author") or ""
    make_cover(d, title, args.cover_subtitle or "", author, args.theme, slice_files[0])

    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    files = [d / "cover.png"] + slice_files
    hs = probe_scaled_heights(files)
    fc = build_filter(len(slice_files), args.slide_dur, args.cover_dur, hs)
    total = args.cover_dur + args.slide_dur * len(slice_files)

    bgm = pick_bgm(args.bgm)
    out = Path(args.out) if args.out else d / "output.mp4"

    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    for f in files:
        cmd += ["-loop", "1", "-t", f"{args.slide_dur if f.name != 'cover.png' else args.cover_dur:.2f}", "-i", str(f)]
    has_audio = False
    if bgm:
        cmd += ["-stream_loop", "-1", "-i", str(bgm)]
        has_audio = True
    cmd += ["-filter_complex", fc + (f";[{len(files)}:a]volume=0.35,atrim=0:{total:.2f},afade=t=in:st=0:d=1.2,afade=t=out:st={total-2.0:.2f}:d=2.0[a]" if has_audio else "")]

    if has_audio:
        cmd += ["-map", "[v]", "-map", "[a]"]
    else:
        cmd += ["-map", "[v]"]
    cmd += [
        "-c:v", "libx264", "-r", "30", "-pix_fmt", "yuv420p",
        "-crf", "20", "-preset", "medium",
        "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart",
        str(out),
    ]
    print(f"[video] 合成中... 共 {len(files)} 段, 总时长 {total:.1f}s, BGM: {bgm.name if bgm else '无'}")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stderr[-3000:], file=sys.stderr)
        sys.exit("[video] ffmpeg 失败")
    print(f"[video] 完成 -> {out}")


if __name__ == "__main__":
    main()
