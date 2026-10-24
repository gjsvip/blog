#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成站点默认 OG 分享图 assets/og-default.png（1200x630）。

设计：深色渐变底（与站点主题一致）+「渡劫博客」标题 + 副标题 + 波浪几何装饰。
中文渲染优先使用系统 Noto Sans CJK 字体；若字体缺失则退化为纯色底 +
几何图形 + ASCII 文本，绝不输出方块字（tofu）。

特性：
- 完全确定性输出（无随机元素），重复执行逐字节一致
- --check：仅校验磁盘产物是否为最新（供 CI 使用），不写入文件

用法：
    python3 scripts/gen_og_image.py            # 生成 assets/og-default.png
    python3 scripts/gen_og_image.py --check    # 校验产物是否最新，过期则退出码 2
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_FILE = ROOT / "assets" / "og-default.png"

WIDTH, HEIGHT = 1200, 630

#: 站点主题色（与 assets/style.css 保持一致）
BG_DEEP = (6, 9, 19)        # --bg-deep
BG_SOFT = (15, 21, 36)      # --bg-soft
TEXT_MAIN = (230, 237, 247)  # --text
TEXT_SUB = (154, 168, 192)   # --text-2
TEXT_DIM = (93, 107, 133)    # --text-3
ACCENT = (56, 189, 248)      # --accent
ACCENT_2 = (129, 140, 248)   # --accent-2

TITLE = "渡劫博客"
SUBTITLE = "独立开发者的技术自留地"
FOOTER = "www.520691.xyz"

#: 中文字体候选路径（按优先级排列），全部不存在则进入无字体降级模式
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",
]


def _load_fonts() -> tuple:
    """加载标题/副标题/脚注字体。返回 (title_font, sub_font, foot_font, ok)。

    找不到任何中文字体时返回 (None, None, None, False)，调用方进入降级绘制。
    """
    from PIL import ImageFont

    for path in FONT_CANDIDATES:
        if not Path(path).exists():
            continue
        try:
            title = ImageFont.truetype(path, 128)
            sub = ImageFont.truetype(path, 46)
            foot = ImageFont.truetype(path, 34)
            return title, sub, foot, True
        except OSError:
            continue
    return None, None, None, False


def _lerp(a: tuple, b: tuple, t: float) -> tuple:
    """线性插值两个 RGB 颜色。"""
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _draw_background(draw) -> None:
    """绘制对角渐变背景（左上 BG_DEEP -> 右下 BG_SOFT）。"""
    for y in range(HEIGHT):
        for_x_end = int(WIDTH * (1 - y / HEIGHT))
        row = _lerp(BG_DEEP, BG_SOFT, y / HEIGHT)
        draw.line([(0, y), (WIDTH, y)], fill=row)


def _draw_waves(draw) -> None:
    """绘制半透明波浪弧线装饰（渡劫博客的「🌊」意象）。"""
    for i, (cx, cy, r, color) in enumerate(
        [(160, 640, 320, ACCENT), (420, 660, 260, ACCENT_2), (1080, 60, 340, ACCENT_2)]
    ):
        alpha = 26 if i != 1 else 18
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=color + (alpha,),
            width=10,
        )


def _draw_pill(draw, font, text: str) -> None:
    """左上角绘制徽标胶囊：持续更新中 · 独立开发实录。"""
    label = "持续更新中 · 独立开发实录"
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 28, 14
    x0, y0 = 90, 96
    draw.rounded_rectangle(
        [x0, y0, x0 + tw + pad_x * 2, y0 + th + pad_y * 2],
        radius=(th + pad_y * 2) // 2,
        outline=ACCENT + (200,),
        width=2,
    )
    draw.text((x0 + pad_x, y0 + pad_y - bbox[1]), label, font=font, fill=ACCENT)


def render() -> bytes:
    """渲染 OG 图并返回 PNG 字节。"""
    import io

    from PIL import Image, ImageDraw

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_DEEP)
    draw = ImageDraw.Draw(img, "RGBA")
    _draw_background(draw)
    _draw_waves(draw)

    title_font, sub_font, foot_font, font_ok = _load_fonts()

    # 标题左侧装饰竖条
    draw.rounded_rectangle([90, 268, 98, 396], radius=4, fill=ACCENT)

    if font_ok:
        _draw_pill(draw, sub_font, "持续更新中 · 独立开发实录")
        draw.text((126, 258), TITLE, font=title_font, fill=TEXT_MAIN)
        draw.text((126, 430), SUBTITLE, font=sub_font, fill=TEXT_SUB)
        draw.text((126, 512), FOOTER, font=foot_font, fill=TEXT_DIM)
    else:
        # 无中文字体降级：几何图形 + ASCII 文本，避免方块字
        draw.rounded_rectangle([90, 96, 560, 150], radius=27, outline=ACCENT, width=3)
        draw.ellipse([108, 110, 134, 136], fill=ACCENT)
        draw.text((150, 106), "UPDATED REGULARLY", fill=ACCENT)
        draw.rounded_rectangle([90, 268, 98, 396], radius=4, fill=ACCENT)
        draw.text((126, 258), "dujie.dev", fill=TEXT_MAIN)
        draw.text((126, 430), "Indie developer tech blog", fill=TEXT_SUB)
        draw.text((126, 512), "www.520691.xyz", fill=TEXT_DIM)
        # 波浪降级为实心圆点阵
        for cx, cy in [(1010, 520), (1080, 440), (940, 440)]:
            draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=ACCENT + (160,))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def main(argv: list) -> int:
    """入口：生成或校验 OG 图。"""
    check_only = "--check" in argv
    data = render()
    if check_only:
        if not OUT_FILE.exists():
            print(f"[gen_og_image] {OUT_FILE.relative_to(ROOT)} 不存在", file=sys.stderr)
            return 2
        if OUT_FILE.read_bytes() != data:
            print(f"[gen_og_image] {OUT_FILE.relative_to(ROOT)} 与当前模板不一致，请重新生成", file=sys.stderr)
            return 2
        print(f"[gen_og_image] 校验通过：{OUT_FILE.relative_to(ROOT)} 为最新（{len(data)} 字节）")
        return 0
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_bytes(data)
    print(f"[gen_og_image] 生成 {OUT_FILE.relative_to(ROOT)}（{WIDTH}x{HEIGHT}，{len(data)} 字节）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
