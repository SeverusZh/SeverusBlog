#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 tools/style-spec.md 规范化 source/_posts 下的文章。

用法：
    python3 tools/normalize-posts.py                  # 全量规范化
    python3 tools/normalize-posts.py --step escapes   # 只清理转义（用于证明渲染中性）
    python3 tools/normalize-posts.py --check          # 只报告改动，不写回

设计原则：
- 幂等：重复执行结果不变。
- 代码块内容（含 Tab 与行尾空格）逐字节保留：先把代码块换成占位行，整篇当散文处理，最后还原。
- 只做 style-spec 列明的改动，不改写正文与代码内容。
"""

import argparse
import glob
import json
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS = os.path.join(ROOT, "source", "_posts")

FENCE = re.compile(r"^(`{3,}|~{3,})(.*)$")
HEAD = re.compile(r"^(#{1,6})(\s+)(.*)$")
WC_LINE = re.compile(r"^字数：\d+，阅读时间：\d+分钟$")
DEAD_IMG = re.compile(r"^!\[[^\]]*\]\(file:///[^)]*\)$")
OL_ITEM = re.compile(r"^(\s*)(\d+)\.(\s+)(.*)$")
UL_ITEM = re.compile(r"^(\s*)([*+])(\s+)(.*)$")
PLACEHOLDER = "\x00CODE{}\x00"


def protect_code(body):
    """代码块 -> 单行占位符，返回 (散文流, 代码块列表)。"""
    lines = body.split("\n")
    out, codes, cur, in_code = [], [], [], False
    for line in lines:
        if FENCE.match(line):
            if not in_code:
                cur = [line]
                in_code = True
            else:
                cur.append(line)
                codes.append("\n".join(cur))
                out.append(PLACEHOLDER.format(len(codes) - 1))
                cur, in_code = [], False
            continue
        if in_code:
            cur.append(line)
        else:
            out.append(line)
    if cur:                                        # 未闭合围栏：按原文保留
        codes.append("\n".join(cur))
        out.append(PLACEHOLDER.format(len(codes) - 1))
    return out, codes


# --------------------------------------------------------------------------
# 散文级改动
# --------------------------------------------------------------------------


def fix_escapes(lines):
    """安全清理多余转义（保守，避免改变渲染）。

    - 词中 `\\_`（两侧为字母/数字）去掉反斜杠：CommonMark 不允许词中 `_` 形成强调。
    - `\\*` / `\\~`：本段内该字符总共只出现一次时去掉反斜杠（单字符无法配对成强调）。
    - `\\[`、`\\]`、`\\\\` 一律保留（数学式/引用语法的一部分）。
    """
    text = "\n".join(lines)
    text = re.sub(r"(?<=[A-Za-z0-9])\\_", "_", text)
    out = []
    for seg in re.split(r"(\n\s*\n)", text):          # 以段落为单位，保留分隔符
        if seg and not re.fullmatch(r"\n\s*\n", seg):
            for ch in ("*", "~", "_"):
                esc = len(re.findall(r"\\" + re.escape(ch), seg))
                raw = len(re.findall(r"(?<!\\)" + re.escape(ch), seg))
                if esc == 1 and raw == 0:
                    seg = seg.replace("\\" + ch, ch)
        out.append(seg)
    return "".join(out).split("\n")


def fix_lists(lines):
    """无序列表统一 `-`。

    有序列表**保留作者显式编号**：这些文章的有序步骤常被代码块/段落打断，
    marked 会把每一段渲染成 `<ol start="N">`，编号必须延续；重置成 1. 会让
    页面显示成一排 “1.”（曾因此产生可见回归，见 verification 记录）。
    """
    out = []
    for line in lines:
        if PLACEHOLDER.split("{}")[0] in line:
            out.append(line)
            continue
        m = UL_ITEM.match(line)
        out.append(f"{m.group(1)}- {m.group(4)}" if m else line)
    return out


def fix_headings(lines, stats):
    """首标题为 ##，且层级不跳级（MD001）。"""
    lv = [len(m.group(1)) for m in (HEAD.match(l) for l in lines) if m]
    if not lv:
        return lines
    # 以“首个标题”为基准（而非最小层级）：个别文章末尾存在层级反转的标题
    shift = 2 - lv[0]
    mapping, prev = [], None
    for x in lv:
        y = max(2, x + shift)
        if prev is not None and y > prev + 1:
            y = prev + 1
        mapping.append(y)
        prev = y
    if mapping == lv:
        return lines
    stats["heading_fix"] += 1
    idx, out = 0, []
    for line in lines:
        m = HEAD.match(line)
        if m and idx < len(mapping):
            out.append("#" * mapping[idx] + m.group(2) + m.group(3))
            idx += 1
        else:
            out.append(line)
    return out


