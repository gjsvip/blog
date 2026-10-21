#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""渡劫博客文章生成器。

读取仓库根目录的 posts.json（集中元数据）与 posts/<slug>.body.html（正文 HTML），
套用与既有文章页完全一致的模板，生成 posts/<slug>.html。

特性：
- 幂等：相同输入产生逐字节一致的输出，可重复执行，无时间戳等不确定因素
- --check：仅校验磁盘产物是否为最新（供 CI 使用），不写入任何文件
- 强校验：slug 格式、日期格式、必需字段、正文非空、中文字数下限（告警）

SEO 注入（每篇文章页）：
- BlogPosting + BreadcrumbList 双 JSON-LD 结构化数据
- og:image / twitter:card 等 OG 与 Twitter 分享标签

用法：
    python3 gen_posts.py            # 生成全部文章
    python3 gen_posts.py --check    # 校验产物是否最新，过期则退出码 2
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POSTS_JSON = ROOT / "posts.json"
POSTS_DIR = ROOT / "posts"

#: slug 只允许小写字母、数字与连字符
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
#: 日期必须是 ISO 格式 YYYY-MM-DD
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
#: 单篇正文的中文字数下限（新文章要求 ≥ 1200 字；历史遗留短文仅告警）
MIN_CJK_CHARS = 1200
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

SITE_NAME = "渡劫博客"
SITE_URL = "https://www.520691.xyz"
AUTHOR = "gjsvip · 渡劫"
#: 作者 Person 实体统一指向关于页（结构化数据 author.url）
AUTHOR_URL = f"{SITE_URL}/about"
#: 默认 OG 分享图（1200x630，由 scripts/gen_og_image.py 生成）
OG_IMAGE = f"{SITE_URL}/assets/og-default.png"
FAVICON = (
    "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
    "<text y='.9em' font-size='90'>🌊</text></svg>"
)

#: 文章页完整模板。占位符形如 __TITLE__，统一用 str.replace 替换，
#: 避免 str.format 与正文中的大量花括号冲突。
PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__ · 渡劫博客</title>
<meta name="description" content="__EXCERPT__">
<meta name="author" content="__AUTHOR__">
<meta property="og:title" content="__TITLE__ · 渡劫博客">
<meta property="og:description" content="__EXCERPT__">
<meta property="og:type" content="article">
<meta property="og:site_name" content="__SITE_NAME__">
<meta property="og:url" content="__CANONICAL__">
<meta property="og:image" content="__OG_IMAGE__">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="__TITLE__ · 渡劫博客">
<meta name="twitter:description" content="__EXCERPT__">
<meta name="twitter:image" content="__OG_IMAGE__">
<link rel="canonical" href="__CANONICAL__">
<link rel="stylesheet" href="../assets/style.css?v=20261021b">
<link rel="alternate" type="application/rss+xml" title="渡劫博客 RSS" href="../rss.xml">
<link rel="icon" href="__FAVICON__">
__JSONLD__
</head>
<body>
<div id="progress-bar"></div>

<header class="site-header">
  <div class="header-inner">
    <a class="logo" href="../index.html">
      <span class="logo-badge">🌊</span>渡劫博客<small>dujie.dev</small>
    </a>
    <nav class="nav">
      <a href="../index.html">首页</a>
      <a href="../archive.html">归档</a>
      <a href="../tags.html">标签</a>
      <a href="../says.html">说说</a>
      <a href="../friends.html">友链</a>
      <a href="../about.html">关于</a>
    </nav>
    <div class="header-actions">
      <button class="search-trigger" aria-label="搜索文章">
        <span>🔍</span><span>搜索文章…</span><kbd>Ctrl K</kbd>
      </button>
      <button class="icon-btn theme-toggle" aria-label="切换主题">☀️</button>
      <button class="icon-btn menu-toggle" aria-label="菜单">☰</button>
    </div>
  </div>
</header>

