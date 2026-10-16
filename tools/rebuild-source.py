#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rebuild-source.py — 从幸存的 Hexo 生成产物反向重建 Markdown 写作源。

输入：/home/sev/dsh-projects/Blog/repo （SeverusZh/SeverusBlog@main 的生成产物）
输出：staging/source/_posts/*.md  与  staging/source/image/**

设计要点
- 代码块：Hexo highlight 的 <figure class="highlight LANG"><table>… 还原为围栏代码块。
- 图片：产物中的 /SeverusBlog/image/… 还原为源工程里的 /image/…（Hexo prependRoot 会补回 /SeverusBlog/）。
- 字数行 <p>字数：N，阅读时间：M分钟</p> 是丢失的站点级注入，不是源内容，转换时剔除。
- <!-- more -->：由列表页摘要文本反推插入位置。
- 该脚本是一次性迁移工具，保留在仓库内以便复核。
"""

import glob
import html
import json
import os
import re
import shutil
import urllib.parse
import sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 历史产物所在目录（本次迁移用的是 git 中 a59a2bf 的检出，即 2025-04-08 线上站点）
REF = os.environ.get("REBUILD_REF", "")
OUT = os.environ.get("REBUILD_OUT", os.path.join(ROOT, "source"))
POSTS_OUT = os.path.join(OUT, "_posts")
IMAGES_OUT = os.path.join(OUT, "image")
# main() 会按 --ref/--out 覆盖以上路径

WC_RE = re.compile(r"<p>字数：\d+，阅读时间：\d+分钟</p>")
INSERT_MORE = False   # 原站未使用 <!-- more -->（见 main() 说明）
BARE_FENCES = False   # 原站围栏带显式语言（等于产物 class）；auto_detect=true 只用于无语言的块
CONTENT_RE = re.compile(r'<div class="post__content">(.*?)\n    </div>', re.S)
FIG_RE = re.compile(r'<figure class="highlight(?: ([^"]*))?">(.*?)</figure>', re.S)
VOID = {"br", "img", "hr", "input", "meta", "link", "area", "base", "col",
        "embed", "source", "track", "wbr"}

# --------------------------------------------------------------------------
# 迷你 DOM
# --------------------------------------------------------------------------


class Node:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = attrs
        self.children = []

    def text(self):
        """节点可见文本（已解码实体）。

        用于代码块/代码片段/表格等需要真实字符的场景；
        普通文本走 esc_text，那里会保留 `&#96;` 的原始写法。
        """
        out = []
        for c in self.children:
            out.append(c if isinstance(c, str) else c.text())
        return html.unescape("".join(out))

    def iter_elements(self):
        for c in self.children:
            if not isinstance(c, str):
                yield c


class MiniDOM(HTMLParser):
    def __init__(self):
        # convert_charrefs=False：必须区分 `&#96;`（原 Markdown 里的实体写法）
        # 与裸反引号，否则重建后源码与产物对不上。
        super().__init__(convert_charrefs=False)
        self.root = Node("#root", {})
        self.stack = [self.root]

    def handle_entityref(self, name):
        self.stack[-1].children.append(f"&{name};")

    def handle_charref(self, name):
        self.stack[-1].children.append(f"&#{name};")

    def handle_starttag(self, tag, attrs):
        n = Node(tag, {k: (v or "") for k, v in attrs})
        self.stack[-1].children.append(n)
        if tag not in VOID:
            self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, {k: (v or "") for k, v in attrs}))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse(fragment):
    p = MiniDOM()
    p.feed(fragment)
    p.close()
    return p.root


# --------------------------------------------------------------------------
# 代码块
# --------------------------------------------------------------------------


def figure_to_code(lang, inner):
    """把 Hexo highlight 的 figure 还原成围栏代码块。

    行数以左侧 gutter 为准：源码里代码块末尾的空行在渲染后会变成多余
    <br>，而 gutter 记录了真实行数，据此补齐才能做到逐字一致。
    """
    gm = re.search(r'<td class="gutter">(.*?)</td>', inner, re.S)
    nlines = len(re.findall(r'<span class="line">', gm.group(1))) if gm else 0
    m = re.search(r'<td class="code">(.*?)</td>', inner, re.S)
    if not m:
        return None
    pm = re.search(r"<pre>(.*?)</pre>", m.group(1), re.S)
    body = pm.group(1) if pm else m.group(1)
    body = re.sub(r"<br\s*/?>", "\n", body)
    body = re.sub(r"<[^>]+>", "", body)          # 去掉 line/token 的 span
    body = html.unescape(body)
    if "\u00a0" in body:                          # Hexo 旧版把缩进写成 &nbsp;
        body = body.replace("\u00a0", " ")
    lines = body.split("\n")
    while lines and lines[-1].strip() == "":
        lines.pop()
    while nlines and len(lines) < nlines:
        lines.append("")                          # 补回源码末尾的空行
    code = "\n".join(lines)
    fence = "```"
    while fence in code:
        fence += "`"
    head = fence if BARE_FENCES else fence + (lang or "")
    return f"{head}\n{code}\n{fence}"


