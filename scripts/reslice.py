# -*- coding: utf-8 -*-
"""
reslice.py - 按"内容墨量均分"重新切片（替代按页面高度均分）

问题：文章里常有大段空白（未加载的图片占位、大间距模块），
      按页面高度均分会导致某一页只有 1/3 的内容，幻灯片长短悬殊。

做法：
  1. 读 full.png，逐行统计墨量 -> 得到"空白行 / 内容行"
  2. 累积内容行数作为新的"标尺"
  3. 按 n 等分取目标位置，把切口吸附到最近的空白段中心（>=min_gap px）
     —— 保证切口落在段落间隙，不会把一行字劈开
  4. 直接切 full.png 输出新的 slice_*.png
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image

INK_THR = 45
MIN_INK_ROW = 3
MIN_GAP = 80        # 可下刀的最小空白段高度
MAX_SNAP = 500      # 切口最多偏离目标位置多少像素去找空白段
MIN_SLICE = 500     # 相邻切口最小间距


def analyze(a):
    bg = int(np.median(np.concatenate([a[0], a[-1]])))
    ink = (np.abs(a - bg) > INK_THR).sum(axis=1)
    return ink, bg


def blank_runs(ink, min_len):
    """返回所有长度 >= min_len 的空白行区间 [(s,e), ...]"""
    blank = ink < MIN_INK_ROW
    runs, s = [], None
    for y, b in enumerate(blank):
        if b and s is None:
            s = y
        elif not b and s is not None:
            if y - s >= min_len:
                runs.append((s, y - 1))
            s = None
    if s is not None and len(blank) - s >= min_len:
        runs.append((s, len(blank) - 1))
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--input-dir", default="capture_v3", help="含 full.png 的目录")
    ap.add_argument("--out-dir", required=True, help="新切片输出目录名")
    ap.add_argument("--slices", type=int, default=7)
    ap.add_argument("--cap-gap", type=int, default=120,
                    help="空白段在均衡度量中的封顶高度（默认120px）")
    args = ap.parse_args()

    base = Path(args.base)
    src = base / args.input_dir
    out = base / args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    img = Image.open(src / "full.png").convert("L")
    a = np.asarray(img, dtype=np.int16)
    h, w = a.shape
    print(f"full.png {w}x{h}")

    ink, bg = analyze(a)
    content = (ink >= MIN_INK_ROW).astype(np.int64)
    cum = np.cumsum(content)          # 累积内容行数
    total = int(cum[-1])
    print(f"背景={bg}  内容行总数={total}")

    runs = blank_runs(ink, MIN_GAP)
    print(f"可用空白段 {len(runs)} 个（>={MIN_GAP}px）")

    # 用"压缩坐标"做等分：
    # 真正决定幻灯片长短的是视觉跨度，不是墨量行数。
    # 图片/大模块会贡献几百行墨量却只是一个元素（v1 按墨量均分被它带偏）；
    # 未加载图片留下的大片空白又会白占高度。
    # 所以把超过 CAP_GAP 的空白段在度量上压缩到 CAP_GAP，再等分。
    CAP_GAP = args.cap_gap
    delta = np.zeros(h + 1, dtype=np.int64)
    for (s, e) in runs:
        shrink = max(0, (e - s + 1) - CAP_GAP)
        if shrink:
            delta[s + 1:] += shrink
    compressed = np.arange(h + 1, dtype=np.int64) - delta
    total_c = int(compressed[h])
    print(f"压缩后度量高度={total_c}（原 {h}，空白段封顶 {CAP_GAP}px）")

    n = args.slices
    cuts = [0]
    for i in range(1, n):
        target_c = total_c * i / n
        y_t = int(np.searchsorted(compressed, target_c))
        y_t = min(y_t, h - 1)

        # 在 y_t 附近找最近的空白段中心
        best, best_d = None, None
        for (s, e) in runs:
            c = (s + e) // 2
            d = abs(c - y_t)
            if d <= MAX_SNAP and (best_d is None or d < best_d):
                best, best_d = c, d
        y = best if best is not None else y_t

        # 保证间距
        y = max(y, cuts[-1] + MIN_SLICE)
        y = min(y, h - MIN_SLICE)
        cuts.append(y)
    cuts.append(h)
    cuts = sorted(set(cuts))

    print("新切口: " + ", ".join(f"{c}" for c in cuts))

    rgb = Image.open(src / "full.png").convert("RGB")
    for i, (t, b) in enumerate(zip(cuts[:-1], cuts[1:]), 1):
        rgb.crop((0, t, w, b)).save(out / f"slice_{i}.png")
        seg_ink = int(content[t:b].sum())
        print(f"  slice_{i}.png  y {t}-{b}  高{b - t}  内容行{seg_ink}")

    print(f"\n完成 -> {out}  ({len(cuts) - 1} 片)")


if __name__ == "__main__":
    main()