<main class="layout has-side">
  <div>
    <div class="breadcrumb"><a href="../index.html">首页</a><span class="sep">/</span><a href="../archive.html">归档</a><span class="sep">/</span>__TITLE__</div>

    <article>
      <div class="article-header">
        <h1>__TITLE__</h1>
        <div class="article-meta">
          <span class="avatar-mini">🌊</span>
          <span class="who">渡劫 · gjsvip</span>
          <span>📅 __DATE__</span>
          <span>📂 __CATEGORY__</span>
        </div>
      </div>

      <div class="article-cover" aria-hidden="true">__COVER__</div>

      <div class="article-body">
__BODY__
      </div>

      <div class="article-actions">
        <button class="like-btn" id="like-btn"><span class="heart">❤️</span><span>点赞 <b id="stat-likes">0</b></span></button>
        <div class="stats-inline">
          <span>👁 阅读 <b id="stat-views">-</b></span>
          <span>💬 评论 <b id="stat-comments">-</b></span>
        </div>
      </div>

      <nav class="post-nav" id="post-nav"></nav>
    </article>

    <section class="comments">
      <div class="comments-title">💬 评论 <span class="count" id="comment-count">0</span></div>
      <form class="comment-form" id="comment-form">
        <div class="form-row">
          <input type="text" id="c-nickname" placeholder="昵称 *" maxlength="24" required>
          <input type="email" id="c-email" placeholder="邮箱（选填，用于 Gravatar 头像）">
        </div>
        <textarea id="c-content" placeholder="说点什么吧… 遵守社区公约，友善交流 💬" maxlength="1000" required></textarea>
        <div class="form-foot">
          <button type="button" class="emoji-btn" id="emoji-btn" aria-label="选择表情">😊</button>
          <span class="form-hint">评论数据全球同步 · 国内 Gitee / 海外 GitHub 与 CF 均可访问</span>
          <button type="submit" class="submit-btn" id="c-submit">发布评论</button>
        </div>
        <div class="emoji-panel" id="emoji-panel"></div>
      </form>
      <div class="comment-list" id="comment-list"></div>
    </section>
  </div>

  <aside class="side">
    <div class="panel alliance-panel" aria-label="博客联盟">
      <div class="panel-title"><span class="ico">🌐</span>博客联盟</div>
      <div class="alliance-badges">
        <a class="alliance-badge" href="https://www.travellings.cn/go.html" target="_blank" rel="noopener" title="开往-友链接力"><img class="tv-logo" src="https://www.travellings.cn/assets/logo.svg" alt="开往-友链接力" width="108" height="27" loading="lazy"></a>
        <a class="alliance-badge" href="https://www.foreverblog.cn/" target="_blank" rel="noopener" title="十年之约 · 博客十年不注销约定"><img class="fb-logo" src="https://www.foreverblog.cn/favicon.ico" alt="十年之约" width="20" height="20" loading="lazy" onerror="this.style.display='none'"><span>十年之约</span></a>
      </div>
    </div>
    <div class="panel">
      <div class="panel-title"><span class="ico">📖</span>目录</div>
      <div class="toc" id="toc-list"></div>
    </div>
    <div class="panel">
      <div class="panel-title"><span class="ico">🔗</span>相关</div>
      <div class="tag-cloud">
        <a href="../index.html">🏠 首页</a>
        <a href="https://dujiecone.520691.xyz/" target="_blank" rel="noopener">💻 渡劫code</a>
        <a href="https://www.520691.xyz/" target="_blank" rel="noopener">🏠 个人官网</a>
      </div>
    </div>
  </aside>
</main>

