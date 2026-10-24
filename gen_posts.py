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
import os
import io
import urllib.request
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POSTS_JSON = ROOT / "posts.json"
POSTS_DIR = ROOT / "posts"

#: 图床（写作流自动把文章本地图传上去，减轻主站带宽）
MEDIA_HOST = "https://media.520691.xyz"
MEDIA_KEY = os.environ.get("MEDIA_KEY", "B2O-AZl1IcREodD4cW4qZDr_cvt1SGTP")
MEDIA_MAX_DIM = 1280
MEDIA_TARGET_KB = 20
MEDIA_FLOOR_Q = 25
#: 仅这类 src 视为"需要上传的本地文章图"（站点资源 /assets 与主站同源，保留）
_IMG_RE = re.compile(r'(<img\b[^>]*?\bsrc=")([^"]+)(")', re.IGNORECASE)

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
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="../assets/style.css?v=20261024a">
<link rel="stylesheet" href="../assets/theme.css?v=20261024a">
<link rel="alternate" type="application/rss+xml" title="渡劫博客 RSS" href="../rss.xml">
<link rel="icon" href="__FAVICON__">
__JSONLD__
<meta name="msvalidate.01" content="48B9573DAB77D5857E5532B001FE1642" />
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
          <span class="am-item"><svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>__DATE__</span>
          <span class="am-item"><svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.83z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>__CATEGORY__</span>
          <span class="am-item"><svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/></svg>__WORDS__ 字</span>
          <span class="am-item"><svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>约 __READTIME__ 分钟</span>
        </div>
      </div>

      <div class="article-cover __COVER_TONE__">__COVER__</div>

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
      <div class="related">__RELATED__</div>
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
        <div id="cf-turnstile-slot"></div>
        <div class="comment-pending-hint" id="comment-pending-hint" hidden>🔍 评论已提交，博主审核通过后展示</div>
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
<script src="../assets/blog.js?v=20261023c" defer></script>
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


_TONE_MAP = {
    "Cloudflare": "cover-tone-tech", "架构": "cover-tone-tech", "运维": "cover-tone-tech",
    "工程实践": "cover-tone-tech",
    "实战": "cover-tone-craft", "工具": "cover-tone-craft", "教程": "cover-tone-craft",
    "项目发布": "cover-tone-craft",
    "复盘": "cover-tone-life", "随笔": "cover-tone-life",
    "AI": "cover-tone-ai",
}


def _cover_parts(meta):
    """封面双模式：URL -> 真实图；否则分类色渐变横幅 + emoji 水印（禁空白容器）。"""
    cover = str(meta.get("cover") or "📄")
    if cover.startswith(("http://", "https://")):
        tone = "cover-img"
        inner = '<img src="%s" alt="" loading="lazy" decoding="async">' % html.escape(cover, quote=True)
    else:
        tone = _TONE_MAP.get(str(meta.get("category", "")), "cover-tone-default")
        inner = '<span class="cover-deco">%s</span>' % html.escape(cover, quote=True)
    return tone, inner


def build_related(meta, all_posts):
    """相关阅读：同分类优先取 3 篇。"""
    if not all_posts:
        return ""
    pool = [p for p in all_posts if p.get("slug") != meta.get("slug")]
    same = [p for p in pool if p.get("category") == meta.get("category")]
    picks = (same if len(same) >= 3 else (same + [p for p in pool if p not in same]))[:3]
    if not picks:
        return ""
    cards = []
    for p in picks:
        cover = str(p.get("cover", ""))
        if cover.startswith(("http://", "https://")):
            img = '<img src="%s" alt="" loading="lazy">' % html.escape(cover, quote=True)
        else:
            img = '<span class="r-emoji">%s</span>' % html.escape(cover[:2] or "📄", quote=True)
        cards.append(
            '<a class="related-card" href="%s.html">%s<span class="r-body"><b>%s</b><time>%s</time></span></a>'
            % (html.escape(p["slug"], quote=True), img, html.escape(p["title"]), html.escape(p.get("date", "")))
        )
    return '<h2 class="related-head">相关阅读</h2><div class="related-grid">' + "".join(cards) + "</div>"


