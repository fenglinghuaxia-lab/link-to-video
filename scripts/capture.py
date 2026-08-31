# -*- coding: utf-8 -*-
"""
capture.py - 用手机视口打开文章链接，整页截图并按段落边界切成 N 张切片
用法:
  python capture.py <url> --out <workdir> [--slices 5] [--selector CSS] [--scale 3]
产出: <workdir>/full.png, <workdir>/slice_1.png ... slice_N.png, <workdir>/meta.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

# 知乎常见的登录弹窗 / 引导浮层选择器，截图前移除
OVERLAY_SELECTORS = [
    ".Modal-wrapper",
    ".modal-wrapper",
    "div[role='dialog']",
    ".OpenInAppButton",
    ".MStoolsTip-banner",
    ".AdblockBanner",
    "body > div:not([id]):not([class])",  # 兜底不动，避免误删
]

# 正文里混入的互动/推荐类元素，截图前移除（否则会切进视频画面）
JUNK_SELECTORS = [
    ".ContentItem-actions",   # 点赞/评论/收藏互动栏
    ".ContentItem-action",
    ".Reward",                # 赞赏
    ".Voters",                # 赞同者列表
    ".Comments", ".Comment",  # 评论区
    ".RelatedReadings",       # 推荐阅读
    ".AppHeader", "header",   # 顶部导航/搜索框
    ".FollowButton", ".VoteButton",
]

CONTENT_SELECTORS = [
    "#js_content",                       # 微信公众号文章正文（优先）
    ".Post-RichTextContainer",          # 知乎专栏文章正文
    "div.RichText.ztext.Post-RichText", # 专栏正文(旧)
    ".AnswerItem .RichContent-inner .RichText",  # 回答正文
    ".AnswerItem .RichText",
    "article",
]


def slugify(text: str, maxlen: int = 24) -> str:
    text = re.sub(r"[\\/:*?\"<>|\s]+", "-", text).strip("-")
    return text[:maxlen] or "article"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--out", required=True, help="工作目录，存放切片产物")
    ap.add_argument("--slices", type=int, default=5)
    ap.add_argument("--selector", default=None, help="手动指定正文容器 CSS 选择器")
    ap.add_argument("--scale", type=int, default=3, help="设备像素比(截图清晰度)")
    ap.add_argument("--wait", type=float, default=2.0, help="页面加载后额外等待秒数")
    ap.add_argument("--storage-state", default=None, help="知乎登录态 JSON(用 --login 生成后复用)")
    ap.add_argument("--login", action="store_true", help="打开登录窗口, 手动扫码后将登录态保存为 storage_state.json")
    args = ap.parse_args()

    state_file = Path(args.storage_state) if args.storage_state else \
        Path(__file__).resolve().parent.parent / "assets" / "storage_state.json"

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=not args.login,  # 登录模式需要有头窗口供扫码
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        # 有登录态文件则复用(知乎未登录会重定向回首页)
        ctx_kwargs = {}
        if not args.login and state_file.exists():
            ctx_kwargs["storage_state"] = str(state_file)
            print(f"[capture] 使用登录态: {state_file}")
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=args.scale,
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            ),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            **ctx_kwargs,
        )
        # 隐藏 webdriver 痕迹，降低反爬概率
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        page = ctx.new_page()
        # 登录模式: 打开知乎登录页等用户手动扫码, 保存登录态后退出
        if args.login:
            page.goto("https://www.zhihu.com/signin", wait_until="domcontentloaded", timeout=60000)
            print("[capture] 已打开登录页, 请在浏览器中手动登录(最多等 3 分钟)...")
            for _ in range(90):
                try:
                    if page.query_selector("img.Avatar, .AppHeader-userInfo"):
                        break
                except Exception:
                    pass
                page.wait_for_timeout(2000)
            state_file.parent.mkdir(parents=True, exist_ok=True)
            ctx.storage_state(path=str(state_file))
            print(f"[capture] 登录态已保存: {state_file}")
            browser.close()
            return
        page.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        })
        # 仅知乎链接需要先访问首页建立 Cookie 上下文，再跳转目标文章
        if "zhihu.com" in args.url:
            page.goto("https://www.zhihu.com", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)
        page.goto(args.url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(int(args.wait * 1000))

        # 滚动到底触发懒加载图片，再回顶部
        page.evaluate(
            """
            async () => {
                const delay = ms => new Promise(r => setTimeout(r, ms));
                const h = () => document.body.scrollHeight;
                let last = 0;
                window.scrollTo(0, 0);
                await delay(300);
                for (let y = 0; y < h(); y += 700) {
                    window.scrollTo(0, y);
                    await delay(150);
                }
                await delay(400);
                window.scrollTo(0, 0);
                await delay(400);
            }
            """
        )

        # 强制加载懒加载图片：
        # 微信公众号/知乎把真实地址放在 data-src / data-original 上，靠滚动触发。
        # 触发失败时图片会渲染成"整宽、几百px高、灰度恒定的浅灰占位块"，
        # 截图后就是一大片空白 —— 只能靠像素分析发现，肉眼很难定位。
        # 症状：full.png 里出现整宽、高度 300~1000px、灰度 247 且零对比度的纯色块。
        forced = page.evaluate(
            """
            () => {
                const ATTRS = ['data-src', 'data-original', 'data-actualsrc',
                               'data-lazy-src', 'data-echo'];
                const imgs = Array.from(document.querySelectorAll('img'));
                let n = 0;
                imgs.forEach(img => {
                    const cur = img.getAttribute('src') || '';
                    if (cur && !cur.startsWith('data:')) return;
                    for (const a of ATTRS) {
                        const v = img.getAttribute(a);
                        if (v && (v.startsWith('http') || v.startsWith('//'))) {
                            img.setAttribute('src', v);
                            img.removeAttribute('data-lazy-src');
                            n++;
                            break;
                        }
                    }
                });
                return {total: imgs.length, forced: n};
            }
            """
        )
        try:
            page.wait_for_function(
                """
                () => Array.from(document.querySelectorAll('img'))
                    .filter(i => {
                        const s = i.getAttribute('src');
                        return s && !s.startsWith('data:');
                    })
                    .every(i => i.complete && i.naturalWidth > 0)
                """,
                timeout=15000,
            )
            img_state = "全部加载完成"
        except Exception:
            img_state = "有图片加载超时（可能仍是占位块）"
        print(f"[capture] 图片: 共{forced['total']}张, 强制加载{forced['forced']}张, {img_state}")
        page.wait_for_timeout(800)

        # 移除登录弹窗/浮层
        page.evaluate(
            """
            (sels) => {
                for (const s of sels) {
                    try { document.querySelectorAll(s).forEach(e => e.remove()); } catch (e) {}
                }
                document.documentElement.style.overflow = 'auto';
                document.body.style.overflow = 'auto';
            }
            """,
            [s for s in OVERLAY_SELECTORS if "body >" not in s],
        )

        # 移除正文里的互动栏/评论区/推荐位（知乎把这些塞在正文容器附近，会混进切片）
        page.evaluate(
            """
            (sels) => {
                for (const s of sels) {
                    try { document.querySelectorAll(s).forEach(e => e.remove()); } catch (e) {}
                }
                // 移除所有 fixed/sticky 定位元素（顶部导航、底部悬浮栏）
                document.querySelectorAll('body *').forEach(el => {
                    try {
                        const pos = window.getComputedStyle(el).position;
                        if (pos === 'fixed' || pos === 'sticky') el.remove();
                    } catch (e) {}
                });
            }
            """,
            JUNK_SELECTORS,
        )

        # 修复加粗失效：
        # 知乎移动端把 <b>/<strong> 设为 font-weight:500(Medium)。Windows 没有 PingFang SC，
        # 回退到微软雅黑后只有 400/700 两个字重，500 会就近回退到 400 → 加粗消失。
        # 解决：把 500~699 的字重强制提升到 700，让浏览器用真正的 Bold 字重。
        page.evaluate(
            """
            () => {
                const roots = document.querySelectorAll(
                    '.Post-RichTextContainer, .RichText.ztext.Post-RichText, article'
                );
                roots.forEach(root => {
                    root.querySelectorAll('b, strong').forEach(el => {
                        el.style.setProperty('font-weight', '700', 'important');
                    });
                    root.querySelectorAll('*').forEach(el => {
                        const fw = parseInt(window.getComputedStyle(el).fontWeight) || 400;
                        if (fw >= 500 && fw < 700) {
                            el.style.setProperty('font-weight', '700', 'important');
                        }
                    });
                });
            }
            """
        )
        page.wait_for_timeout(500)

        # 定位正文容器
        root = None
        if args.selector:
            root = page.query_selector(args.selector)
        if root is None:
            for sel in CONTENT_SELECTORS:
                root = page.query_selector(sel)
                if root:
                    break
        if root is None:
            print("[capture] 未找到正文容器，回退为整页截图", file=sys.stderr)
            root = page.query_selector("body")

        # 元信息
        title = page.title()
        try:
            h1 = page.query_selector("h1")
            if h1:
                title = (h1.inner_text() or title).strip()
        except Exception:
            pass
        author = ""
        for sel in (".AuthorInfo-name", "meta[name='author']"):
            try:
                el = page.query_selector(sel)
                if el:
                    author = el.get_attribute("content") or el.inner_text() or ""
                    author = author.strip()
                    if author:
                        break
            except Exception:
                pass

        root.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        root.screenshot(path=str(outdir / "full.png"))

        # 计算段落边界（相对正文容器顶部）
        rects = root.evaluate(
            """
            el => {
                const base = el.getBoundingClientRect();
                const out = [];
                el.querySelectorAll('p,h1,h2,h3,h4,h5,blockquote,figure,img,ul,ol,pre,hr,table').forEach(n => {
                    const r = n.getBoundingClientRect();
                    if (r.height < 8) return;
                    const top = r.top - base.top, bottom = r.bottom - base.top;
                    if (top >= 0 && bottom <= base.height + 50) out.push([top, bottom]);
                });
                out.sort((a, b) => a[0] - b[0]);
                return {height: base.height, rects: out};
            }
            """
        )
        body_h = rects["height"]
        block_bounds = [b for _, b in rects["rects"]]

        print(f"[capture] 正文高度(CSS px) = {body_h}, 标题 = {title}, 作者 = {author or '(未知)'}")

        # 按 N 等分目标找最近段落边界作为切点
        n = max(1, args.slices)
        cuts = [0.0]
        for i in range(1, n):
            target = body_h * i / n
            if block_bounds:
                win = body_h / (2 * n)
                cands = [b for b in block_bounds if abs(b - target) <= win]
                if cands:
                    cut = min(cands, key=lambda b: abs(b - target))
                else:
                    cut = target
            else:
                cut = target
            # 保证切点严格递增且不贴边
            if cut > cuts[-1] + 40 and cut < body_h - 40:
                cuts.append(cut)
        cuts.append(body_h)
        cuts.sort()
        slices = [
            (cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1)
        ]
        print(f"[capture] 实际切 {len(slices)} 片: " + ", ".join(f"{a:.0f}-{b:.0f}" for a, b in slices))

        # PIL 裁切（full.png 是 scale 倍图）
        from PIL import Image

        img = Image.open(outdir / "full.png")
        for idx, (top, bottom) in enumerate(slices, 1):
            y0 = max(0, int(top * args.scale) - 6)
            y1 = min(img.height, int(bottom * args.scale) + 6)
            crop = img.crop((0, y0, img.width, y1))
            crop.save(outdir / f"slice_{idx}.png")
        print(f"[capture] 完成: {len(slices)} 张切片 -> {outdir}")

        (outdir / "meta.json").write_text(
            json.dumps(
                {
                    "url": args.url,
                    "title": title,
                    "author": author,
                    "slices": len(slices),
                    "slice_files": [f"slice_{i}.png" for i in range(1, len(slices) + 1)],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        browser.close()


if __name__ == "__main__":
    import os
    code = 0
    try:
        main()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 0
    except BaseException:
        import traceback
        traceback.print_exc()
        code = 1
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)  # 规避 playwright 同步 API 退出阶段 greenlet 清理报错