def normalize_prose(lines, title, step, stats):
    if step == "escapes":
        return fix_escapes(lines)

    # 1) 开头的「字数：…」工具行
    while lines and lines[0].strip() == "":
        lines.pop(0)
    if lines and WC_LINE.match(lines[0].strip()):
        lines.pop(0)
        while lines and lines[0].strip() == "":
            lines.pop(0)
        stats["wordcount_line"] += 1

    lines = fix_escapes(lines)

    # 2) 与标题重复的首个 H1
    for i, l in enumerate(lines):
        if l.strip() == "":
            continue
        m = HEAD.match(l)
        if m and len(m.group(1)) == 1 and m.group(3).strip() == title:
            lines.pop(i)
            while i < len(lines) and lines[i].strip() == "":
                lines.pop(i)
            stats["dup_h1"] += 1
        break

    lines = fix_lists(lines)
    lines = fix_headings(lines, stats)

    # 3) 删除指向本地临时文件的坏链图片
    keep = []
    for l in lines:
        if DEAD_IMG.match(l.strip()):
            stats["dead_img"] += 1
            continue
        keep.append(l)
    lines = keep

    # 4) 空白规范：行尾去空格、连续空行压一个
    text = "\n".join(l.rstrip() for l in lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = text.split("\n")

    # 5) NBSP -> 普通空格
    n = sum(l.count("\u00a0") for l in lines)
    if n:
        lines = [l.replace("\u00a0", " ") for l in lines]
        stats["nbsp"] += n
    while lines and lines[-1].strip() == "":
        lines.pop()
    return lines


# --------------------------------------------------------------------------
# front matter
# --------------------------------------------------------------------------


def split_file(text):
    parts = text.split("---", 2)
    return parts[0], parts[1], parts[2]          # before, fm, rest


def fmt_dt(v):
    """front matter 日期统一成 YAML 可读字符串。"""
    import datetime
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, datetime.date):
        return v.strftime("%Y-%m-%d")
    return str(v).strip()


def parse_fm(fm):
    """用 YAML 解析 front matter（正确反解引号，避免重复转义）。"""
    d = yaml.safe_load(fm) or {}
    tags = d.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    return {
        "title": str(d.get("title", "")).strip(),
        "date": fmt_dt(d["date"]) if d.get("date") is not None else "",
        "updated": fmt_dt(d["updated"]) if d.get("updated") is not None else "",
        "tags": [str(t).strip() for t in tags],
    }


def yaml_scalar(s):
    if re.fullmatch(r"[A-Za-z0-9\u4e00-\u9fff ._+\-/&()]+", s) and not s.strip().startswith(("-", "?", ":")):
        return s
    return json.dumps(s, ensure_ascii=False)


def build_fm(data, stats):
    fm = ["---", f"title: {yaml_scalar(data['title'])}", f"date: {data['date']}"]
    if data.get("updated"):
        fm.append(f"updated: {data['updated']}")
    tags = [t.lstrip("-").strip() for t in data["tags"]]
    if tags != data["tags"]:
        stats["tag_fix"] += 1
    if tags:
        fm.append("tags:")
        for t in tags:
            fm.append(f"  - {yaml_scalar(t)}")
    fm.append("---")
    return "\n".join(fm)


# --------------------------------------------------------------------------


def normalize_file(path, step, check):
    text = open(path, encoding="utf-8").read()
    stats = dict(wordcount_line=0, dup_h1=0, heading_fix=0, dead_img=0,
                 nbsp=0, tag_fix=0)
    _before, fm, rest = split_file(text)
    data = parse_fm(fm)

    lead = re.match(r"^(\s*)", rest).group(1) or "\n\n"
    body = rest[len(lead):]
    flow, codes = protect_code(body)
    flow = normalize_prose(flow, data["title"], step, stats)
    new_body = "\n".join(flow).replace("\x00", "\x00")
    for i, code in enumerate(codes):
        new_body = new_body.replace(PLACEHOLDER.format(i), code)

    if step == "escapes":
        out = "---" + fm + "---" + lead + new_body.strip("\n") + "\n"
    else:
        out = build_fm(data, stats) + "\n\n" + new_body.strip("\n") + "\n"

    changed = out != text
    if changed and not check:
        open(path, "w", encoding="utf-8").write(out)
    return changed, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", default="full", choices=["full", "escapes"])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--posts", default=POSTS)
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.posts, "*.md")))
    total = dict(wordcount_line=0, dup_h1=0, heading_fix=0, dead_img=0,
                 nbsp=0, tag_fix=0)
    changed = 0
    for f in files:
        c, st = normalize_file(f, args.step, args.check)
        changed += 1 if c else 0
        for k in total:
            total[k] += st[k]
    print(f"文章 {len(files)} 篇，{'将有' if args.check else '已'}改动 {changed} 篇")
    print("改动统计:", {k: v for k, v in total.items() if v})
    return 0


if __name__ == "__main__":
    sys.exit(main())
