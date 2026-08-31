# -*- coding: utf-8 -*-
"""
make_preview.py - 生成技能描述用的预览素材图

产出（写到 assets/examples/）：
  presets.png        11 种边框配色套在同一页内容上的对比图（4 列网格）
  sample_cover.png   封面样例
  sample_page.png    内页样例（带卡片边框）

用途：README / 技能市场描述里的"效果预览"。

用法：
  python make_preview.py                       # 用默认样例内容
  python make_preview.py --slide <某张 slide>   # 指定用来演示的内容页
  python make_preview.py --cover <封面图>
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SKILL = Path(__file__).resolve().parent.parent
EXAMPLES = SKILL / "assets" / "examples"

FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
FONT_REG = r"C:\Windows\Fonts\msyh.ttc"

from add_border import PRESETS, hex_to_rgb, make_card_frame, process_slide  # noqa: E402

BG = (248, 249, 251)
INK = (33, 37, 41)
MUTED = (108, 117, 125)


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def build_presets_sheet(slide_path, out_path, cols=4, cell_w=380, cell_h=700):
    """把 11 种配色套到同一页内容上，拼成对比图"""
    src = Image.open(slide_path).convert("RGB")

    names = list(PRESETS.keys())
    rows = (len(names) + cols - 1) // cols

    f_title = _font(FONT_BOLD, 40)
    f_sub = _font(FONT_REG, 22)
    f_tag = _font(FONT_BOLD, 24)
    f_note = _font(FONT_REG, 19)

    head_h = 130
    foot_h = 70
    pad = 46
    W = pad * 2 + cols * cell_w
    H = head_h + pad + rows * cell_h + foot_h

    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    d.text((pad, 44), "边框配色 preset 一览", font=f_title, fill=INK)
    d.text((pad, 96), "同一页内容套 11 套配色，--preset <名字> 即可切换",
           font=f_sub, fill=MUTED)

    for i, name in enumerate(names):
        bg_hex, dash_hex, desc = PRESETS[name]
        bg = hex_to_rgb(bg_hex)
        dash = hex_to_rgb(dash_hex)

        # 内容缩到格子宽度，再套卡片
        tw = cell_w - 110
        k = tw / src.width
        thumb = src.resize((tw, int(src.height * k)), Image.LANCZOS)
        if thumb.height > cell_h - 210:
            k2 = (cell_h - 210) / thumb.height
            thumb = thumb.resize((int(thumb.width * k2), cell_h - 210), Image.LANCZOS)

        card = make_card_frame(thumb, bg, dash, corner_radius=14,
                               outer_pad=11, inner_pad=7)

        cx = pad + (i % cols) * cell_w
        cy = head_h + pad + (i // cols) * cell_h
        sx = cx + (cell_w - card.width) // 2
        sheet.paste(card, (sx, cy))

        ty = cy + card.height + 18
        d.text((cx, ty), name, font=f_tag, fill=INK)
        # 描述可能较长，按宽度截断
        note = desc
        while d.textlength(note, font=f_note) > cell_w - 20:
            note = note[:-1]
        d.text((cx, ty + 32), note, font=f_note, fill=MUTED)

    d.text((pad, H - foot_h + 18),
           "外层圆角底 + 白色内容区 + 内虚线。也支持 --bg-color / --dash-color 直接给色值",
           font=f_note, fill=MUTED)

    EXAMPLES.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=95)
    print(f"  -> {out_path}  {sheet.size}")
    return out_path


def build_sample(cover_path, frame_path, out_cover, out_page, width=520):
    """封面样例 + 内页样例并排，展示最终成片效果"""
    cover = Image.open(cover_path).convert("RGB")
    frame = Image.open(frame_path).convert("RGB")

    k = width / cover.width
    c2 = cover.resize((width, int(cover.height * k)), Image.LANCZOS)
    p2 = frame.resize((width, int(frame.height * k)), Image.LANCZOS)

    pad = 40
    gap = 36
    head_h = 96
    h = max(c2.height, p2.height)
    W = pad * 2 + width * 2 + gap
    H = head_h + h + pad

    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    d.text((pad, 34), "成片效果", font=_font(FONT_BOLD, 38), fill=INK)
    d.text((pad, 78), "左：封面（标题自动取自文章）　右：内页（截图 + 卡片边框）",
           font=_font(FONT_REG, 20), fill=MUTED)

    sheet.paste(c2, (pad, head_h))
    sheet.paste(p2, (pad + width + gap, head_h))

    EXAMPLES.mkdir(parents=True, exist_ok=True)
    sheet.save(out_page, quality=95)
    print(f"  -> {out_page}  {sheet.size}")

    c2.save(out_cover, quality=95)
    print(f"  -> {out_cover}  {c2.size}")
    return out_page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slide", default=None, help="用于演示配色的内容页")
    ap.add_argument("--cover", default=None, help="封面样例")
    ap.add_argument("--frame", default=None, help="带边框的内页样例")
    args = ap.parse_args()

    work = Path(r"C:\Users\Lenovo\WorkBuddy\2026-08-28-11-52-14\zh2_out")
    slide = Path(args.slide) if args.slide else work / "screenshots" / "slide_2.png"
    cover = Path(args.cover) if args.cover else work / "cover.png"
    frame = Path(args.frame) if args.frame else work / "video_frames" / "frame_2.png"

    print("生成预览素材：")
    if slide.exists():
        build_presets_sheet(slide, EXAMPLES / "presets.png")
    else:
        print(f"  [跳过] presets.png —— 找不到 {slide}")

    if cover.exists() and frame.exists():
        build_sample(cover, frame, EXAMPLES / "sample_cover.png",
                     EXAMPLES / "sample_page.png")
    else:
        print(f"  [跳过] 样张 —— 缺 {cover} 或 {frame}")

    print("\n完成")


if __name__ == "__main__":
    main()
