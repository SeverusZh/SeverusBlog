---
title: Github Pages上图片显示问题和添加评论
date: 2024-09-10 00:33:35
updated: 2025-03-03
tags:
  - 博客搭建
---

把博客发布到Pages上后，遗憾地发现图片又不能显示了…重新看了下 `index.html`，又是路径的锅。

## 脚本处理

有两种处理思路，一种是修改 `index.html`然后再提交到仓库，但是一来处理量大，二来有些地方匹配不到 `image`，因为直接把相对路径转化了。所以我选择处理自己的markdown文件，格式整齐，处理量小。

这里匹配 `image`并替换，deploy后再替换回来，编辑上就不会有问题了。

```python
import os
import re

# 定义正则表达式匹配规则
pattern = r'image'
replacement = 'image'

# 获取source/_post目录下的所有文件
post_dir = 'source/_posts'
files = [f for f in os.listdir(post_dir) if os.path.isfile(os.path.join(post_dir, f))]

# 批量处理所有文件，将image修改为image
for file in files:
    with open(os.path.join(post_dir, file), 'r', encoding='utf-8') as f:
        content = f.read()
        modified_content = re.sub(pattern, replacement, content)
    with open(os.path.join(post_dir, file), 'w', encoding='utf-8') as f:
        f.write(modified_content)

# 执行hexo g -d命令
os.system("hexo g -d")

# 再次匹配，恢复image为image
for file in files:
    with open(os.path.join(post_dir, file), 'r', encoding='utf-8') as f:
        content = f.read()
        restored_content = re.sub(replacement, pattern, content)
    with open(os.path.join(post_dir, file), 'w', encoding='utf-8') as f:
        f.write(restored_content)
```

如你所见，这是个python程序，需要有python环境才能运行。

## 添加评论

主要是发现主题有这个配置选项，顺便就加上吧。

这里选择的是Valine评论系统，一个无后端评论系统。[链接](https://valine.js.org/quickstart.html)

1. 首先注册LeanCloud账号

2. 创建应用

  ![1725902872641](/image/Github-Pages%E4%B8%8A%E5%9B%BE%E7%89%87%E6%98%BE%E7%A4%BA%E9%97%AE%E9%A2%98%E4%BF%AE%E5%A4%8D%E5%92%8C%E6%B7%BB%E5%8A%A0%E8%AF%84%E8%AE%BA/1725902872641.png)、

1. 应用创建好以后，进入刚刚创建的应用，选择左边的 `设置`>`应用凭证`，找到 `AppID`和 `AppKey`

  ![1725902929116](/image/Github-Pages%E4%B8%8A%E5%9B%BE%E7%89%87%E6%98%BE%E7%A4%BA%E9%97%AE%E9%A2%98%E4%BF%AE%E5%A4%8D%E5%92%8C%E6%B7%BB%E5%8A%A0%E8%AF%84%E8%AE%BA/1725902929116.png)

1. 修改配置文件

  ![1725903043459](/image/Github-Pages%E4%B8%8A%E5%9B%BE%E7%89%87%E6%98%BE%E7%A4%BA%E9%97%AE%E9%A2%98%E4%BF%AE%E5%A4%8D%E5%92%8C%E6%B7%BB%E5%8A%A0%E8%AF%84%E8%AE%BA/1725903043459.png)

重新 `hexo g -d`应该就能看到评论区。
