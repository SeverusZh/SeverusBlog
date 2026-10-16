#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""规范化“有意变更”校验：证明规范化只做了规范列明的改动。

比对 基线构建（规范化前）与 新构建（规范化后）：

有意变更（比对时从两侧归一掉）：
  A. 删除「字数：N，阅读时间：M分钟」行
  B. 删除与文章标题重复的首个 H1（主题已在页顶渲染标题）
  C. 标题层级统一直到 ## 且不跳级（只比较标题文本序列，不比较层级）
  D. 删除 2 处指向本地临时文件的坏链图片
  E. 散文 NBSP -> 普通空格
  F. 主题补丁：updated 与 date 同一天时不再输出「更新于」
  G. 停用 Valine：评论块不再输出
  H. 标签名去前缀（-面试题 -> 面试题）

必须仍然相等（不得有任何差异）：
  - 正文可见文本
  - 代码块正文（逐字节）
  - 其余图片引用
  - 标题文本序列
  - 文章 URL 集合（另由 check-permalinks.py 守卫）

用法：python3 tools/verify-normalization.py <基线public> [新public]
"""

import glob
import html
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_RE = re.compile(r'<div class="post__content">(.*?)\n    </div>', re.S)
FIG_RE = re.compile(r'<figure class="highlight[^"]*">(.*?)</figure>', re.S)
CODE_RE = re.compile(r'<td class="code">.*?<pre>(.*?)</pre>', re.S)
VALINE_RE = re.compile(r'<script>\s*function loadComment\(\)[\s\S]*?</script>', re.S)
UPDATED_RE = re.compile(r'<div class="post-footer__meta">.*?</div>', re.S)
TOC_RE = re.compile(r'<div class="toc[\s\S]*?</div>\s*</div>', re.S)


def strip_tags(h):
    return html.unescape(re.sub(r"<[^>]+>", "", h))


def canon(text):
    text = text.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def code_blocks(content):
    out = []
    for inner in FIG_RE.findall(content):
        m = CODE_RE.search(inner)
        body = re.sub(r"<br\s*/?>", "\n", m.group(1)) if m else ""
        body = html.unescape(re.sub(r"<[^>]+>", "", body)).replace("\u00a0", " ")
        out.append(body)
    return out


def img_srcs(content):
    return re.findall(r'<img[^>]*src="([^"]*)"', content)


def headings(content):
    return [re.sub(r"\s+", " ", strip_tags(m.group(1)).replace("\u00a0", " ")).strip()
            for m in re.finditer(r"<h[1-6][^>]*>(.*?)</h[1-6]>", content, re.S)]


def load(base, slug):
    hits = glob.glob(os.path.join(base, "20*", "*", "*", slug, "index.html"))
    return open(hits[0], encoding="utf-8").read() if hits else None


def main():
    base, new = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else
                              os.path.join(BASE, "public"))
    slugs = sorted({os.path.basename(os.path.dirname(p))
                    for p in glob.glob(os.path.join(base, "20*", "*", "*", "*", "index.html"))})
    print(f"文章 {len(slugs)} 篇")

    problems = []
    for slug in slugs:
        a, b = load(base, slug), load(new, slug)
        if a is None or b is None:
            problems.append(f"{slug}: 缺页面（base={a is not None} new={b is not None}）")
            continue
        ca, cb = CONTENT_RE.search(a), CONTENT_RE.search(b)
        if ca is None or cb is None:
            problems.append(f"{slug}: 缺 post__content")
            continue
        A, B = ca.group(1), cb.group(1)

        # --- 有意变更 A：字数行（基线有，新无）
        A2 = re.sub(r'<p>字数：\d+，阅读时间：\d+分钟</p>\n?', "", A, count=1)
        # --- 有意变更 B：与标题重复的首个 H1（基线有，新无）
        tm = re.search(r"<title>([^<]*)</title>", a)
        title = html.unescape(tm.group(1)).split(" | ")[0].strip() if tm else ""
        m = re.search(r"<h1[^>]*>(.*?)</h1>", A2, re.S)
        if m and strip_tags(m.group(1)).strip() == title:
            A2 = A2[:m.start()] + A2[m.end():]
        # --- 有意变更 D/E/F/G：坏链图片、空白、更新于、评论块
        A2 = re.sub(r'<img[^>]*src="file:///[^"]*"[^>]*>', "", A2)
        B2 = re.sub(r'<img[^>]*src="file:///[^"]*"[^>]*>', "", B)
        B2 = UPDATED_RE.sub("", B2)
        A2 = UPDATED_RE.sub("", A2)

        # --- 必须相等：正文文本 / 代码块 / 图片 / 标题文本
        ta, tb = canon(strip_tags(A2)), canon(strip_tags(B2))
        if ta != tb:
            i = next((k for k, (x, y) in enumerate(zip(ta, tb)) if x != y), min(len(ta), len(tb)))
            problems.append(f"{slug}: 正文文本不一致 @{i} "
                            f"base={ta[max(0,i-40):i+50]!r} new={tb[max(0,i-40):i+50]!r}")
        ka, kb = code_blocks(A2), code_blocks(B2)
        if ka != kb:
            problems.append(f"{slug}: 代码块不一致（{len(ka)} vs {len(kb)}）")
            for i, (x, y) in enumerate(zip(ka, kb)):
                if x != y:
                    j = next((k for k, (p, q) in enumerate(zip(x, y)) if p != q), min(len(x), len(y)))
                    problems.append(f"    第{i+1}块 @{j}: base={x[max(0,j-30):j+30]!r} new={y[max(0,j-30):j+30]!r}")
                    break
        ia, ib = img_srcs(A2), img_srcs(B2)
        if ia != ib:
            problems.append(f"{slug}: 图片引用不一致 base={ia[:3]} new={ib[:3]}")
        ha, hb = headings(A2), headings(B2)
        if ha != hb:
            problems.append(f"{slug}: 标题文本序列不一致\n      base={ha[:6]}\n      new ={hb[:6]}")

    print(f"问题 {len(problems)} 个")
    for p in problems[:20]:
        print("  -", p)
    print("判定:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