<footer class="site-footer">
  <div class="footer-inner">
    <div class="footer-brand">
      <a class="logo" href="../index.html"><span class="logo-badge">🌊</span>渡劫博客</a>
      <p>独立开发者 gjsvip 的技术自留地。静态博客 + Cloudflare 全栈驱动，国内 Gitee 镜像，全球 CDN 加速。评论数据全球实时同步。</p>
    </div>
    <div class="footer-col">
      <h4>导航</h4>
      <a href="../archive.html">文章归档</a>
      <a href="../tags.html">标签</a>
      <a href="../says.html">说说</a>
      <a href="../about.html">关于我</a>
    </div>
    <div class="footer-col">
      <h4>项目</h4>
      <a href="https://www.520691.xyz/" target="_blank" rel="noopener">个人官网</a>
      <a href="https://dujiecone.520691.xyz/" target="_blank" rel="noopener">渡劫code</a>
      <a href="https://github.com/gjsvip" target="_blank" rel="noopener">GitHub</a>
      <a href="https://gitee.com/gjsvip" target="_blank" rel="noopener">Gitee</a>
    </div>
  </div>
  <div class="footer-bottom">
    © 2024 - 2026 渡劫博客 · Powered by <span class="heart">❤️</span> HTML + Cloudflare | <a href="../rss.xml">RSS 订阅</a>
  </div>
</footer>

<div class="search-modal" id="search-modal" role="dialog" aria-label="站内搜索">
  <div class="search-panel">
    <div class="search-input-row">
      <span class="ico">🔍</span>
      <input id="search-input" type="text" placeholder="搜索标题、标签、内容…" autocomplete="off">
      <kbd>ESC 关闭</kbd>
    </div>
    <div class="search-results" id="search-results"></div>
  </div>
</div>