def render_page(meta: dict, body: str, all_posts=None) -> str:
    """把元数据与正文套入 PAGE_TEMPLATE，返回完整 HTML 文本。"""
    canonical = f"{SITE_URL}/posts/{meta['slug']}"
    tone_cover, inner_cover = _cover_parts(meta)
    replacements = {
        "__TITLE__": html.escape(meta["title"], quote=True),
        "__EXCERPT__": html.escape(meta.get("excerpt", ""), quote=True),
        "__CATEGORY__": html.escape(meta.get("category", "随笔"), quote=True),
        "__WORDS__": str(meta.get("words", "—")),
        "__READTIME__": str(meta.get("read_time", "—")),
        "__COVER_TONE__": tone_cover,
        "__COVER__": inner_cover,
        "__DATE__": meta["date"],
        "__AUTHOR__": AUTHOR,
        "__SITE_NAME__": SITE_NAME,
        "__CANONICAL__": canonical,
        "__OG_IMAGE__": OG_IMAGE,
        "__FAVICON__": FAVICON,
        "__JSONLD__": build_jsonld(meta),
        "__BODY__": body.rstrip("\n"),
        "__RELATED__": build_related(meta, all_posts),
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


def _compress_to_webp(path: str) -> bytes:
    """把本地图片压到 TARGET_KB 以下（长边缩 + WebP 自适应质量）。返回字节。"""
    from PIL import Image
    img = Image.open(path)
    img = img.convert("RGB") if img.mode in ("RGBA", "P", "LA") else img
    bw, bh = img.size
    target = MEDIA_TARGET_KB * 1024
    q, scale = 90, 1.0
    while True:
        cur = img.resize((max(16, int(bw * scale)), max(16, int(bh * scale))), Image.LANCZOS) if scale < 1.0 else img
        buf = io.BytesIO()
        cur.save(buf, format="WEBP", quality=q, method=6)
        data = buf.getvalue()
        if len(data) <= target:
            return data
        if q > MEDIA_FLOOR_Q:
            q -= 5
            continue
        if min(cur.size) < 160:
            return data
        scale *= 0.7
        q = 80


def _upload_image(local_path: str) -> str | None:
    """压缩并上传本地图到图床，返回公开 URL；失败返回 None（保留原链接）。"""
    try:
        data = _compress_to_webp(local_path)
    except Exception as exc:  # noqa: BLE001
        print(f"[gen_posts][图片] 压缩失败 {local_path}: {exc}", file=sys.stderr)
        return None
    req = urllib.request.Request(
        MEDIA_HOST + "/upload", data=data, method="POST"
    )
    req.add_header("x-api-key", MEDIA_KEY)
    req.add_header("content-type", "image/webp")
    req.add_header("User-Agent", "Mozilla/5.0 (compatible; dujie-gen/1.0)")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode()).get("url")
    except Exception as exc:  # noqa: BLE001
        print(f"[gen_posts][图片] 上传失败 {local_path}: {exc}", file=sys.stderr)
        return None


def rewrite_images(body: str, base_dir: Path) -> str:
    """把正文中引用的本地文章图自动传到图床并改写 src。

    - http(s)://、//、data:、含 /assets/ 的站点资源 一律跳过
    - 其余相对路径视为本地图：存在则上传并替换为 CDN URL
    """
    def repl(m):
        pre, src, post = m.group(1), m.group(2), m.group(3)
        if src.startswith(("http://", "https://", "//", "data:")) or "/assets/" in src:
            return m.group(0)
        local = (base_dir / src).resolve()
        if not local.is_file():
            return m.group(0)
        url = _upload_image(str(local))
        return pre + (url or src) + post if url else m.group(0)
    return _IMG_RE.sub(repl, body)


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
        body = rewrite_images(body, body_file.parent)
        cjk = count_cjk(body)
        if cjk < MIN_CJK_CHARS:
            warnings.append(f"{slug}: 正文仅 {cjk} 个中文字符（< {MIN_CJK_CHARS}）")
        try:
            page = render_page(meta, body, posts)
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
