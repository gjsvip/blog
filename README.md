# gjsvip.github.io/blog

gjsvip 的技术博客，深色 IDE 风格纯静态站。由渡劫code 项目体系自动部署。

- **线上地址**：https://gjsvip.github.io/blog/
- **官网主域**：https://gjsvip.github.io/ （渡劫code，GitHub Pages 根路径）
- **关联项目**：[gjsvip/dujiecode](https://github.com/gjsvip/dujiecode)（云端 IDE，GitHub + Gitee + Cloudflare 三端同步）

## 本地预览

纯静态、无构建依赖，任选其一：

```bash
python3 -m http.server 8080   # http://localhost:8080
npx serve .
```

## 目录结构

```
blog/
├── index.html                  # 文章列表首页
├── posts/
│   ├── hello-world.html        # 保留文章（原 Hexo 博客迁移）
│   ├── dujiecode-release.html  # 渡劫code 发布记
│   └── three-end-sync.html     # 三端同步架构记
├── assets/style.css            # 深色 IDE 主题
├── robots.txt                  # 相对路径 Sitemap
├── sitemap.xml                 # 博客 sitemap
└── .nojekyll                   # 跳过 Jekyll
```

## 新增文章

1. 在 `posts/` 新建 `xxx.html`（复制现有文章头部结构，使用相对路径 `../assets/style.css`）
2. 在 `index.html` 的 `.post-list` 添加卡片（倒序排列）
3. 在 `sitemap.xml` 添加 URL
4. 提交推送，GitHub Pages 自动发布

## 部署

GitHub Pages 项目页（主分支根目录），push 即自动发布。
收录：sitemap + robots + IndexNow（密钥托管于主域 gjsvip.github.io 根路径）。
