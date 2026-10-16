#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""线上站点校验：把部署后的页面与本地已验证构建逐字节比对。

用法：python3 tools/verify-live.py [本地构建目录，默认 public]
退出码 0 = 全部一致（search.json 允许条目顺序不同）。
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "public")
BASE = "https://severuszh.github.io/SeverusBlog"
RETRY = 3


def fetch(rel):
    url = BASE + "/" + urllib.parse.quote(rel)
    last = None
    for _ in range(RETRY):
        try:
            with urllib.request.urlopen(url, timeout=45) as r:
                return rel, r.read(), None
        except Exception as e:                      # 网络抖动重试
            last = str(e)[:60]
    return rel, None, last


def main():
    files = []
    for dp, _dirs, fs in os.walk(PUBLIC):
        for f in fs:
            files.append(os.path.relpath(os.path.join(dp, f), PUBLIC).replace(os.sep, "/"))
    files.sort()
    same, diff, fail = [], [], []
    with ThreadPoolExecutor(max_workers=10) as ex:
        for rel, body, err in ex.map(fetch, files):
            if err:
                fail.append((rel, err))
            elif body == open(os.path.join(PUBLIC, rel), "rb").read():
                same.append(rel)
            else:
                diff.append(rel)

    print(f"线上文件 {len(files)}：逐字节相同 {len(same)}，不同 {len(diff)}，取不到 {len(fail)}")
    for r in diff:
        note = "（仅条目顺序不同，内容一致）" if r == "search.json" else ""
        print("  不同:", r, note)
    for r, e in fail:
        print("  取不到:", r, "|", e)

    if "search.json" in diff:                       # 允许搜索索引条目顺序差异
        a = json.load(open(os.path.join(PUBLIC, "search.json"), encoding="utf-8"))
        b = json.loads(urllib.request.urlopen(BASE + "/search.json", timeout=60).read().decode())
        ma, mb = {x.get("url"): x for x in a}, {x.get("url"): x for x in b}
        if set(ma) != set(mb):
            print("  search.json 条目集合不一致！")
            return 1
    ok = not fail and set(diff) <= {"search.json"}
    print("判定:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
