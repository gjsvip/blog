# 渡劫博客（自研版 · 已归档）

> 本仓库是渡劫博客的**初代自研版本**，现已被 [flare-stack-blog](https://github.com/du2333/flare-stack-blog) 方案取代并归档。开源出来给有需要的朋友参考学习。

## 特性

- 纯手写静态站：零框架、零依赖，原生 HTML/CSS/JS
- 双主题（墨色/纸感语义变量一键切换）+ 衬线标题排版
- 评论/点赞/浏览量/说说（Cloudflare Worker + D1，全球同步）
- 文章生成器 `gen_posts.py`：Markdown → HTML、封面图自动上传图床（Pillow 压缩 ≤20KB）、字数统计、相关推荐
- SEO：sitemap / RSS / IndexNow / 结构化数据
- Cloudflare Pages 自动部署（连 GitHub 仓库）

## 结构

```
├── gen_posts.py        # 文章生成器（含图床上传/字数统计/相关推荐）
├── index.html          # 首页（信息流卡片 + 打字机 hero）
├── posts/              # 生成的文章页（30 篇）
├── assets/             # style.css / blog.js（原生实现）
├── friends.json        # 友链数据
└── _headers            # CF Pages 缓存策略（immutable + SWR）
```

## 部署

推送到 GitHub → Cloudflare Pages 连接仓库即可。评论后端需要另配 Worker + D1（参考 dujiecode 仓库）。

## 后记

自研版跑了 4 天，完成度尚可，但功能密度、后台管理、内容管理效率远不如现成方案。**建议独立开发者优先用现成项目，把时间花在内容上。**

—— 渡劫 gjsvip · 2026-10