# --------------------------------------------------------------------------
# 文本转义
# --------------------------------------------------------------------------

INLINE_ESCAPE = str.maketrans({
    "\\": "\\\\", "*": "\\*", "_": "\\_", "`": "\\`",
    "[": "\\[", "]": "\\]", "~": "\\~",
})
LINE_START = re.compile(r"^(\s*)([#>+\-]|\d+\.)")


BT_PLACEHOLDER = "\x01"


def esc_text(t):
    """文本节点 -> markdown。

    解析器保留实体原貌：`&#96;` 是原作者写的实体，重建时必须原样写回；
    其余实体先解码再按 markdown 规则转义（裸反引号转义后渲染仍是裸反引号）。
    """
    if "&" in t or BT_PLACEHOLDER in t:
        t = t.replace("&#96;", BT_PLACEHOLDER)
        t = html.unescape(t)
        t = t.translate(INLINE_ESCAPE)
        return t.replace(BT_PLACEHOLDER, "&#96;")
    return t.translate(INLINE_ESCAPE)


def esc_line_start(t):
    m = LINE_START.match(t)
    if m:
        return f"{m.group(1)}\\{m.group(2)}" + t[m.end():]
    return t


# --------------------------------------------------------------------------
# 行内转换
# --------------------------------------------------------------------------

IMG_PREFIX = "/SeverusBlog/"


def fix_src(src):
    if src.startswith(IMG_PREFIX):
        return "/" + src[len(IMG_PREFIX):]
    return src


BLOCK_TAGS = {"p", "ul", "ol", "blockquote", "table", "figure", "pre", "div", "hr",
              "h1", "h2", "h3", "h4", "h5", "h6", "script", "style", "figcaption",
              "thead", "tbody", "tr", "td", "th"}


def inline_element(c):
    """单个行内元素 -> markdown。"""
    t = c.tag
    if t in ("strong", "b"):
        return "**" + inline_children(c.children) + "**"
    if t in ("em", "i"):
        return "*" + inline_children(c.children) + "*"
    if t in ("del", "s"):
        return "~~" + inline_children(c.children) + "~~"
    if t == "code":
        code = c.text()
        tick = "`"
        while tick in code:
            tick += "`"
        pad = " " if code.startswith("`") or code.endswith("`") else ""
        return f"{tick}{pad}{code}{pad}{tick}"
    if t == "a":
        if "headerlink" in c.attrs.get("class", ""):
            return ""                      # 标题锚点，重渲染时会再生成
        href = fix_src(c.attrs.get("href", ""))
        return f"[{inline_children(c.children) or href}]({href})"
    if t == "img":
        return f"![{c.attrs.get('alt', '')}]({fix_src(c.attrs.get('src', ''))})"
    if t == "br":
        return "\n"
    return inline_children(c.children)


