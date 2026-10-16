#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 tools/style-spec.md 检查 source/_posts 下的文章。

用法：python3 tools/lint-posts.py [--posts DIR]
退出码 0 = 全部合规。
"""

import argparse
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS = os.path.join(ROOT, "source", "_posts")

FENCE = re.compile(r"^(`{3,})(.*)$")
BAD_IMG = re.compile(r"!\[[^\]]*\]\(file:///")
WC_LINE = re.compile(r"^字数：\d+，阅读时间：\d+分钟$")
UL_ITEM = re.compile(r"^(\s*)([*+])\s")
OL_ITEM = re.compile(r"^(\s*)(\d+)\.\s")


def split_lines(body):
    """返回 [(is_code, lineno, line)]。"""
    out, in_code = [], False
    for i, line in enumerate(body.split("\n"), 1):
        m = FENCE.match(line)
        if m:
            out.append((in_code, i, line))
            in_code = not in_code
            continue
        out.append((in_code, i, line))
    return out


def check_file(path):
    errs = []
    text = open(path, encoding="utf-8").read()
    name = os.path.basename(path)
    if "\r" in text:
        errs.append("含 CR（应为 LF）")
    if not text.endswith("\n") or text.endswith("\n\n"):
        errs.append("文末应为恰好一个换行")
    if not text.startswith("---\n"):
        errs.append("缺少 front matter")
        return errs

    fm, body = text.split("---", 2)[1], text.split("---", 2)[2]
    keys = [m.group(1) for m in re.finditer(r"^([a-z_]+):", fm, re.M)]
    if keys != [k for k in ["title", "date", "updated", "tags"] if k in keys]:
        errs.append(f"front matter 字段顺序应为 title/date/updated/tags，实际 {keys}")
    if "categories" in keys:
        errs.append("不应使用 categories")
    m = re.search(r"^date:\s*(.+)$", fm, re.M)
    if not m or not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", m.group(1).strip()):
        errs.append(f"date 格式应为 YYYY-MM-DD HH:mm:ss，实际 {m.group(1).strip() if m else '缺失'}")
    for t in re.findall(r"^\s+-\s*(.*)$", fm, re.M):
        if t.strip().startswith("-"):
            errs.append(f"标签名不应带前缀符号：{t.strip()}")
    title = re.search(r'^title:\s*(.*)$', fm, re.M)
    title = title.group(1).strip().strip('"') if title else ""

    lines = split_lines(body)
    if not any(FENCE.match(l) for _c, _i, l in lines) and lines and lines[-1][2] == "":
        pass

    headings = []
    fence_count = 0
    for is_code, i, line in lines:
        if FENCE.match(line):
            fence_count += 1
            lang = FENCE.match(line).group(2).strip()
            if not is_code and lang and lang != lang.lower():
                errs.append(f"第 {i} 行：代码语言应小写（{lang}）")
            continue
        if is_code:
            continue
        if line != line.rstrip():
            errs.append(f"第 {i} 行：散文行尾有空格")
        if "\t" in line:
            errs.append(f"第 {i} 行：散文含 Tab")
        if "\u00a0" in line:
            errs.append(f"第 {i} 行：散文含 NBSP")
        if "&nbsp;" in line:
            errs.append(f"第 {i} 行：应使用普通空格而不是 &nbsp;")
        if WC_LINE.match(line.strip()):
            errs.append(f"第 {i} 行：残留「字数：…」工具行")
        if BAD_IMG.search(line):
            errs.append(f"第 {i} 行：残留本地坏链图片")
        hm = re.match(r"^(#{1,6})\s+(.*)$", line)
        if hm:
            headings.append((len(hm.group(1)), i, hm.group(2).strip()))
        um = UL_ITEM.match(line)
        if um:
            errs.append(f"第 {i} 行：无序列表应使用 `-`（实际 {um.group(2)}）")

    if fence_count % 2:
        errs.append("代码围栏未闭合")
    if headings:
        if headings[0][0] != 2:
            errs.append(f"第 {headings[0][1]} 行：首个标题层级应为 ##（实际 {'#' * headings[0][0]}）")
        prev = None
        for lv, i, _t in headings:
            if prev is not None and lv > prev + 1:
                errs.append(f"第 {i} 行：标题层级跳级（{'#' * prev} -> {'#' * lv}）")
            prev = lv
    run = 0
    for is_code, i, line in lines:
        if is_code:
            run = 0
            continue
        run = run + 1 if line.strip() == "" else 0
        if run >= 3:
            errs.append(f"第 {i} 行附近：散文出现连续 3 个以上空行")
            break
    # 有序列表编号连续
    counters = {}
    for is_code, i, line in lines:
        if is_code:
            continue
        om = OL_ITEM.match(line)
        if om:
            indent, n = om.group(1), int(om.group(2))
            want = counters.get(indent, 0) + 1
            if n != want:
                errs.append(f"第 {i} 行：有序列表编号应为 {want}（实际 {n}）")
            counters[indent] = n
            for k in [k for k in counters if len(k) > len(indent)]:
                del counters[k]
        elif line.strip():
            counters.clear()
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--posts", default=POSTS)
    args = ap.parse_args()
    files = sorted(glob.glob(os.path.join(args.posts, "*.md")))
    bad = 0
    for f in files:
        errs = check_file(f)
        if errs:
            bad += 1
            print(f"✗ {os.path.basename(f)}")
            for e in errs[:8]:
                print("   ", e)
    print(f"检查 {len(files)} 篇：合规 {len(files) - bad}，违规 {bad}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
