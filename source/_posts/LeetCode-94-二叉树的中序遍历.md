---
title: "LeetCode 94: 二叉树的中序遍历"
date: 2024-09-11 21:00:24
updated: 2025-03-03
tags:
  - LeetCode
---

字数：261，阅读时间：2分钟

### 题目

给定一个二叉树的根节点 `root` ，返回 *它的 **中序** 遍历* 。

**示例 1：**

![](https://assets.leetcode.com/uploads/2020/09/15/inorder_1.jpg)

```java
输入：root = [1,null,2,3]
输出：[1,3,2]
```

**示例 2：**

```java
输入：root = []
输出：[]
```

**示例 3：**

```java
输入：root = [1]
输出：[1]
```

**提示：**

- 树中节点数目在范围 `[0, 100]` 内
- `-100 <= Node.val <= 100`

### 中序遍历的概念

就当作是数据结构的复习了，稍微回顾一下中序遍历顺序的结构。简单来说三种遍历顺序都用递归算法来实现的话，就是访问根节点的时机。

中序遍历首先遍历左子树，然后访问根结点，最后遍历右子树。若二叉树为空则结束返回，否则：

（1）中序遍历左子树

（2）访问根结点

（3）中序遍历右子树

### 思路

简单来说就是递归访问，按中序遍历的顺序先左再根最后右。如果要用迭代算法就引入一个栈的数据结构。

这里注意一下List的方法，java里 `list`没有 `append`和 `insert`方法，使用 `add`方法和`addAll`方法即可。

### 题解

```java
class Solution {
    public List<Integer> inorderTraversal(TreeNode root) {
        List<Integer> list = new ArrayList<>();
        if (root != null) {
            if (root.left != null)
                list.addAll(inorderTraversal(root.left));
            list.add(root.val);
            if (root.right != null)
                list.addAll(inorderTraversal(root.right));
        }
        return list;
    }
}
```
