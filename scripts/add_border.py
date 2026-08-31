# -*- coding: utf-8 -*-
"""
add_border_v2.py - 卡片式边框（参考用户提供的样式）
特点：
  - 外层：浅色圆角背景（薄荷绿/青色调）
  - 内层：白色内容区 + 细虚线内边框
  - 整体效果：像一张便签卡片
输入: screenshots/slide_*.png
输出: video_frames/frame_*.png (带卡片边框的1080x1920画布)
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw

# 边框配色预设。
# 选色原则：低饱和、不抢文字、与白色内容区有足够对比但不刺眼。
# 用户偏好：深蓝黑底 + 低饱和暖/冷叠加、禁霓虹色。
PRESETS = {
    "deepblue":  ("#7FA8D4", "#5A82B0", "深蓝 · 专业商务（默认，金融/科技）"),
    "navy":      ("#5B7FA6", "#3E5C7E", "藏青 · 沉稳权威（财经分析/研报）"),
    "mint":      ("#D8EDE5", "#A8C9BC", "薄荷绿 · 清新自然（教育/读书/生活）"),
    "warm":      ("#E8D5C4", "#C4A484", "暖棕 · 温暖文艺（随笔/故事/情感）"),
    "lavender":  ("#DDD6EB", "#B0A0CC", "淡紫 · 优雅高级（艺术/设计/女性向）"),
    "gold":      ("#F0E4C8", "#C9A961", "香槟金 · 高端质感（品牌/奢侈品/年终）"),
    "crimson":   ("#F2DADA", "#C08080", "朱红 · 热烈醒目（行情/节日/促销）"),
    "teal":      ("#D2E8E6", "#7FA8A4", "青碧 · 冷静科技（医疗/制造/数据）"),
    "slate":     ("#DDE1E6", "#9AA4B0", "石墨灰 · 中性理性（资讯/干货/通用）"),
    "sand":      ("#EDE4D3", "#BFAA8A", "米杏 · 柔和耐看（长文/连载/日更）"),
    "plain":     ("#FFFFFF", "#DDDDDD", "无框 · 极简白（不抢任何设计）"),
}


def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join(c * 2 for c in hex_str)
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))


def make_card_frame(img, bg_color, dash_color, corner_radius=24,
                    outer_pad=20, inner_pad=12):
    """
    把图片放到一个卡片框架里：
    - 外层：bg_color 圆角矩形背景
    - 中层：白色内容区
    - 内层：dash_color 虚线边框
    """
    img_w, img_h = img.size

    # 计算各层尺寸
    # 外层尺寸 = 图片 + 内边距*2 + 白色区padding*2 + 外边距*2
    white_pad = 18   # 白色区域比图片多出的内边距
    total_w = img_w + inner_pad * 2 + white_pad * 2 + outer_pad * 2
    total_h = img_h + inner_pad * 2 + white_pad * 2 + outer_pad * 2

    # 创建外层（圆角背景）
    card = Image.new("RGB", (total_w, total_h), bg_color)

    # 绘制圆角矩形遮罩来裁剪成圆角
    mask = Image.new("L", (total_w, total_h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(
        [0, 0, total_w - 1, total_h - 1],
        radius=corner_radius,
        fill=255
    )

    # 白色内容区（圆角稍小一点）
    white_x = outer_pad
    white_y = outer_pad
    white_w = total_w - outer_pad * 2
    white_h = total_h - outer_pad * 2
    white_r = max(corner_radius - 6, 4)

    card_draw = ImageDraw.Draw(card)
    card_draw.rounded_rectangle(
        [white_x, white_y, white_x + white_w - 1, white_y + white_h - 1],
        radius=white_r,
        fill=(255, 255, 255)
    )

    # 虚线内边框（在白色区域内，距离边缘 inner_pad）
    dash_margin = inner_pad + white_pad // 2
    dash_x = white_x + dash_margin
    dash_y = white_y + dash_margin
    dash_w = white_w - dash_margin * 2
    dash_h = white_h - dash_margin * 2
    dash_r = max(white_r - 4, 2)

    # PIL 不直接支持虚线，用小短线模拟
    draw_dashed_rect(card_draw, dash_x, dash_y, dash_x + dash_w, dash_y + dash_h,
                     dash_r, dash_color, dash=(6, 4))

    # 粘贴原图到中心
    paste_x = white_x + white_pad
    paste_y = white_y + white_pad
    card.paste(img, (paste_x, paste_y))

    return card


def draw_dashed_rect(draw, x1, y1, x2, y2, radius, color, dash=(6, 4)):
    """绘制圆角虚线矩形"""
    gap, length = dash

    def draw_line(xa, ya, xb, yb):
        """画一条虚线段"""
        import math
        dx = xb - xa
        dy =yb - ya
        dist = math.sqrt(dx*dx + dy*dy)
        if dist == 0:
            return
        ux, uy = dx/dist, dy/dist
        pos = 0.0
        drawing = True
        while pos < dist:
            seg_len = length if drawing else gap
            end_pos = min(pos + seg_len, dist)
            sx = xa + ux * pos
            sy = ya + uy * pos
            ex = xa + ux * end_pos
            ey = ya + uy * end_pos
            if drawing:
                draw.line([(int(sx), int(sy)), (int(ex), int(ey))], fill=color, width=1)
            pos = end_pos
            drawing = not drawing

    r = radius
    # 四条边（简化：直线部分，角落用短弧代替或跳过）
    # 上边
    draw_line(x1 + r, y1, x2 - r, y1)
    # 下边
    draw_line(x1 + r, y2, x2 - r, y2)
    # 左边
    draw_line(x1, y1 + r, x1, y2 - r)
    # 右边
    draw_line(x2, y1 + r, x2, y2 - r)


def process_slide(src_path, dst_path, bg_color, dash_color,
                  canvas_size=(1080, 1920), target_width=860):
    """处理单张截图 -> 带卡片边框的画布帧"""
    img = Image.open(src_path).convert("RGB")

    # 缩放
    if img.width != target_width:
        scale = target_width / img.width
        new_h = int(img.height * scale)
        img = img.resize((target_width, new_h), Image.LANCZOS)

    # 自动收缩：卡片 = 图片 + CARD_PAD(88)px，四周再留 BREATH px 呼吸位
    CARD_PAD = (10 + 18 + 16) * 2   # inner_pad + white_pad + outer_pad，双向
    BREATH = 40
    max_img_h = canvas_size[1] - CARD_PAD - BREATH
    max_img_w = canvas_size[0] - CARD_PAD - BREATH
    if img.height > max_img_h or img.width > max_img_w:
        k = min(max_img_h / img.height, max_img_w / img.width)
        img = img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))),
                         Image.LANCZOS)

    # 加卡片边框
    card = make_card_frame(img, bg_color, dash_color,
                           corner_radius=20, outer_pad=16, inner_pad=10)

    # 居中到画布
    canvas = Image.new("RGB", canvas_size, (245, 247, 250))  # 浅灰蓝背景
    paste_x = (canvas_size[0] - card.width) // 2
    paste_y = (canvas_size[1] - card.height) // 2
    canvas.paste(card, (paste_x, paste_y))

    canvas.save(dst_path, quality=95)
    return canvas.size, card.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=False, default=".",
                    help="工作目录（含 screenshots/ 和 video_frames/）")
    ap.add_argument("--preset", default="deepblue", choices=list(PRESETS),
                    help="配色预设名（--list-presets 查看全部）")
    ap.add_argument("--bg-color", default=None, help="外层背景色，覆盖预设")
    ap.add_argument("--dash-color", default=None, help="虚线颜色，覆盖预设")
    ap.add_argument("--target-width", type=int, default=860)
    ap.add_argument("--list-presets", action="store_true", help="列出所有预设并退出")
    args = ap.parse_args()

    if args.list_presets:
        print("边框配色预设：\n")
        for k, (bg, dash, desc) in PRESETS.items():
            print(f"  {k:10s} 外{bg}  虚{dash}   {desc}")
        print("\n用法: --preset navy   或   --preset navy --dash-color '#2E4A6B'")
        return

    bg_default, dash_default, desc = PRESETS[args.preset]
    bg_color = hex_to_rgb(args.bg_color or bg_default)
    dash_color = hex_to_rgb(args.dash_color or dash_default)

    base = Path(args.workdir)
    src_dir = base / "screenshots"
    dst_dir = base / "video_frames"
    dst_dir.mkdir(parents=True, exist_ok=True)

    # 注意：不主动删除旧 frame_*（沙箱可能禁止删除）。
    # 数量变少时的残留由 make_final.py 按 screenshots/ 数量截断处理。

    # 自然序排序：字符串排序会让 slide_10 排到 slide_2 前面
    slides = sorted(src_dir.glob("slide_*.png"),
                    key=lambda p: int("".join(c for c in p.stem if c.isdigit()) or 0))

    print(f"工作目录: {base}")
    print(f"配色: {args.preset} — {desc}")
    print(f"  外层 {args.bg_color or bg_default}   虚线 {args.dash_color or dash_default}")
    print(f"目标宽度: {args.target_width}px\n")

    for i, sp in enumerate(slides, 1):
        dst = dst_dir / f"frame_{i}.png"
        csz, isz = process_slide(str(sp), str(dst), bg_color, dash_color,
                                  target_width=args.target_width)
        print(f"  frame_{i}.png  卡片 {isz[0]}x{isz[1]} -> 画布 {csz[0]}x{csz[1]}")

    print(f"\n完成！{len(slides)} 张已加边框")


if __name__ == "__main__":
    main()
