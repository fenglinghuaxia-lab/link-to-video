# -*- coding: utf-8 -*-
"""
make_cover_preview.py - 生成「11 种封面配色」对比图

同一个标题套 11 套封面配色，拼成一张图，方便直接挑。
配色名与 add_border.py 的边框预设一一对应，选了哪个边框就用同名封面。

用法：
  python scripts/make_cover_preview.py
  python scripts/make_cover_preview.py --title "自定义标题" --cols 3 --thumb-w 360
输出：
  assets/examples/cover_themes.png
"""
import argparse
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SKILL = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from make_final import THEMES, THEME_DESC, make_cover, W, H  # noqa: E402

FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
FONT_REG = r"C:\Windows\Fonts\msyh.ttc"

# 与 add_border.py 预设同名、能和边框配套的那些（排除旧版 dark / light）
PRESET_ORDER = ["deepblue", "navy", "mint", "warm", "lavender", "gold",
                "crimson", "teal", "slate", "sand", "plain"]


def build(out_path, title, subtitle, author, cols, thumb_w, bg=None):
    items = [k for k in PRESET_ORDER if k in THEMES]
    thumb_h = int(thumb_w * H / W)
    rows = (len(items) + cols - 1) // cols

    label_h = 100
    gap = 24
    margin = 30
    head_h = 90

    cw = thumb_w + gap
    ch = thumb_h + label_h + gap
    sheet_w = margin * 2 + cols * cw - gap
    sheet_h = margin * 2 + head_h + rows * ch - gap

    sheet = Image.new("RGB", (sheet_w, sheet_h), (247, 248, 250))
    d = ImageDraw.Draw(sheet)
    f_head = ImageFont.truetype(FONT_BOLD, 40)
    f_name = ImageFont.truetype(FONT_BOLD, 30)
    f_hex = ImageFont.truetype(FONT_REG, 21)
    f_desc = ImageFont.truetype(FONT_REG, 22)

    d.text((margin, 26), "封面配色（与边框预设同名，建议配套使用）",
           font=f_head, fill=(23, 33, 48))

    tmp = Path(tempfile.mkdtemp(prefix="coverprev_"))
    for i, key in enumerate(items):
        p = tmp / f"{key}.png"
        make_cover(p, title, subtitle, author, key, bg=bg)
        thumb = Image.open(p).convert("RGB").resize((thumb_w, thumb_h), Image.LANCZOS)

        r, c = divmod(i, cols)
        x = margin + c * cw
        y = margin + head_h + r * ch
        sheet.paste(thumb, (x, y))

        # 浅色封面（如 plain）在白底上会糊，加一圈描边
        d.rectangle((x - 1, y - 1, x + thumb_w, y + thumb_h),
                    outline=(210, 214, 222), width=1)

        ly = y + thumb_h + 12
        ar, ag, ab = THEMES[key]["accent"]
        # 第一行：配色名 + 色值（挤同一行，窄列也放得下）
        d.text((x, ly), key, font=f_name, fill=(23, 33, 48))
        kw = d.textlength(key, font=f_name)
        d.text((x + kw + 12, ly + 9), f"#{ar:02X}{ag:02X}{ab:02X}",
               font=f_hex, fill=(140, 150, 165))
        # 第二行：中文说明；砍掉括号里的适用场景，300px 列宽放不下完整描述
        d.text((x, ly + 42), THEME_DESC.get(key, "").split("（")[0],
               font=f_desc, fill=(110, 122, 138))

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    print(f"封面配色预览图: {out_path}")
    print(f"  {sheet_w}x{sheet_h}   {len(items)} 套配色")
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(SKILL / "assets" / "examples" / "cover_themes.png"))
    ap.add_argument("--title", default="一个链接，五分钟变成一条视频")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--author", default="期权Z叔")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--thumb-w", type=int, default=300)
    ap.add_argument("--bg", default=None, help="封面背景图（不填则用纯色渐变，配色看得更清楚）")
    args = ap.parse_args()
    build(args.out, args.title, args.subtitle, args.author,
          args.cols, args.thumb_w, args.bg)


if __name__ == "__main__":
    main()