def inline_children(children):
    """行内子节点序列 -> markdown（保持行内语义，不拆成块）。"""
    out = []
    for c in children:
        out.append(esc_text(c) if isinstance(c, str) else inline_element(c))
    return "".join(out)


# --------------------------------------------------------------------------
# 块级转换
# --------------------------------------------------------------------------


def code_placeholder(i):
    return f"\x00CODE{i}\x00"


PLACEHOLDER_RE = re.compile(r"^\x00CODE(\d+)\x00$")


class CodeRef:
    """块级位置上的代码块引用（占位符不参与行内拼接）。"""
    __slots__ = ("idx",)

    def __init__(self, idx):
        self.idx = idx


def render_code(codes, idx):
    lang, inner = codes[idx]
    return figure_to_code(lang, inner) or ""


def render_table(node):
    rows = []
    head = []

    def collect(tr):
        cells = []
        for td in tr.children:
            if isinstance(td, str):
                continue
            if td.tag in ("td", "th"):
                cells.append(inline_children(td.children).replace("|", "\\|").strip().replace("\n", " "))
        return cells

    def walk(n):
        nonlocal head
        for c in n.children:
            if isinstance(c, str):
                continue
            if c.tag == "tr":
                cells = collect(c)
                if not head and any(x.tag == "th" for x in c.children if not isinstance(x, str)):
                    head = cells
                elif not head and not rows:
                    head = cells
                else:
                    rows.append(cells)
            elif c.tag in ("thead", "tbody", "tfoot"):
                walk(c)

    walk(node)
    if not head:
        return ""
    width = max([len(head)] + [len(r) for r in rows]) if rows else len(head)
    head += [""] * (width - len(head))
    lines = ["| " + " | ".join(head) + " |",
             "| " + " | ".join(["---"] * width) + " |"]
    for r in rows:
        r += [""] * (width - len(r))
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def render_list(node, codes, ordered=False, indent=0):
    """列表 -> markdown。

    <li> 的直接内容通常是行内序列（文本 + <code>/<strong>/<a>…），必须整行拼接；
    只有块级子节点（嵌套列表、代码块、引用等）才另起行。

    关键：项内块的缩进必须等于**标记宽度**（`- ` 为 2，`1. ` 为 3，`10. ` 为 4），
    否则块会掉出列表项，把一条列表割裂成多个 <ol>（编号会各起 1）。
    """
    items = [c for c in node.children if not isinstance(c, str) and c.tag == "li"]
    loose = any(any(not isinstance(g, str) and g.tag == "p" for g in li.children)
                for li in items)
    out = []
    for idx, li in enumerate(items):
        marker = f"{idx + 1}. " if ordered else "- "
        pad = " " * (indent + len(marker))
        inline_nodes, blocks, first_p_used = [], [], False
        for g in li.children:
            if isinstance(g, str):
                m = PLACEHOLDER_RE.match(g.strip())
                if m:
                    blocks.append(CodeRef(int(m.group(1))))
                else:
                    inline_nodes.append(g)
            elif g.tag == "p":
                # 第一个 <p> 并入行内首行；后续 <p> 是项内独立段落
                if not first_p_used and not blocks:
                    inline_nodes.append(g)
                    first_p_used = True
                else:
                    blocks.append(g)
            elif g.tag in BLOCK_TAGS:
                blocks.append(g)
            else:
                inline_nodes.append(g)
        content = inline_children(inline_nodes).strip()
        head = marker + content if content else marker.rstrip()
        lines = [(" " * indent) + head]
        for b in blocks:
            if loose and content:
                lines.append("")                # 松散列表：项内块之间需空行
            if isinstance(b, CodeRef):
                bm, prefix = render_code(codes, b.idx), pad
            elif getattr(b, "tag", "") in ("ul", "ol"):
                # 嵌套列表自缩进（marker 落在本项内容缩进处），不要再叠加 pad
                bm = render_list(b, codes, ordered=(b.tag == "ol"),
                                 indent=indent + len(marker))
                prefix = ""
            else:
                bm, prefix = render_block(b, codes, 0), pad
            keep_blank = isinstance(b, CodeRef) or getattr(b, "tag", "") in ("ul", "ol")
            for l in bm.split("\n"):
                if not l.strip():
                    if keep_blank:
                        lines.append("")       # 代码块空行 / 松散子列表的空行必须保留
                    continue
                lines.append(prefix + l)
        out.append("\n".join(lines))
    sep = "\n\n" if loose else "\n"
    return sep.join(out)


