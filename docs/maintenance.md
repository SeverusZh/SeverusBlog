# 维护说明

站点：**https://severuszh.github.io/SeverusBlog/**（仓库 `SeverusZh/SeverusBlog`）

仓库根目录是**写作源**（Markdown + 图片 + 配置）；线上站点由 GitHub Actions 构建
`public/` 后通过 Pages 部署，构建产物不进 Git。

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
export TZ=Asia/Shanghai        # 必须，见下文“构建时区”
git add -A && git commit -m "post: 文章标题" && git push
```

推送后 CI 会先检查文章格式与 URL 稳定性，再构建部署，约 1 分钟生效。

## 文章格式规范

38 篇文章统一遵循 [`tools/style-spec.md`](style-spec.md)：

- 不重复写标题（主题已在页顶渲染）；首个标题层级为 `##` 且不跳级；不写「字数：…」行。
- 代码块语言小写，代码内容（含 Tab）不动；无序列表用 `-`；有序列表保留显式编号
  （这些文章的编号步骤常被代码块打断，重编号会让页面显示成一排 “1.”）。
- 散文 NBSP 一律用普通空格；文末单换行；不留行尾空格。

```bash
python3 tools/normalize-posts.py     # 按规范自动规范化（幂等）
python3 tools/lint-posts.py          # 检查是否合规（CI 也会跑）
python3 tools/verify-normalization.py <基线public>   # 证明只做了规范内的改动
```

`themes/cards/layout/_meta/updated.ejs` 有一处本地补丁：仅当 `updated` 与 `date`
不同天才显示「更新于」；升级主题后需要重打。

## 目录结构

| 路径 | 说明 |
| --- | --- |
| `source/_posts/` | 38 篇文章（Markdown，写作主体） |
| `source/image/` | 文章配图（按文章名分目录） |
| `source/README.md` | 站点上的 `/README.html` 页面 |
| `source/tags/index.md` | `/tags/` 标签云页（`layout: tag`） |
| `source/search/index.md` | `/search/` 本地搜索页（`layout: search`） |
| `themes/cards/` | 主题 hexo-theme-cards **v1.5.1**（vendored） |
| `_config.yml` | 站点配置 |
| `themes/cards/_config.yml` | 主题配置（导航、封面、TOC、评论、摘要等） |
| `tools/` | 迁移与校验脚本（可复跑，供溯源/复核） |
| `.github/workflows/deploy.yml` | 构建 + 部署流水线 |

## 依赖与版本约束（**改动前请先读**）

- `hexo` **8.1.2**（2026-10 从 7.3.0 升级；Node 需 ≥ 20.19，CI 用 22）
- `hexo-renderer-marked` 6.3.0、`hexo-renderer-stylus` 3.0.1、`hexo-renderer-ejs` 2.0.0
- `highlight.js` **11.11.2**（精确锁定）

`highlight.js` 是关键：11.12.0 起 Java 语法高亮的分词结果变化，会让代码块的
`<span>` 结构与既有文章不一致，并影响列表页摘要的截断位置。
升级 Hexo / 主题 / highlight.js 前，请先跑校验确认产物仍然一致。

## 维护须知

- **站点 URL 不能改**：仓库名/路径一旦变化，所有文章链接与评论归档都会失联。
- **构建时区必须是 `Asia/Shanghai`**：Hexo 的 permalink 日期按构建机器的时区渲染，
  时区不同会改变文章 URL（例如 2025-04-08 凌晨的文章在 UTC 下会变成 2025-04-07）。
  CI 已在 workflow 里设 `TZ: Asia/Shanghai`。
- CI 生成后会跑 `python3 tools/check-permalinks.py`：URL 集合一旦与历史站点不一致
  就让构建失败，避免悄悄改掉链接。
- 文章底部若出现「**更新于**」一行，其值来自 front matter 的 `updated:`；
  不写该项时按 `date`（`updated_option: date`，不依赖文件 mtime）。
- 列表页摘要由主题的 `meta.auto_excerpt`（`length: 150`）自动生成，无需手写。
- 代码块围栏可带语言（如 ` ```c `）；未带语言的块由 `highlight.auto_detect` 识别。
- **评论已停用**（2026-10，原用 Valine/LeanCloud）：页面不再加载第三方评论脚本，
  也不再暴露 appId/appKey。如需恢复，把 `themes/cards/_config.yml` 的 `comments.use:`
  改成 `valine`；LeanCloud 侧的应用/数据需要登录控制台处理。

## 界面语言（必须用合法语言标签）

`_config.yml` 用 `language: zh-CN`，与主题的 `languages/zh-CN.yml` 对应，界面为中文
（“标签”“文章目录”）。

**不要写 `zh_CN`**：它不是合法的 BCP-47 标签，Node 22（CI）与 Node 24（本地）对
`Intl.Locale` 的处理不同，会让界面语言随构建环境在中文/英文之间跳变（已实测）。
想要英文界面，改成 `language: en`（同样确定）。

## 校验脚本（产物等价性）

```bash
VERIFY_REF=<历史产物目录> VERIFY_NEW=public python3 tools/verify-rebuild.py
python3 tools/verify-live.py          # 线上产物 vs 本地构建，逐字节比对
```

本仓库的写作源是由 **2025-04-08 的线上产物反向重建**的（原 Hexo 源工程已丢失，
仓库当时只剩构建产物）。重建脚本：`python3 tools/rebuild-source.py --ref <历史产物>`。
重建与规范化后的站点对原线上站点等价：文章 38/38 一致，469 个文件中 397 个逐字节
相同，其余差异全部来自有意变更（generator 版本、删「字数」行、确定性 `modified_time`、
抑制冗余「更新于」、删坏链图片）。

## 升级主题

```bash
git clone --depth 1 --branch v1.5.1 https://github.com/ChrAlpha/hexo-theme-cards.git /tmp/cards
# 用 /tmp/cards 覆盖 themes/cards（保留 themes/cards/_config.yml 的本地配置与 _meta/updated.ejs 补丁）
```
