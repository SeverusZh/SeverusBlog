---
title: "LeetCode 82&83: 删除排序链表中的重复元素"
date: 2024-09-11 18:54:53
updated: 2025-03-03
tags:
  - LeetCode
---

字数：598，阅读时间：3分钟

### 题目83

给定一个已排序的链表的头 `head` ， *删除所有重复的元素，使每个元素只出现一次* 。返回 *已排序的链表* 。

**示例 1：**

![img1](https://assets.leetcode.com/uploads/2021/01/04/list1.jpg)

```java
输入：head = [1,1,2]
输出：[1,2]
```

**示例 2：**

![img2](https://assets.leetcode.com/uploads/2021/01/04/list2.jpg)

```java
输入：head = [1,1,2,3,3]
输出：[1,2,3]
```

**提示：**

- 链表中节点数目在范围 `[0, 300]` 内
- `-100 <= Node.val <= 100`
- 题目数据保证链表已经按升序 **排列**

#### 思路

由于链表已经排好序了，检查下一个节点的数值并和当前节点比较应该就能解决这个问题吧。

#### 题解

就是基础的检查元素并删除节点的操作。

```java
class Solution {
    public ListNode deleteDuplicates(ListNode head) {
        ListNode temp = head;
        if(head == null)
        {
            return head;
        }
        while (temp.next != null) {
            if (temp.next.val == temp.val) {
                if (temp.next.next == null) {
                    temp.next = null;
                } else {
                    temp.next = temp.next.next;
                }
            } else {
                temp = temp.next;
            }
        }
        return head;
    }
}
```

### 题目82

为什么要先做83呢，因为83难度是简单但82是中等。

给定一个已排序的链表的头 `head` ， *删除原始链表中所有重复数字的节点，只留下不同的数字* 。返回 *已排序的链表* 。

**示例 1：**

![img3](https://assets.leetcode.com/uploads/2021/01/04/linkedlist1.jpg)

```java
输入：head = [1,2,3,3,4,4,5]
输出：[1,2,5]
```

**示例 2：**

![img4](https://assets.leetcode.com/uploads/2021/01/04/linkedlist2.jpg)

```java
输入：head = [1,1,1,2,3]
输出：[2,3]
```

**提示：**

- 链表中节点数目在范围 `[0, 300]` 内
- `-100 <= Node.val <= 100`
- 题目数据保证链表已经按升序 **排列**

#### 尝试

思路什么的先放一边，我们把刚刚写的源码放进去再执行一遍，看看这题有什么不同。

![1726054362641](/image/LeetCode-83-%E5%88%A0%E9%99%A4%E6%8E%92%E5%BA%8F%E9%93%BE%E8%A1%A8%E4%B8%AD%E7%9A%84%E9%87%8D%E5%A4%8D%E5%85%83%E7%B4%A0/1726054362641.png)

原来这道题要把重复的节点全部删掉，这样就比刚刚复杂了。

#### 思路

就在此时我浮现了一个思路，既然是单向升序链表，也就是说，只要我设置把重复的节点`val`设成`head`的`val-1`或者`-101`，然后等全部执行完再遍历一遍删除，应该就能实现这个功能了。

理论存在，实践开始！

#### 题解

首先引入一个标志 `flag`，这个标志负责记录当前节点有没有重复的下一节点，如果有则置1，等待该节点完成一般的删除重复节点操作后，在其即将进入下一个不重复的节点时修改当前节点的值为-101，然后再复位。当执行完一般的删除重复节点操作后，再从头指针开始遍历，遇到节点值为-101的情况就删除当前节点。需要注意的是，如果头节点的值为-101，则要执行特殊的删除循环结构，因为头节点没有前驱。同时注意一下null的情况，就可以完成这个题目了。

```java
class Solution {
    public ListNode deleteDuplicates(ListNode head) {
        ListNode temp = head;
        int flag = 0;
        if (head == null) {
            return head;
        }
        while (temp.next != null) {
            if (temp.next.val == temp.val) {
                if (temp.next.next == null) {
                    temp.next = null;
                } else {
                    temp.next = temp.next.next;
                }
                flag = 1;
            } else {
                if (flag == 1) {
                    temp.val = -101;
                    flag = 0;
                }
                temp = temp.next;
            }
        }
        if (flag == 1) {
            temp.val = -101;
            flag = 0;
        }
        while ( 1 == 1) {
            if (head.val == -101) {
                if (head.next == null) {
                    head = null;
                    return head;
                } else {
                    head =head.next;
                }
            } else {
                break;
            }
        }
        temp = head;
        while (temp.next != null) {
            if (temp.next.val == -101) {
                if (temp.next.next == null) {
                    temp.next = null;
                } else {
                    temp.next = temp.next.next;
                }
            } else {
                temp = temp.next;
            }
        }
        return head;
    }
}
```