def render_block(c, codes, indent=0):
    """单个块级元素 -> markdown。"""
    t = c.tag
    if t == "p":
        # 不 strip：原站有段落带前导空格（<p> 配置…），标记法能保留
        body = inline_children(c.children)
        return body if body.strip() else ""
    if re.fullmatch(r"h[1-6]", t):
        txt = inline_children(c.children).strip()
        return ("#" * int(t[1]) + " " + txt) if txt else ""
    if t in ("ul", "ol"):
        return render_list(c, codes, ordered=(t == "ol"), indent=indent)
    if t == "blockquote":
        inner = "\n\n".join(x for x in render_children(c, codes, indent) if x.strip())
        return "\n".join("> " + l if l.strip() else ">" for l in inner.split("\n"))
    if t == "table":
        return render_table(c)
    if t == "figure":
        # 正常情况下 highlight 的 figure 已被占位符替换；走到这里说明漏匹配。
        return inline_children(c.children).strip()
    if t == "img":
        return inline_element(c)
    if t == "hr":
        return "---"
    if t == "pre":
        raw = html.unescape(re.sub(r"<[^>]+>", "", c.text()))
        fence = "```"
        while fence in raw:
            fence += "`"
        return f"{fence}\n{raw.strip()}\n{fence}"
    if t == "div":
        return "\n\n".join(x for x in render_children(c, codes, indent) if x.strip())
    if t in ("script", "style", "figcaption"):
        return ""
    return inline_children(c.children).strip()


def render_children(node, codes, indent=0):
    """把容器下的块级子节点转换成 markdown 块序列。

    与 node.children 一一对应（无输出的子节点占一个空串），
    这样摘要反推出的块下标可以直接定位 <!-- more -->。
    """
    blocks = []
    for c in node.children:
        if isinstance(c, str):
            m = PLACEHOLDER_RE.match(c.strip())
            if m:
                blocks.append(render_code(codes, int(m.group(1))))
                continue
            blocks.append(esc_line_start(esc_text(c.strip())) if c.strip() else "")
            continue
        if c.tag in BLOCK_TAGS:
            blocks.append(render_block(c, codes, indent))
        else:
            blocks.append(inline_element(c).strip())
    return blocks


def strip_md(s):
    """粗略去掉 markdown 标记，用于与产物纯文本比对。"""
    s = re.sub(r"```.*?```", "", s, flags=re.S)
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"^\s{0,3}#{1,6}\s*", "", s, flags=re.M)
    s = re.sub(r"^\s{0,3}[-*+]\s+", "", s, flags=re.M)
    s = re.sub(r"^\s{0,3}\d+\.\s+", "", s, flags=re.M)
    s = s.replace("**", "").replace("*", "").replace("\\", "")
    return re.sub(r"\s+", "", s)


# --------------------------------------------------------------------------
# 摘要 → <!-- more --> 位置
# --------------------------------------------------------------------------


def entries_from_list_pages():
    """从列表页收集 标题 -> 摘要纯文本。"""
    res = {}
    for pg in ("index.html", "page/2/index.html", "page/3/index.html", "page/4/index.html",
               "page/5/index.html"):
        path = os.path.join(REF, pg)
        if not os.path.exists(path):
            continue
        raw = open(path, encoding="utf-8").read()
        for chunk in raw.split("<div class='post-entry content-card'>")[1:]:
            tm = re.search(r'<h2 class="post-entry__title">\s*(.*?)\s*</h2>', chunk, re.S)
            if not tm:
                continue
            title = html.unescape(tm.group(1)).strip()
            pm = re.search(r"<p>\s*(.*?)\s*</p>", chunk, re.S)
            exc = html.unescape(re.sub(r"<[^>]+>", "", pm.group(1))).strip() if pm else ""
            exc = re.sub(r"^\s*字数：\d+，阅读时间：\d+分钟\s*", "", exc)
            res.setdefault(title, re.sub(r"\s+", "", exc))
    return res


