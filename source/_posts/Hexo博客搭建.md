---
title: Hexo博客搭建
date: 2024-09-08 22:21:14
updated: 2025-03-03
tags:
  - 博客搭建
---

今天心血来潮想搭建一个个人博客，将自己在技术学习过程中的经历与遇到的小问题都记录在博客上，博客先部署在主机上，之后会部署到服务器中。既然搭建了博客，第一篇文章不妨就记录一下这个Hexo博客的搭建过程吧。

## 环境配置

Hexo的环境其实很简单，安装了 `Git`和 `Node.js`基础环境就安装好了。在Windows环境下都是去官网下载安装即可。

```plaintext
https://git-scm.com/download/win
https://nodejs.org/zh-cn
```

输入 `git -v`、`node -v`和 `npm -v`即可检查是否安装成功。

![1725805936037](/image/Hexo%E5%8D%9A%E5%AE%A2%E6%90%AD%E5%BB%BA/1725805936037.png)

## 安装Hexo

这一步更简单，只要在命令行中输入下面的命令即可安装：

```powershell
npm install -g hexo-cli
```

## 建站

输入下面命令初始化Hexo：

```powershell
hexo init
```

输入下面命令启动Hexo：

```powershell
hexo server #可以简写为hexo s
```

![1725806364107](/image/Hexo%E5%8D%9A%E5%AE%A2%E6%90%AD%E5%BB%BA/1725806364107.png)

这样就可以从我们本地的4000端口上访问了，如果你有公网IP，也可以从公网IP的端口访问，像我一样没有的话可以租用云服务器或者是用内网穿透服务来从公网访问。

![1725806686246](/image/Hexo%E5%8D%9A%E5%AE%A2%E6%90%AD%E5%BB%BA/1725806686246.png)

当然默认的主题并不是这个样子，因此下面顺便介绍一下怎么切换主题。

## 更换主题

打开 `https://hexo.io/themes/`，这是Hexo官方的主题收录站，我就是从这里找到的目前正在使用的主题Cards。当然直接在Github上搜索Hexo也能搜到不少定制的主题。

![1725807025809](/image/Hexo%E5%8D%9A%E5%AE%A2%E6%90%AD%E5%BB%BA/1725807025809.png)

![1725807061685](/image/Hexo%E5%8D%9A%E5%AE%A2%E6%90%AD%E5%BB%BA/1725807061685.png)

我个人更喜欢极简的风格，所以选择Cards作为示例。

简单的来说，你只需要在博客的根目录输入下面这条Git命令就可以安装主题了：

```powershell
git clone https://github.com/ChrAlpha/hexo-theme-cards.git themes/cards
```

当然你需要把_config.yml中的主题名更换一下。

![1725807399147](/image/Hexo%E5%8D%9A%E5%AE%A2%E6%90%AD%E5%BB%BA/1725807399147.png)

博客的标题和一些其他配置都可以到主题的配置文件中去修改：

![1725808421706](/image/Hexo%E5%8D%9A%E5%AE%A2%E6%90%AD%E5%BB%BA/1725808421706.png)

接下来重新启动Hexo即可。

如果恰好遇上了无法 `git clone`的问题，可以直接下载压缩包并解压到themes文件夹中，记得重命名文件夹名称。
