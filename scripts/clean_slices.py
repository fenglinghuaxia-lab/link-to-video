# -*- coding: utf-8 -*-
"""
clean_slices.py - 对截图做智能裁剪
1. 检测每张 slice 的实际内容边界（去掉顶部/底部空白、UI、孤立图标）
2. 输出干净的截图到 screenshots/（小红书用）
3. 输出画布版到 video_frames/（视频用）

算法（v2，2026-08-31 重写）：
  旧版用"整行非背景像素占比 > 5%"判定内容行 —— 遇到短行（如换行后只剩
  "全0基础的小白。"占行宽 15%）会漏检，导致最后一行被切掉。
  新版改为：
    a. 逐行统计非背景像素数（numpy，阈值 |gray-bg| > 45）
    b. 相邻有墨行 gap<=25 合并为"块"（一个块 = 一行文字/一个元素）
    c. 块与块 gap<=220 合并为"簇"（覆盖正常行距 ~63px 与段间距 ~137px）
    d. 剔除"孤立小图标"簇：跨度<=90px 且 宽度<=70px 且 墨量<主簇15%
       （典型：未移除的浮动按钮、圆环图标）
    e. 保留簇的最外边界 + 安全边距
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

# ---------- 可调参数 ----------
INK_THR = 45        # 像素与背景差异超过此值算"有墨"
MIN_INK_ROW = 3     # 一行至少几个有墨像素才算内容行
LINE_GAP = 25       # 块内合并间隙（同一行文字的上下部分）
CLUSTER_GAP = 220   # 簇合并间隙（正常行距63 / 段间距137 都远小于此）
JUNK_SPAN = 90      # 孤立垃圾簇最大跨度
JUNK_WIDTH = 70     # 孤立垃圾簇最大宽度
JUNK_INK_RATIO = 0.15
MARGIN_TOP = 18
MARGIN_BOTTOM = 28


def find_content_bounds(img, debug=False):
    """返回 (top, bottom) 内容边界行号（含）"""
    g = np.asarray(img.convert("L"), dtype=np.int16)
    h, w = g.shape
    if h == 0 or w == 0:
        return 0, max(0, h - 1)

    # 背景色取上下边缘的中位数，比取左上角单个像素稳
    bg = int(np.median(np.concatenate([g[0], g[-1]])))

    ink = (np.abs(g - bg) > INK_THR).sum(axis=1)
    rows = np.where(ink >= MIN_INK_ROW)[0]
    if len(rows) == 0:
        return 0, h - 1

    # 合并成块
    blocks = []
    s = p = int(rows[0])
    for r in rows[1:]:
        r = int(r)
        if r - p > LINE_GAP:
            blocks.append((s, p))
            s = r
        p = r
    blocks.append((s, p))

    # 每块的几何信息
    info = []
    for (b0, b1) in blocks:
        seg = g[b0:b1 + 1]
        cols = np.where((np.abs(seg - bg) > INK_THR).sum(axis=0) >= 1)[0]
        bw = int(cols[-1] - cols[0] + 1) if len(cols) else 0
        info.append({
            "b0": int(b0), "b1": int(b1),
            "w": bw, "ink": int(ink[b0:b1 + 1].sum()),
        })

    # 合并成簇
    clusters = []
    cur = [info[0]]
    for it in info[1:]:
        if it["b0"] - cur[-1]["b1"] <= CLUSTER_GAP:
            cur.append(it)
        else:
            clusters.append(cur)
            cur = [it]
    clusters.append(cur)

    def c_ink(c):
        return sum(x["ink"] for x in c)

    def c_w(c):
        return max(x["w"] for x in c)

    def c_span(c):
        return c[-1]["b1"] - c[0]["b0"]

    main = max(clusters, key=c_ink)
    mi = max(1, c_ink(main))

    keep, dropped = [], []
    for c in clusters:
        is_junk = (
            c is not main
            and c_ink(c) < mi * JUNK_INK_RATIO
            and c_span(c) <= JUNK_SPAN
            and c_w(c) <= JUNK_WIDTH
        )
        (dropped if is_junk else keep).append(c)

    top = min(c[0]["b0"] for c in keep)
    bottom = max(c[-1]["b1"] for c in keep)

    if debug:
        print(f"    背景={bg} 块数={len(info)} 簇数={len(clusters)}")
        print(f"    主簇 y{min(x['b0'] for x in main)}-{max(x['b1'] for x in main)} 墨量={mi}")
        for c in dropped:
            print(f"    丢弃垃圾簇 y{c[0]['b0']}-{c[-1]['b1']} "
                  f"宽{c_w(c)} 墨量{c_ink(c)}")

    crop_top = max(0, top - MARGIN_TOP)
    crop_bottom = min(h - 1, bottom + MARGIN_BOTTOM)
    return crop_top, crop_bottom


def clean_slice(img_path, target_width=860, canvas_size=(1080, 1920), debug=False):
    """
    1. 裁剪掉顶部/底部空白和垃圾元素
    2. 缩放到目标宽度
    3. 居中到白色画布
    返回 (画布版, 纯净裁剪版)
    """
    img = Image.open(img_path).convert("RGB")
    orig_w, orig_h = img.size

    crop_top, crop_bottom = find_content_bounds(img, debug=debug)
    cropped = img.crop((0, crop_top, orig_w, crop_bottom + 1))
    print(f"  裁剪: y {crop_top}-{crop_bottom} / {orig_h}  ->  保留 {cropped.height}px")

    scale = target_width / cropped.width
    new_h = max(1, int(cropped.height * scale))
    if new_h > canvas_size[1]:
        # 超高时按高度反算宽度，保证整页能塞进画布
        scale = canvas_size[1] / cropped.height
        target_width = max(1, int(cropped.width * scale))
        new_h = canvas_size[1]
    resized = cropped.resize((target_width, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", canvas_size, (255, 255, 255))
    canvas.paste(resized, ((canvas_size[0] - target_width) // 2,
                           (canvas_size[1] - new_h) // 2))
    return canvas, cropped


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="工作目录，如 .../wx_out")
    ap.add_argument("--input-dir", default="capture_v3", help="切片所在子目录名")
    ap.add_argument("--width", type=int, default=860)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    base = Path(args.base)
    input_dir = base / args.input_dir
    output_screenshots = base / "screenshots"
    output_frames = base / "video_frames"
    output_screenshots.mkdir(parents=True, exist_ok=True)
    output_frames.mkdir(parents=True, exist_ok=True)

    slices = sorted(input_dir.glob("slice_*.png"),
                    key=lambda p: int("".join(ch for ch in p.stem if ch.isdigit()) or 0))
    print(f"找到 {len(slices)} 张切片（{input_dir}）")

    for i, sp in enumerate(slices, 1):
        print(f"\n--- {sp.name} ---")
        canvas_img, clean_img = clean_slice(
            str(sp), target_width=args.width, debug=args.debug
        )
        clean_img.save(output_screenshots / f"slide_{i}.png", quality=95)
        print(f"  -> screenshots/slide_{i}.png {clean_img.size}")
        canvas_img.save(output_frames / f"frame_{i}.png", quality=95)
        print(f"  -> video_frames/frame_{i}.png")

    print(f"\n完成！{len(slices)} 张已处理")


if __name__ == "__main__":
    main()
