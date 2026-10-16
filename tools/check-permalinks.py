#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验构建产物的 URL 集合与历史站点完全一致。

Hexo 的 permalink 日期按「构建机器的时区」渲染，因此时区不同会改变文章 URL
（例如 2025-04-08 凌晨的文章在 UTC 下会变成 2025-04-07），进而破坏旧链接与
Valine 评论。此脚本作为 CI 守卫：URL 集合一旦漂移就让构建失败。

用法：python3 tools/check-permalinks.py [public 目录]
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "public")
LIST = os.path.join(ROOT, "tools", "expected-paths.txt")


def main():
    expected = {l.strip() for l in open(LIST, encoding="utf-8") if l.strip()}
    missing = sorted(p for p in expected if not os.path.exists(os.path.join(PUBLIC, p)))
    if missing:
        print(f"URL 校验失败：{len(missing)}/{len(expected)} 个预期路径缺失")
        for p in missing[:15]:
            print("  缺失:", p)
        print("\n最常见原因：构建时区不是 Asia/Shanghai（请设 TZ=Asia/Shanghai）")
        return 1
    print(f"URL 校验通过：{len(expected)} 个路径全部存在")
    return 0


if __name__ == "__main__":
    sys.exit(main())