<div id="toast-wrap"></div>
<button id="back-top" aria-label="返回顶部">↑</button>
<script src="../assets/blog.js?v=20261021a" defer></script>
</body>
</html>
"""


def build_jsonld(meta: dict) -> str:
    """构造文章页的结构化数据（JSON-LD）：BlogPosting + BreadcrumbList 两块。

    字段值全部取自 posts.json 真实元数据，不编造。
    """
    canonical = f"{SITE_URL}/posts/{meta['slug']}"
    posting = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": meta["title"],
        "description": meta.get("excerpt", ""),
        "image": OG_IMAGE,
        "url": canonical,
        "datePublished": meta["date"],
        "dateModified": meta["date"],
        "inLanguage": "zh-CN",
        "keywords": ", ".join(meta.get("tags", [])),
        "author": {
            "@type": "Person",
            "name": "gjsvip",
            "alternateName": "渡劫",
            "url": AUTHOR_URL,
        },
        "publisher": {
            "@type": "Organization",
            "name": SITE_NAME,
            "url": f"{SITE_URL}/",
            "logo": {"@type": "ImageObject", "url": OG_IMAGE},
        },
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
    }
    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "首页", "item": f"{SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "归档", "item": f"{SITE_URL}/archive"},
            {"@type": "ListItem", "position": 3, "name": meta["title"], "item": canonical},
        ],
    }
    blocks = []
    for data in (posting, breadcrumb):
        blocks.append(
            '<script type="application/ld+json">\n'
            + json.dumps(data, ensure_ascii=False)
            + "\n</script>"
        )
    return "\n".join(blocks)


def render_page(meta: dict, body: str) -> str:
    """把元数据与正文套入 PAGE_TEMPLATE，返回完整 HTML 文本。"""
    canonical = f"{SITE_URL}/posts/{meta['slug']}"
    replacements = {
        "__TITLE__": html.escape(meta["title"], quote=True),
        "__EXCERPT__": html.escape(meta.get("excerpt", ""), quote=True),
        "__CATEGORY__": html.escape(meta.get("category", "随笔"), quote=True),
        "__COVER__": html.escape(meta.get("cover", "📄"), quote=True),
        "__DATE__": meta["date"],
        "__AUTHOR__": AUTHOR,
        "__SITE_NAME__": SITE_NAME,
        "__CANONICAL__": canonical,
        "__OG_IMAGE__": OG_IMAGE,
        "__FAVICON__": FAVICON,
        "__JSONLD__": build_jsonld(meta),
        "__BODY__": body.rstrip("\n"),
    }
    page = PAGE_TEMPLATE
    for token, value in replacements.items():
        page = page.replace(token, value)
    leftover = re.findall(r"__[A-Z_]+__", page)
    if leftover:
        raise ValueError(f"模板存在未替换占位符: {leftover}")
    return page


def load_posts() -> list:
    """读取 posts.json 并做基础校验，返回文章元数据列表。"""
    if not POSTS_JSON.exists():
        raise FileNotFoundError(f"未找到 {POSTS_JSON}")
    data = json.loads(POSTS_JSON.read_text(encoding="utf-8"))
    posts = data.get("posts", data if isinstance(data, list) else [])
    if not isinstance(posts, list) or not posts:
        raise ValueError("posts.json 中没有任何文章")
    seen = set()
    for meta in posts:
        for field in ("slug", "title", "date"):
            if not meta.get(field):
                raise ValueError(f"文章缺少必需字段 {field}: {meta}")
        slug = meta["slug"]
        if not SLUG_RE.match(slug):
            raise ValueError(f"非法 slug（仅允许小写字母/数字/连字符）: {slug}")
        if not DATE_RE.match(meta["date"]):
            raise ValueError(f"非法日期（应为 YYYY-MM-DD）: {slug} -> {meta['date']}")
        if slug in seen:
            raise ValueError(f"slug 重复: {slug}")
        seen.add(slug)
    return posts


def count_cjk(text: str) -> int:
    """统计正文中的中文字符数（剔除 HTML 标签后粗略估计）。"""
    plain = re.sub(r"<[^>]+>", " ", text)
    return len(CJK_RE.findall(plain))


def main(argv: list) -> int:
    """入口：生成或校验全部文章产物。"""
    check_only = "--check" in argv
    try:
        posts = load_posts()
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"[gen_posts] 读取 posts.json 失败: {exc}", file=sys.stderr)
        return 1

    exit_code = 0
    stale, warnings = [], []
    for meta in posts:
        slug = meta["slug"]
        body_file = POSTS_DIR / f"{slug}.body.html"
        out_file = POSTS_DIR / f"{slug}.html"
        if not body_file.exists():
            print(f"[gen_posts] 缺少正文文件 {body_file.relative_to(ROOT)}，跳过", file=sys.stderr)
            exit_code = 1
            continue
        body = body_file.read_text(encoding="utf-8")
        cjk = count_cjk(body)
        if cjk < MIN_CJK_CHARS:
            warnings.append(f"{slug}: 正文仅 {cjk} 个中文字符（< {MIN_CJK_CHARS}）")
        try:
            page = render_page(meta, body)
        except ValueError as exc:
            print(f"[gen_posts] {slug} 渲染失败: {exc}", file=sys.stderr)
            exit_code = 1
            continue
        if check_only:
            if not out_file.exists():
                stale.append(f"{slug}.html 不存在")
                exit_code = max(exit_code, 2)
            elif out_file.read_text(encoding="utf-8") != page:
                stale.append(f"{slug}.html 与元数据/正文不同步")
                exit_code = max(exit_code, 2)
        else:
            out_file.write_text(page, encoding="utf-8")
            print(f"[gen_posts] 生成 posts/{slug}.html（{cjk} 中文字符）")

    for w in warnings:
        print(f"[gen_posts][警告] {w}", file=sys.stderr)
    if check_only:
        if stale:
            print("[gen_posts] 以下文章产物不是最新，请执行 python3 gen_posts.py：", file=sys.stderr)
            for s in stale:
                print(f"  - {s}", file=sys.stderr)
        else:
            print(f"[gen_posts] 校验通过：{len(posts)} 篇文章产物均为最新")
    else:
        print(f"[gen_posts] 完成：共处理 {len(posts)} 篇文章")
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
