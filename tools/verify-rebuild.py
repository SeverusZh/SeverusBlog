#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify-rebuild.py — 把重建构建（site-src/public）与线上参考产物（repo/）逐页比对。

判据（全部必须通过才算还原无损）：
  1. 文章数 38，文章 URL 集合与参考完全一致；
  2. 每篇正文可见文本、代码块正文、图片引用、标题序列一致；
  3. 列表页/归档/标签页可见文本一致；
  4. search.json 的条目元数据与正文文本一致。

输出：docs/aegis/verification/rebuild-diff.md
"""

import glob
import html
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.environ.get("VERIFY_REF") or os.path.join(ROOT, "repo")
NEW = os.environ.get("VERIFY_NEW") or os.path.join(ROOT, "site-src", "public")
OUT = os.environ.get("VERIFY_OUT") or os.path.join(ROOT, "docs", "aegis", "verification", "rebuild-diff.md")

CONTENT_RE = re.compile(r'<div class="post__content">(.*?)\n    </div>', re.S)
FIG_RE = re.compile(r'<figure class="highlight(?: ([^"]*))?">(.*?)</figure>', re.S)
CODE_RE = re.compile(r'<td class="code">.*?<pre>(.*?)</pre>', re.S)
IGNORE_PATHS = {".nojekyll", "README.md", "db.json"}


def strip_tags(h):
    return html.unescape(re.sub(r"<[^>]+>", "", h))


def norm(s):
    s = re.sub(r"\s+", " ", s).strip()
    # 页脚版权年份取决于构建时间（主题用当前年份），不属于还原差异
    return re.sub(r"©\s*\d{4}", "© YYYY", s)


def code_blocks(content):
    out = []
    for lang, inner in FIG_RE.findall(content):
        m = CODE_RE.search(inner)
        if not m:
            out.append(("?", ""))
            continue
        body = re.sub(r"<br\s*/?>", "\n", m.group(1))
        body = html.unescape(re.sub(r"<[^>]+>", "", body))
        out.append((lang or "", body.replace("\u00a0", " ")))
    return out


def img_srcs(content):
    return re.findall(r'<img[^>]*src="([^"]*)"', content)


def headings(content):
    return [(m.group(1), strip_tags(m.group(2)).strip())
            for m in re.finditer(r'<h([1-6])[^>]*>(.*?)</h\1>', content, re.S)]


def page_set(base):
    res = set()
    for dirpath, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            rel = os.path.relpath(os.path.join(dirpath, f), base).replace(os.sep, "/")
            if rel in IGNORE_PATHS or rel == ".git" or rel.startswith(".git/"):
                continue
            res.add(rel)
    return res


def post_pages(base):
    res = {}
    for y in ("2024", "2025"):
        for p in glob.glob(os.path.join(base, y, "*", "*", "*", "index.html")):
            rel = os.path.relpath(p, base).replace(os.sep, "/")
            res[rel] = open(p, encoding="utf-8").read()
    return res


def compare_post(rel, a, b, problems):
    ca, cb = CONTENT_RE.search(a), CONTENT_RE.search(b)
    if not ca or not cb:
        problems.append(f"{rel}: 缺少 post__content（ref={bool(ca)} new={bool(cb)}）")
        return False
    A, B = ca.group(1), cb.group(1)
    ok = True
    for label, fa, fb in (
        ("可见文本", lambda c: norm(strip_tags(c)), lambda c: norm(strip_tags(c))),
        ("代码块", code_blocks, code_blocks),
        ("图片引用", img_srcs, img_srcs),
        ("标题序列", headings, headings),
    ):
        va, vb = fa(A), fb(B)
        if va != vb:
            ok = False
            if label == "可见文本":
                i = next((i for i, (x, y) in enumerate(zip(va, vb)) if x != y),
                         min(len(va), len(vb)))
                problems.append(
                    f"{rel}: {label}不一致 (ref {len(va)} 字符 / new {len(vb)} 字符) "
                    f"首个差异@{i}: ref={va[max(0,i-30):i+40]!r} new={vb[max(0,i-30):i+40]!r}")
            elif label == "代码块":
                problems.append(f"{rel}: {label} 数量 ref={len(va)} new={len(vb)}")
                for i, (x, y) in enumerate(zip(va, vb)):
                    if x != y:
                        o = next((k for k, (p1, p2) in enumerate(zip(x[1], y[1])) if p1 != p2),
                                 min(len(x[1]), len(y[1])))
                        problems.append(f"    第{i+1}块 lang={x[0]!r}/{y[0]!r} 长度 "
                                        f"{len(x[1])}/{len(y[1])} 差异@{o}: "
                                        f"ref={x[1][max(0,o-25):o+35]!r} new={y[1][max(0,o-25):o+35]!r}")
                        break
            else:
                problems.append(f"{rel}: {label}不一致 ref={va if label!='标题序列' else va[:6]} "
                                f"new={vb if label!='标题序列' else vb[:6]}")
    return ok


def compare_generic(rel, a, b, problems):
    ta, tb = norm(strip_tags(a)), norm(strip_tags(b))
    if ta != tb:
        i = next((i for i, (x, y) in enumerate(zip(ta, tb)) if x != y), min(len(ta), len(tb)))
        problems.append(f"{rel}: 文本不一致 (ref {len(ta)} / new {len(tb)}) "
                        f"首个差异@{i}: ref={ta[max(0,i-40):i+50]!r} new={tb[max(0,i-40):i+50]!r}")
        return False
    return True


def main():
    problems = []
    ref_pages, new_pages = page_set(REF), page_set(NEW)
    only_ref = sorted(ref_pages - new_pages)
    only_new = sorted(new_pages - ref_pages)
    for p in only_ref:
        problems.append(f"仅参考产物存在: {p}")
    for p in only_new:
        problems.append(f"仅重建产物存在: {p}")

    rp, np_ = post_pages(REF), post_pages(NEW)
    stats = {"post_ok": 0, "post_total": 0, "page_ok": 0, "page_total": 0}
    for rel in sorted(set(rp) | set(np_)):
        stats["post_total"] += 1
        if rel not in rp or rel not in np_:
            problems.append(f"{rel}: 文章缺失")
            continue
        if compare_post(rel, rp[rel], np_[rel], problems):
            stats["post_ok"] += 1

    for rel in sorted(ref_pages & new_pages):
        if rel in rp:
            continue
        if not rel.endswith(".html"):
            continue
        stats["page_total"] += 1
        if compare_generic(rel, open(os.path.join(REF, rel), encoding="utf-8").read(),
                           open(os.path.join(NEW, rel), encoding="utf-8").read(), problems):
            stats["page_ok"] += 1

    # search.json
    sj = []
    ws_only = []
    if os.path.exists(os.path.join(NEW, "search.json")):
        a = json.load(open(os.path.join(REF, "search.json"), encoding="utf-8"))
        b = json.load(open(os.path.join(NEW, "search.json"), encoding="utf-8"))
        if len(a) != len(b):
            problems.append(f"search.json 条目数 ref={len(a)} new={len(b)}")
        am = {x.get("url"): x for x in a}
        bm = {x.get("url"): x for x in b}
        for u in sorted(set(am) & set(bm)):
            for k in ("title", "date", "tags", "categories"):
                if am[u].get(k) != bm[u].get(k):
                    problems.append(f"search.json {u} 字段 {k} 不一致: "
                                    f"{am[u].get(k)!r} vs {bm[u].get(k)!r}")
            if norm(am[u].get("content", "")) != norm(bm[u].get("content", "")):
                problems.append(f"search.json {u} content 不一致")
            elif am[u].get("content", "") != bm[u].get("content", ""):
                ws_only.append(u)
        order_same = [x.get("url") for x in a] == [x.get("url") for x in b]
        sj = [f"条目 ref={len(am)} new={len(bm)}，仅参考有={sorted(set(am)-set(bm))}，"
              f"仅重建有={sorted(set(bm)-set(am))}；条目顺序一致={order_same}；"
              f"仅空白差异的条目={len(ws_only)}"]
    else:
        problems.append("重建产物缺少 search.json")

    # 字节级比对与差异归类
    import hashlib
    common = sorted(ref_pages & new_pages)
    same = 0
    cat = {}
    for rel in common:
        a = open(os.path.join(REF, rel), "rb").read()
        b = open(os.path.join(NEW, rel), "rb").read()
        if a == b:
            same += 1
            continue
        sa = a.decode("utf-8", "ignore")
        sb = b.decode("utf-8", "ignore")
        why = set()
        if re.search(r"©\s*2025", sa) and re.search(r"©\s*2026", sb):
            why.add("页脚版权年份（主题取构建年份）")
        ma = re.search(r'article:modified_time" content="([^"]+)"', sa)
        mb2 = re.search(r'article:modified_time" content="([^"]+)"', sb)
        if ma and mb2 and ma.group(1) != mb2.group(1):
            why.add("article:modified_time（原为 mtime，现为确定性日期）")
        if not why:
            why.add("search.json 条目顺序（集合与字段一致）" if rel == "search.json"
                    else "未归类")
        cat.setdefault(" + ".join(sorted(why)), []).append(rel)
    byte_stats = [f"逐字节相同：**{same}/{len(common)}**（仅参考有：{sorted(ref_pages-new_pages)}；仅重建有：{sorted(new_pages-ref_pages)}）"]
    for k, v in sorted(cat.items(), key=lambda x: -len(x[1])):
        byte_stats.append(f"字节不同但内容等价：{len(v)} 个 —— {k}")

    ok = not problems
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("# 重建 diff 验证报告\n\n")
        f.write(f"- 参考产物：`{os.path.relpath(REF, ROOT)}`（SeverusZh/SeverusBlog@main 2025-04-08 发布）\n")
        f.write(f"- 重建产物：`{os.path.relpath(NEW, ROOT)}`\n")
        f.write(f"- 判定：**{'PASS' if ok else 'FAIL'}**\n\n")
        f.write(f"## 统计\n\n")
        f.write(f"- 文章页一致：{stats['post_ok']}/{stats['post_total']}\n")
        f.write(f"- 其他 HTML 页一致：{stats['page_ok']}/{stats['page_total']}\n")
        f.write(f"- search.json：{sj[0] if sj else 'n/a'}\n")
        f.write(f"- 路径集合：仅参考 {len(only_ref)} 个，仅重建 {len(only_new)} 个\n\n")
        f.write("## 字节级比对\n\n")
        f.write("".join(f"- {x}\n" for x in byte_stats))
        f.write("\n## 问题清单\n\n")
        f.write("\n".join(f"- {p}" for p in problems) if problems else "无\n")
        f.write("\n")
    print(f"post {stats['post_ok']}/{stats['post_total']}  "
          f"pages {stats['page_ok']}/{stats['page_total']}  "
          f"problems={len(problems)}  => {'PASS' if ok else 'FAIL'}")
    for p in problems[:25]:
        print("  -", p)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
