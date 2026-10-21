#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""渡劫博客 SEO 产物生成器。

读取 posts.json（唯一事实源），确定性再生三个 SEO 产物：
- rss.xml            主域 RSS（pubDate 为合法 RFC-822，全部 ≤ 文章真实日期）
- sitemap.xml        主域 sitemap（无扩展名 URL 形态，与 canonical 一致）
- sitemap-github.xml GitHub Pages 端 sitemap（.html 形态）

设计纪律与 gen_posts.py 一致：
- 幂等：相同输入产生逐字节一致的输出，可重复执行
- 非破坏：保留现有文件中的频道元信息、静态页条目与历史文章的 link/guid 形态，
  只按 posts.json 刷新文章日期、排序与 lastmod，避免改变已发布 RSS 的 guid
- --check：仅校验磁盘产物是否为最新（供 CI 使用），不写入任何文件

用法：
    python3 scripts/gen_seo_files.py            # 再生三个产物
    python3 scripts/gen_seo_files.py --check    # 校验产物是否最新，过期则退出码 2
"""
from __future__ import annotations

import datetime
import json
import re
import sys
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_JSON = ROOT / "posts.json"
RSS_FILE = ROOT / "rss.xml"
SITEMAP_FILE = ROOT / "sitemap.xml"
SITEMAP_GH_FILE = ROOT / "sitemap-github.xml"

SITE_URL = "https://www.520691.xyz"
GH_PAGES_URL = "https://gjsvip.github.io/blog"

#: pubDate 统一使用东八区早八点，与既有产物保持一致
PUB_TZ = datetime.timezone(datetime.timedelta(hours=8))
PUB_HOUR = 8

#: 静态页 sitemap 条目（非文章页），按既有产物原样保留
STATIC_PAGES_MAIN = [
    ("/", "2026-10-21", "weekly", "1.0"),
    ("/archive", "2026-10-21", "weekly", "0.5"),
    ("/tags", "2026-10-21", "weekly", "0.5"),
    ("/says", "2026-10-21", "daily", "0.4"),
    ("/friends", "2026-10-21", "monthly", "0.4"),
    ("/about", "2026-10-21", "monthly", "0.4"),
]
STATIC_PAGES_GH = [
    ("/", "2026-10-21", "weekly", "0.9"),
    ("/archive.html", "2026-10-21", "weekly", "0.5"),
    ("/tags.html", "2026-10-21", "weekly", "0.5"),
    ("/says.html", "2026-10-21", "daily", "0.4"),
    ("/friends.html", "2026-10-21", "monthly", "0.4"),
    ("/about.html", "2026-10-21", "monthly", "0.4"),
]

ITEM_RE = re.compile(r"<item>.*?</item>", re.S)
LINK_RE = re.compile(r"<link>(.*?)</link>", re.S)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
GUID_RE = re.compile(r"<guid[^>]*>(.*?)</guid>", re.S)
CATEGORY_RE = re.compile(r"<category>(.*?)</category>", re.S)
DESCRIPTION_RE = re.compile(r"<description>(.*?)</description>", re.S)
LAST_BUILD_RE = re.compile(r"<lastBuildDate>.*?</lastBuildDate>", re.S)


def load_posts() -> list:
    """读取 posts.json 并按日期倒序返回（稳定排序，同日期保持文件内顺序）。"""
    data = json.loads(POSTS_JSON.read_text(encoding="utf-8"))
    posts = data.get("posts", [])
    if not posts:
        raise ValueError("posts.json 中没有任何文章")
    return sorted(posts, key=lambda p: p["date"], reverse=True)


def rfc822(date_iso: str) -> str:
    """把 ISO 日期转换为 RFC-822  pubDate（东八区 08:00:00）。"""
    d = datetime.date.fromisoformat(date_iso)
    dt = datetime.datetime(d.year, d.month, d.day, PUB_HOUR, 0, 0, tzinfo=PUB_TZ)
    return format_datetime(dt)


def slug_from_link(link: str) -> str:
    """从文章链接提取 slug（兼容无扩展名与 .html 两种形态）。"""
    tail = link.rstrip("/").rsplit("/", 1)[-1]
    return tail[:-5] if tail.endswith(".html") else tail


def parse_existing_items(text: str) -> dict:
    """解析现有 rss.xml，返回 slug -> 各字段原文字符串的映射（保留历史形态）。"""
    items: dict = {}
    for block in ITEM_RE.findall(text):
        link_m = LINK_RE.search(block)
        if not link_m:
            continue
        slug = slug_from_link(link_m.group(1))
        entry = {"link": link_m.group(1)}
        for name, regex in (
            ("title", TITLE_RE),
            ("guid", GUID_RE),
            ("category", CATEGORY_RE),
            ("description", DESCRIPTION_RE),
        ):
            m = regex.search(block)
            entry[name] = m.group(1) if m else ""
        items[slug] = entry
    return items


def render_rss(posts: list, existing_text: str) -> str:
    """基于现有 rss.xml 的频道头与条目字段，按 posts.json 刷新日期与排序。"""
    old_items = parse_existing_items(existing_text)
    channel_head = existing_text.split("<item>", 1)[0]
    newest = posts[0]["date"]
    channel_head = LAST_BUILD_RE.sub(
        f"<lastBuildDate>{rfc822(newest)}</lastBuildDate>", channel_head
    )
    blocks = []
    for meta in posts:
        slug = meta["slug"]
        old = old_items.get(slug, {})
        link = old.get("link", f"{SITE_URL}/posts/{slug}")
        guid = old.get("guid", link)
        title = old.get("title", meta["title"])
        category = old.get("category", meta.get("category", "随笔"))
        description = old.get("description", meta.get("excerpt", ""))
        blocks.append(
            "  <item>\n"
            f"    <title>{title}</title>\n"
            f"    <link>{link}</link>\n"
            f'    <guid isPermaLink="true">{guid}</guid>\n'
            f"    <pubDate>{rfc822(meta['date'])}</pubDate>\n"
            f"    <category>{category}</category>\n"
            f"    <description>{description}</description>\n"
            "  </item>"
        )
    # rstrip() 去掉 <item> 前的缩进空白，保证重复运行逐字节一致（幂等）
    head = channel_head.rstrip()
    return head + "\n" + "\n".join(blocks) + "\n</channel>\n</rss>\n"


def render_urlset(entries: list) -> str:
    """把 (loc, lastmod, changefreq, priority) 列表渲染为 urlset 行。"""
    return [
        f'  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod>'
        f"<changefreq>{cf}</changefreq><priority>{pri}</priority></url>"
        for loc, lastmod, cf, pri in entries
    ]


def render_sitemap(posts: list) -> str:
    """主域 sitemap：静态页 + 文章（无扩展名形态，与 canonical 一致）。"""
    entries = [
        (f"{SITE_URL}{path}", lm, cf, pri)
        for path, lm, cf, pri in STATIC_PAGES_MAIN
    ]
    entries += [
        (f"{SITE_URL}/posts/{p['slug']}", p["date"], "monthly", "0.8")
        for p in posts
    ]
    body = "\n".join(render_urlset(entries))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n</urlset>\n"
    )


def render_sitemap_github(posts: list) -> str:
    """GitHub Pages 端 sitemap：静态页 + 文章（.html 形态）。"""
    entries = [
        (f"{GH_PAGES_URL}{path}", lm, cf, pri)
        for path, lm, cf, pri in STATIC_PAGES_GH
    ]
    entries += [
        (f"{GH_PAGES_URL}/posts/{p['slug']}.html", p["date"], "monthly", "0.8")
        for p in posts
    ]
    body = "\n".join(render_urlset(entries))
    header = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<!--\n"
        "  GitHub Pages 端（https://gjsvip.github.io/blog/）专用 sitemap。\n"
        "  GitHub Pages 不支持无扩展名 URL，故此处一律使用 .html 形态。\n"
        "  主域 sitemap（sitemap.xml）只含 www.520691.xyz，两者互不混载。\n"
        "-->\n"
    )
    return (
        header
        + '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + f"{body}\n</urlset>\n"
    )


def build_outputs() -> dict:
    """生成全部三个产物的目标内容，返回 路径 -> 文本。"""
    posts = load_posts()
    rss_text = RSS_FILE.read_text(encoding="utf-8") if RSS_FILE.exists() else ""
    return {
        RSS_FILE: render_rss(posts, rss_text),
        SITEMAP_FILE: render_sitemap(posts),
        SITEMAP_GH_FILE: render_sitemap_github(posts),
    }


def main(argv: list) -> int:
    """入口：生成或校验 SEO 产物。"""
    check_only = "--check" in argv
    try:
        outputs = build_outputs()
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"[gen_seo] 生成失败: {exc}", file=sys.stderr)
        return 1

    exit_code = 0
    for path, content in outputs.items():
        if check_only:
            if not path.exists():
                print(f"[gen_seo] {path.name} 不存在", file=sys.stderr)
                exit_code = max(exit_code, 2)
            elif path.read_text(encoding="utf-8") != content:
                print(f"[gen_seo] {path.name} 与 posts.json 不同步", file=sys.stderr)
                exit_code = max(exit_code, 2)
        else:
            path.write_text(content, encoding="utf-8")
            print(f"[gen_seo] 生成 {path.relative_to(ROOT)}")
    if check_only:
        if exit_code == 0:
            print("[gen_seo] 校验通过：rss/sitemap 产物均为最新")
        else:
            print("[gen_seo] 产物过期，请执行 python3 scripts/gen_seo_files.py", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
