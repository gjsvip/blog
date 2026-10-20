# 渡劫小站（dujie blog）

独立开发者 gjsvip（渡劫）的技术博客。**纯静态 HTML**，零构建、零依赖，评论与互动由 Cloudflare D1 + Worker 驱动。

## 三端同步

| 端 | 地址 | 触发方式 |
|---|---|---|
| Cloudflare Pages | https://blog.520691.xyz | push main → wrangler pages deploy |
| GitHub Pages | https://gjsvip.github.io/blog/ | push main → gh-pages 分支（Gitee 镜像源） |
| Gitee Pages | https://dujie_nb_admin.gitee.io/blog/ | mirror-to-gitee.yml 自动同步 |

**评论全球同步**：三端前端共用同一 API `https://dujie_cone.520691.xyz/api/blog/*`，
国内 Gitee 入口发布的评论，海外 GitHub / CF 入口实时可见（同一套 D1 数据）。

## 功能

- 深/浅双主题（localStorage 记忆）
- Ctrl+K 站内搜索（标题/标签/摘要）
- 树形评论 + 楼中楼回复 + Gravatar 头像 + emoji
- 点赞 / 浏览（UV 级）/ 评论数统计
- 阅读进度条、TOC 目录、代码一键复制 + 轻量高亮
- 归档时间线、标签云、友链、说说
- RSS（rss.xml）+ sitemap.xml + IndexNow 收录

## 目录

```
├── index.html / archive / tags / says / friends / about
├── posts/            # 4 篇文章
├── assets/           # style.css（设计系统）+ blog.js
├── posts.json        # 文章元数据（搜索/列表/归档共用）
├── rss.xml / sitemap.xml / robots.txt
└── .github/workflows/  # deploy-cf-pages.yml + mirror-to-gitee.yml
```

## 本地预览

任意静态服务器即可，如 `python3 -m http.server 8080`。
