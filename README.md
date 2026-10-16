# Severus' Blog Site

个人博客，Hexo + GitHub Pages。
线上地址：**https://severuszh.github.io/SeverusBlog/**

> 仓库根目录是**写作源**（Markdown + 图片 + 配置）；线上站点由 GitHub Actions
> 构建 `public/` 后通过 Pages 部署，构建产物不进 Git。

---

## 写一篇新文章

```bash
npm ci                         # 首次或依赖变更后
npx hexo new post "文章标题"    # 生成 source/_posts/文章标题.md
npx hexo server                # 本地预览 http://localhost:4000/SeverusBlog/
```

编辑 `source/_posts/文章标题.md`，图片放到 `source/image/<文章名>/`，
正文里用 `/image/<文章名>/<文件名>.png` 引用（Hexo 会自动补上 `/SeverusBlog/` 前缀）。

发布 = 提交并推送：

```bash
git add -A
git commit -m "post: 文章标题"
git push
```

推送后 GitHub Actions 会自动构建并部署，约 1 分钟生效。

## 目录结构

| 路径 | 说明 |
| --- | --- |
| `source/_posts/` | 38 篇归档文章（Markdown，写作主体） |
| `source/image/` | 文章配图（按文章名分目录） |
| `source/README.md` | 站点上的 `/README.html` 页面 |
| `source/tags/index.md` | `/tags/` 标签云页（`layout: tag`） |
| `source/search/index.md` | `/search/` 本地搜索页（`layout: search`） |
| `themes/cards/` | 主题 hexo-theme-cards **v1.5.1**（vendored，勿改 `.git`） |
| `_config.yml` | 站点配置 |
| `themes/cards/_config.yml` | 主题配置（导航、封面、TOC、评论、摘要等） |
| `tools/` | 一次性迁移与校验脚本，仅作溯源/复核用 |
| `.github/workflows/deploy.yml` | 构建 + 部署流水线 |

## 依赖与版本约束（**改动前请先读**）

构建产物对依赖版本敏感，以下版本是为复刻历史输出而锁定的：

- `hexo` 7.3.0、`hexo-renderer-marked` 6.3.0、`hexo-renderer-stylus` 3.0.1
- `highlight.js` **11.11.2**（锁定精确版本）

`highlight.js` 是关键：11.12.0 起 Java 语法高亮的分词结果变化，会让代码块的
`<span>` 结构与线上既有文章不一致，并进而影响列表页摘要的截断位置。
升级 Hexo / 主题 / highlight.js 前，请先用校验脚本确认产物仍然一致。

## 校验（重构与产物的等价性）

`site-src/public` 之外的产物比对脚本：

```bash
python3 tools/verify-rebuild.py     # 需要 repo/（历史产物）与 site-src/public/
```

本仓库的写作源是由 2025-04-08 的线上产物反向重建的（原源工程已丢失）。
重建结果与线上产物逐页等价：文章页 38/38、其他页面 33/33、469 个共同文件中
397 个逐字节相同；其余差异仅来自构建元数据（页脚版权年份、`article:modified_time`）。

## 维护须知

- **站点 URL 不能改**：仓库名/路径一旦变化，Valine 评论（按页面 URL 归档）会全部失联。
- 文章日期使用 `Asia/Shanghai`（`_config.yml` 的 `timezone`），CI 在 UTC 下构建也会得到相同 URL。
- 文章顶部若出现「**更新于**」一行，其值来自 front matter 的 `updated:`；
  新文章不写该项时按 `date` 显示（`updated_option: date`，不依赖文件 mtime）。
- 列表页摘要由主题的 `meta.auto_excerpt`（`length: 150`）自动生成，无需手写。
- 代码块围栏可带语言（如 ```c）；未带语言的块由 `highlight.auto_detect` 识别。
- 评论为 Valine（LeanCloud），配置在 `themes/cards/_config.yml`。
  appId/appKey 是客户端公开配置；若不再使用请在 LeanCloud 侧停用应用。

## 升级主题

```bash
cd themes/cards && git clone --depth 1 --branch v1.5.1 https://github.com/ChrAlpha/hexo-theme-cards.git /tmp/cards
# 用 /tmp/cards 覆盖本目录（保留 <主题>/_config.yml 的本地配置）
```
