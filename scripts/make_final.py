# -*- coding: utf-8 -*-
"""
make_final.py - 封面生成 + 静态轮播视频

封面按当前文章标题自动生成（从 meta.json 读取），暖调大字风格。
用法:
  python make_final.py --workdir <dir> --out <video.mp4> [--slices-dir capture_v2]
                       [--subtitle "副标题"] [--author "期权Z叔"] [--theme warm]

依赖: workdir/<slices-dir>/meta.json 里有 title 字段
"""
import argparse
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
COVER_DUR = 2.5
SLIDE_DUR = 3.5

FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
FONT_REG = r"C:\Windows\Fonts\msyh.ttc"

# 封面主题
THEMES = {
    "warm": {"top": (41, 25, 18), "bottom": (94, 55, 32), "accent": (245, 158, 11), "text": (253, 246, 237)},
    "dark": {"top": (12, 18, 32), "bottom": (28, 39, 62), "accent": (96, 165, 250), "text": (241, 245, 249)},
    "light": {"top": (248, 250, 252), "bottom": (224, 231, 241), "accent": (37, 99, 235), "text": (15, 23, 42)},
}


def wrap_text(draw, text, font, max_w):
    """按像素宽度自动换行"""
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


def make_cover(out_path, title, subtitle, author, theme, bg=None):
    """暖调大字封面：背景模糊压暗 + 引号装饰 + 大标题"""
    th = THEMES.get(theme, THEMES["warm"])
    img = Image.new("RGB", (W, H), th["top"])

    # 背景：首图高斯模糊压暗
    if bg and Path(bg).exists():
        try:
            b = Image.open(bg).convert("RGB")
            r = max(W / b.width, H / b.height)
            b = b.resize((int(b.width * r) + 1, int(b.height * r) + 1))
            b = b.crop(((b.width - W) // 2, (b.height - H) // 2,
                        (b.width - W) // 2 + W, (b.height - H) // 2 + H))
            b = b.filter(ImageFilter.GaussianBlur(14))
            dark = Image.new("RGB", (W, H), th["top"])
            img = Image.blend(b, dark, 0.72)
        except Exception:
            pass

    # 渐变遮罩（上深下浅）
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

    # 标题（自动换行）
    lines = wrap_text(d, title, f_title, W - 180)
    y = 560
    for ln in lines[:6]:
        d.text((90, y), ln, font=f_title, fill=th["text"])
        y += 118

    # accent 短线
    d.rounded_rectangle((90, y + 40, 290, y + 50), radius=5, fill=th["accent"])

    # 副标题
    if subtitle:
        sy = y + 110
        for ln in wrap_text(d, subtitle, f_sub, W - 180)[:3]:
            d.text((90, sy), ln, font=f_sub, fill=th["text"])
            sy += 64

    # 底部信息
    if author:
        d.text((90, H - 220), f"@{author}", font=f_small, fill=th["accent"])
    d.text((90, H - 150), "完整全文见原文", font=f_small, fill=th["text"])

    img.save(out_path, quality=95)
    print(f"封面已生成: {out_path}")
    print(f"  标题: {title}")
    return out_path


def resolve_bgm(spec):
    """
    解析 BGM 参数：
      none              -> 返回 None（无音乐）
      文件路径           -> 原样返回
      random            -> 全曲库随机
      upbeat/calm/...   -> 指定情绪包内随机
    曲库清单在 assets/bgm/manifest.json，由 fetch_bgm.py 维护。
    """
    import random as _r

    bgm_dir = Path(r"C:\Users\Lenovo\.workbuddy\skills\link-to-video\assets\bgm")
    if not spec or spec.lower() == "none":
        return None
    p = Path(spec)
    if p.exists() and p.is_file():
        return str(p)

    man_path = bgm_dir / "manifest.json"
    if not man_path.exists():
        raise SystemExit(f"曲库清单不存在: {man_path}\n先跑 fetch_bgm.py --curate 建库")
    man = json.loads(man_path.read_text(encoding="utf-8"))
    tracks = man.get("tracks", [])
    if not tracks:
        raise SystemExit("曲库为空，先跑 fetch_bgm.py --curate")

    mood = spec.strip().lower()
    if mood in ("random", "auto", "any"):
        pool = tracks
    else:
        pool = [t for t in tracks if t.get("mood") == mood]
        if not pool:
            raise SystemExit(f"没有 {mood} 风格的曲目，可用: "
                             + ", ".join(sorted({t['mood'] for t in tracks})))

    pick = _r.choice(pool)
    path = bgm_dir / pick["file"]
    if not path.exists():
        raise SystemExit(f"曲目文件缺失: {path}\n重跑 fetch_bgm.py --curate 修复")
    print(f"BGM[{mood}]: {pick['title']}  ({pick.get('feel', '')})")
    print(f"  署名: {pick['credit']}")
    return str(path)


def build_video(cover_path, frame_paths, out_path, bgm, total=None):
    """ffmpeg 静态轮播 + BGM"""
    ff = imageio_ffmpeg.get_ffmpeg_exe()

    inputs = [str(cover_path)] + [str(p) for p in frame_paths]
    durations = [COVER_DUR] + [SLIDE_DUR] * len(frame_paths)
    total = total or sum(durations)
    print(f"总时长: {total:.1f}s (封面{COVER_DUR}s + {len(frame_paths)}页×{SLIDE_DUR}s)")

    parts = []
    for i, dur in enumerate(durations):
        parts.append(
            f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=f5f7fa,"
            f"setsar=1,trim=duration={dur},setpts=PTS-STARTPTS,fps=30[v{i}]"
        )
    concat_in = "".join(f"[v{i}]" for i in range(len(durations)))
    parts.append(f"{concat_in}concat=n={len(durations)}:v=1:a=0[vout]")

    cmd = [ff, "-y"]
    for p in inputs:
        cmd += ["-loop", "1", "-i", p]

    if bgm:
        n_in = len(durations)
        parts.append(
            f"[{n_in}:a]volume=0.35,atrim=duration={total},"
            f"afade=t=in:st=0:d=1.5,afade=t=out:st={total-2}:d=2[aout]"
        )
        cmd += ["-i", str(bgm)]
        cmd += [
            "-filter_complex", ";".join(parts),
            "-map", "[vout]", "-map", "[aout]",
            "-c:a", "aac", "-b:a", "128k",
        ]
    else:
        cmd += ["-filter_complex", ";".join(parts), "-map", "[vout]"]

    cmd += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", "30",
        "-shortest",
        str(out_path),
    ]

    print("生成中...")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("FFMPEG ERROR:")
        print(r.stderr[-3000:])
        return False
    print(f"完成: {out_path}")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True, help="工作目录（含 capture_*/ 和 video_frames/）")
    ap.add_argument("--out", required=True, help="输出视频路径")
    ap.add_argument("--slices-dir", default=None, help="截图目录名，默认自动查找 capture_*")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--author", default="期权Z叔")
    ap.add_argument("--theme", default="warm", choices=list(THEMES.keys()))
    ap.add_argument("--bgm", default="random",
                    help="BGM 选择：文件路径 | random(全库随机) | 情绪包名(upbeat/calm/focus/warm) | none(无音乐)")
    ap.add_argument("--reuse-cover", default=None, help="复用已有封面文件（不自动生成）")
    args = ap.parse_args()

    workdir = Path(args.workdir)
    args.bgm = resolve_bgm(args.bgm)

    # 1. 找截图目录，读 meta.json 拿标题
    slices_dir = None
    if args.slices_dir:
        slices_dir = workdir / args.slices_dir
    else:
        cands = sorted(workdir.glob("capture*"), key=lambda p: p.stat().st_mtime, reverse=True)
        slices_dir = cands[0] if cands else None

    title = "文章标题"
    if slices_dir and (slices_dir / "meta.json").exists():
        meta = json.loads((slices_dir / "meta.json").read_text(encoding="utf-8"))
        title = meta.get("title", "文章标题")
        # 去掉知乎/公众号的后缀
        for suffix in (" - 知乎", " - 微信公众号"):
            if title.endswith(suffix):
                title = title[: -len(suffix)]
    print(f"文章标题: {title}")

    # 2. 封面
    if args.reuse_cover:
        cover = Path(args.reuse_cover)
        print(f"复用封面: {cover}")
    else:
        cover = workdir / "cover.png"
        # 背景图取第一张切片
        bg = None
        if slices_dir and (slices_dir / "slice_1.png").exists():
            bg = slices_dir / "slice_1.png"
        make_cover(cover, title, args.subtitle, args.author, args.theme, bg)

    # 3. 内页
    # 按 screenshots/ 的实际数量截断，避免 video_frames/ 里的旧残留被误用
    frames_dir = workdir / "video_frames"
    screens_dir = workdir / "screenshots"
    n_screens = len(list(screens_dir.glob("slide_*.png"))) if screens_dir.exists() else 0

    # 自然序排序：字符串排序会让 frame_10 排到 frame_2 前面
    frames = sorted(frames_dir.glob("frame_*.png"),
                    key=lambda p: int("".join(c for c in p.stem if c.isdigit()) or 0))
    if n_screens and len(frames) > n_screens:
        print(f"提示: video_frames 有 {len(frames)} 张，按 screenshots({n_screens}) 截断")
        frames = frames[:n_screens]
    print(f"内页: {len(frames)} 张")

    # 4. 生成视频
    ok = build_video(str(cover), frames, Path(args.out), Path(args.bgm))
    if ok:
        print(f"\n✅ 视频已生成: {args.out}")
        print(f"   规格: {W}x{H} 30fps 静态轮播 + BGM")


if __name__ == "__main__":
    main()
