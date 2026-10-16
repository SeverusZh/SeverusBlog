---
title: Hexo + Github Pages
date: 2024-09-09 22:03:38
updated: 2025-03-03
tags:
  - 博客搭建
---

字数：444，阅读时间：3分钟

本来我打算租用一个服务器来部署这个博客网站的，偶然间发现可以使用Github的Pages服务来进行部署。无论从经济还是实用性的角度感觉都更加优秀。

### 建立仓库

注册Github和SSH本地连接的部分就不详细介绍了， 直接从建立仓库开始说起。

建立仓库的界面如下，创建什么仓库名并不重要。可以选择初始化仓库生成一个README文件。

![1725891377729](/image/Hexo-Github-Page/1725891377729.png)

![1725891447203](/image/Hexo-Github-Page/1725891447203.png)

点击 `Create repository`后就创建完了。

![1725891518856](/image/Hexo-Github-Page/1725891518856.png)

我们需要创建的是一个Github Pages仓库，现在打开仓库的Settings中的Pages，进行如下设置，注意点击Save保存。

![1725892100930](/image/Hexo-Github-Page/1725892100930.png)

出现这样的界面说明已经设置好了。

![1725892203134](/image/Hexo-Github-Page/1725892203134.png)

访问上面框中的网址就能访问你创建的网页了，比如这里创建个新的 `index.html`，随便输入点内容就可以访问试试看。

![1725892251595](/image/Hexo-Github-Page/1725892251595.png)

![1725892346432](/image/Hexo-Github-Page/1725892346432.png)

### 配置Git用户名和邮箱

一般来说都配置好了，所以下面只放命令（在Git Bash中输入）

```stylus
git config --global user.name "your account name"
git config --global user.email "your email"
```

### 把本地Hexo博客发布到Github Pages上

首先安装插件 `hexo-deployer-git`。也可以用cnpm下载。

```ada
npm install hexo-deployer-git --save
```

![1725892873409](/image/Hexo-Github-Page/1725892873409.png)

接下来要把本地目录和Github关联，也就是进行SSH连接，但SSH连接早在很久之前就完成过了，因此不再赘述。

我们直接打开hexo配置文件配置相关内容。这里我修改了一下仓库名，没有什么影响。

![1725893274923](/image/Hexo-Github-Page/1725893274923.png)

然后我们拉到最底下，进行deploy设置。

```avrasm
type: git
repo: git@github.com:Github用户名/仓库名.git
branch: main
```

这个repo可以直接复制这里的链接：

![1725893494605](/image/Hexo-Github-Page/1725893494605.png)

现在已经配置好了，输入下面的命令后访问网页看看是否成功。

```css
hexo g
hexo d
```

![1725895041837](/image/Hexo-Github-Page/1725895041837.png)

搭建成功，当然也可以从另外一个分支构建然后在主页加一个 `README.md`。