def norm(s):
    return re.sub(r"\s+", "", s)


def find_more_index(blocks_texts, excerpt_norm):
    """返回应在其后插入 <!-- more --> 的块下标；找不到返回 None。"""
    if not excerpt_norm:
        return None
    acc = ""
    for i, t in enumerate(blocks_texts):
        acc += norm(t)
        if acc == excerpt_norm:
            return i
        if len(acc) > len(excerpt_norm) and not excerpt_norm.startswith(acc[:len(excerpt_norm)]):
            return None
    return None


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------


def load_meta():
    data = json.load(open(os.path.join(REF, "search.json"), encoding="utf-8"))
    meta = {}
    for p in data:
        u = p.get("url", "")
        if not re.match(r"^/SeverusBlog/20\d\d/", u):
            continue
        path = urllib.parse.unquote(u.replace("/SeverusBlog/", "").rstrip("/"))
        meta[path] = {
            "title": p.get("title", ""),
            "date": p.get("date", ""),
            "tags": [t[0] for t in p.get("tags", [])],
        }
    return meta


def fmt_date(iso):
    """UTC ISO -> 北京时间 'YYYY-MM-DD HH:mm:ss'。"""
    import datetime
    dt = datetime.datetime.strptime(iso.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S.%f%z")
    dt = dt.astimezone(datetime.timezone(datetime.timedelta(hours=8)))
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def yaml_scalar(s):
    if re.fullmatch(r"[A-Za-z0-9\u4e00-\u9fff ._+\-/&()]+", s) and not s.strip().startswith(("-", "?", ":")):
        return s
    return json.dumps(s, ensure_ascii=False)


def main():
    global REF, OUT
    import argparse
    ap = argparse.ArgumentParser(description="从历史构建产物反向重建 Markdown 写作源")
    ap.add_argument("--ref", default=REF, help="历史产物目录（含 search.json 与 image/）")
    ap.add_argument("--out", default=OUT, help="输出目录（默认写入仓库 source/）")
    ap.add_argument("--posts-out", default="", help="仅指定文章输出目录")
    a = ap.parse_args()
    if not a.ref or not os.path.isdir(a.ref):
        print("错误：需要 --ref 指向历史构建产物目录（例如 git 中 a59a2bf 的检出）")
        return 2
    REF = os.path.abspath(a.ref)
    OUT = os.path.abspath(a.out)
    global POSTS_OUT, IMAGES_OUT
    POSTS_OUT = a.posts_out or os.path.join(OUT, "_posts")
    IMAGES_OUT = os.path.join(OUT, "image")
    meta = load_meta()
    excerpts = entries_from_list_pages()
    os.makedirs(POSTS_OUT, exist_ok=True)
    os.makedirs(IMAGES_OUT, exist_ok=True)

    post_dirs = sorted(glob.glob(os.path.join(REF, "20[0-9][0-9]", "*", "*", "*")))
    report = []
    for d in post_dirs:
        rel = os.path.relpath(d, REF)
        if rel not in meta:
            continue
        info = meta[rel]
        raw = open(os.path.join(d, "index.html"), encoding="utf-8").read()
        cm = CONTENT_RE.search(raw)
        if not cm:
            report.append((rel, "NO_CONTENT", 0, 0))
            continue
        # 字数行：原站由某个写作工具/过滤器生成，无法用任何已知插件公式复现
        # （hexo-wordcount 的 wordcount/min2read 均对不上，偏差不成比例）。
        # 因此按原样保留为正文首段，保证 38 篇归档文章重建后完全一致。
        m_wc = WC_RE.search(cm.group(1))
        wc_line = m_wc.group(0)[3:-4] if m_wc else ""      # 去掉 <p> </p>
        content = WC_RE.sub("", cm.group(1), count=1)

        # 代码块抽出为占位符
        codes = []

        def repl(m):
            codes.append((m.group(1), m.group(2)))
            return code_placeholder(len(codes) - 1)

        protected = FIG_RE.sub(repl, content)
        dom = parse(protected)

        # 摘要 -> more 位置（DOM 顶层子节点与 blocks 一一对应）
        texts = []
        for c in dom.children:
            if isinstance(c, str):
                texts.append(c.strip())
            else:
                texts.append(html.unescape(re.sub(r"<[^>]+>", "", c.text())))
        # 结论（已用 hexo-util 实测验证）：原站没有使用 <!-- more -->，
        # 列表页摘要来自主题的 meta.auto_excerpt = strip_html(truncate(content, {length: 159}))。
        # 因此这里不再插入更多标记，保留推断逻辑仅供复核。
        more_idx = None if not INSERT_MORE else find_more_index(texts, excerpts.get(info["title"], ""))

        blocks = render_children(dom, codes)

        def sub_code(m):
            lang, inner = codes[int(m.group(1))]
            return figure_to_code(lang, inner) or ""

        blocks = [re.sub(r"\x00CODE(\d+)\x00", sub_code, b) for b in blocks]

        # 定位更多标记：放在 more_idx 之前最后一个非空块之后
        anchor = None
        if more_idx is not None:
            for i in range(min(more_idx, len(blocks) - 1), -1, -1):
                if blocks[i].strip():
                    anchor = i
                    break

        parts = []
        for i, b in enumerate(blocks):
            if not b.strip():
                continue
            parts.append(b)
            if anchor is not None and i == anchor:
                parts.append("<!-- more -->")
        body = "\n\n".join(parts)
        if wc_line:
            body = wc_line + "\n\n" + body

        # updated：原站显示的是源文件 mtime（非帖子日期，29/38 篇不同于 date）。
        # 显式写回产物中的值，避免依赖 mtime（CI 检出后 mtime 会变）。
        local_date = fmt_date(info["date"])[:10]
        um = re.search(r"updated at (\d{4}-\d{2}-\d{2})", raw)
        upd = um.group(1) if um else None

        fm = ["---", f"title: {yaml_scalar(info['title'])}",
              f"date: {fmt_date(info['date'])}"]
        if upd and upd != local_date:
            fm.append(f"updated: {upd}")
        if info["tags"]:
            fm.append("tags:")
            for t in info["tags"]:
                fm.append(f"  - {yaml_scalar(t)}")
        fm.append("---")

        out_path = os.path.join(POSTS_OUT, rel.split("/")[-1] + ".md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(fm) + "\n\n" + body.rstrip() + "\n")
        report.append((rel, "OK", len(body), os.path.getsize(out_path),
                       "more" if anchor is not None else "NO-MORE"))

    # 图片
    src_img = os.path.join(REF, "image")
    if os.path.isdir(src_img):
        for dirpath, _dirs, files in os.walk(src_img):
            for fn in files:
                s = os.path.join(dirpath, fn)
                t = os.path.join(IMAGES_OUT, os.path.relpath(s, src_img))
                os.makedirs(os.path.dirname(t), exist_ok=True)
                shutil.copy2(s, t)

    print(f"参考产物: {REF}")
    print(f"文章 {len(report)} 篇；图片 {sum(len(f) for _, _, f in os.walk(IMAGES_OUT))} 个")
    miss = [r for r in report if r[1] != "OK"]
    print("异常:", miss if miss else "无")
    print("未定位到 more 的文章:",
          [f"{r[0]} ({r[4]})" for r in report if r[4] != "more"] or "无")
    print("正文长度 min/max:",
          min(r[2] for r in report), max(r[2] for r in report))


if __name__ == "__main__":
    main()
