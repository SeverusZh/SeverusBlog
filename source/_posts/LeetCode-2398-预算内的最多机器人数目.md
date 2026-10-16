---
title: "LeetCode 2398: 预算内的最多机器人数目"
date: 2024-09-13 02:15:19
updated: 2025-03-03
tags:
  - LeetCode
---

字数：1837，阅读时间：10分钟

虽然刚学Java不久，但也不能天天做简单题，今天正好每日一题是一道困难题，就来做做看。

### 题目

你有 `n` 个机器人，给你两个下标从 **0** 开始的整数数组 `chargeTimes` 和 `runningCosts` ，两者长度都为 `n` 。第 `i` 个机器人充电时间为 `chargeTimes[i]` 单位时间，花费 `runningCosts[i]` 单位时间运行。再给你一个整数 `budget` 。

运行 `k` 个机器人 **总开销** 是 `max(chargeTimes) + k * sum(runningCosts)` ，其中 `max(chargeTimes)` 是这 `k` 个机器人中最大充电时间，`sum(runningCosts)` 是这 `k` 个机器人的运行时间之和。

请你返回在 **不超过** `budget` 的前提下，你 **最多** 可以 **连续** 运行的机器人数目为多少。

**示例 1：**

```java
输入：chargeTimes = [3,6,1,3,4], runningCosts = [2,1,3,4,5], budget = 25
输出：3
```

解释：
可以在 budget 以内运行所有单个机器人或者连续运行 2 个机器人。
选择前 3 个机器人，可以得到答案最大值 3 。总开销是 max(3,6,1) + 3 *sum(2,1,3) = 6 + 3* 6 = 24 ，小于 25 。
可以看出无法在 budget 以内连续运行超过 3 个机器人，所以我们返回 3 。

**示例 2：**

```java
输入：chargeTimes = [11,12,19], runningCosts = [10,8,7], budget = 19
输出：0
解释：即使运行任何一个单个机器人，还是会超出 budget，所以我们返回 0 。
```

**提示：**

- `chargeTimes.length == runningCosts.length == n`
- `1 <= n <= 5 * 10<sup>4</sup>`
- `1 <= chargeTimes[i], runningCosts[i] <= 10<sup>5</sup>`
- `1 <= budget <= 10<sup>15</sup>`

### 滑动窗口

其实这个题目中比较关键的是**连续**这两个字，因为其实充电时间和运行时间什么的都只是需要计算的数据，而连续这两个字就代表了我们不能直接排序，而是要使用**滑动窗口**的方法。滑动窗口在思想上的表现就是一种子视图，通过动态控制这个视图的大小来截取数据，单次遍历即可实现。窗口左侧只能删除数据而右侧只能添加数据。窗口永远不会向左移动。在这个题目中我们删除或添加数据的方法就是计算总预算的值。运行时间的和是比较好计算的，但是最大充电时间这个值每次都要重新计算，会消耗大量计算时间，当然也有优化的办法，那就是使用双端队列来维护这个充电时间，用空间换时间，不过这个可以之后再讲，我们先拿出一份朴素的、超时的代码。

```java
class Solution {
    public int maximumRobots(int[] chargeTimes, int[] runningCosts, long budget) {
        int length = chargeTimes.length;
        int max_count = 0;
        boolean flag = true; // 标志是否低于预算
        List<Integer> list = new ArrayList<>();

        for (int i = 0; i < length;) {
            if (flag || list.isEmpty()) {
                list.add(i);
            }

            if (JudgeOverBudget(list, chargeTimes, runningCosts, budget)) {
                list.remove(0);
                flag = false;
            } else {
                flag = true;
            }

            if (flag || list.isEmpty()) {
                i++;
            }

            max_count = Math.max(max_count, list.size());
        }

        return max_count;
    }

    public boolean JudgeOverBudget(List<Integer> list, int[] chargeTimes, int[] runningCosts, long budget) {
        int length = list.size();
        int sum = 0;
        int max = 0;

        for (int i = 0; i < length; i++) {
            max = Math.max(max, chargeTimes[list.get(i)]);
            sum += runningCosts[list.get(i)];
        }

        return (max + (long) length * sum) > budget; // 如果超过预算，则返回true
    }
}
```

这份代码有多朴素呢，首先它能通过数据量比较小的测试用例，说明它的思想是对的，但是这里的滑动窗口没有用双指针来实现（偷懒ing🤗），然后每次都重算一遍最大充电时间和总运行时间，哪怕根本不用双端队列，也可以把总运行时间的运算抽离成每次循环只计算一次，但是我没有。所以总的来说，这份代码写的比较粗犷，自然而然也就超时了，不过相应的，也比较好读懂。放这份代码是为了介绍接下来双端队列的内容，方便看懂。

### 双端队列

由于双端队列完全在这个滑动窗口中工作，所以介绍一下使用双指针实现的滑动窗口。

#### 滑动窗口的双指针实现

滑动窗口是一种通过一对指针（通常称为 `left`和 `right`）来动态调整子数组范围的技术。在遍历数组的过程中，右边界 `right`每次右移（扩大窗口），当某些条件满足（如总费用超过预算）时，左边界 `left`右移（缩小窗口）。滑动窗口能够在O(n)时间内遍历整个数组，并动态调整窗口的范围，从而避免嵌套循环。

在这个问题中，窗口表示当前可以操作的机器的范围：

- `right` 指针表示当前处理的机器。
- `left` 指针表示窗口的左边界。

每次 `right`指针右移时，我们会计算当前窗口内的总费用，若费用超过预算，就移动 `left`指针缩小窗口。通过这种方式，我们可以在O(n)时间内找到最大数量的机器。

#### 双端队列的介绍

双端队列是一种可以在两端高效插入和删除元素的数据结构。这里我们使用它来维护滑动窗口内的最大值，这样我们可以在O(1)时间内获取窗口中的最大充电时间。

这个问题中，我们希望能够动态地得到当前窗口中机器的最大充电时间。如果使用上面的代码那样计算最大值，时间复杂度会很高。所以我们使用双端队列来保存数组的索引，并维护一个“递减队列”：

- **队列的左端** ：存储当前窗口中最大充电时间的索引。
- **队列的右端** ：存储接下来可能成为最大值的元素的索引。

简单来说，队列的最左端的索引值所在的位置一定在当前窗口中，如果left大于该索引值，队列就会删掉这个元素，从而使得下一个元素成为最大值。而每次right移动时都会加入一个新的索引到这个队列中，如果这个索引值对应的最大充电时间大于其左边的一些值，那么直接把这些值全部从队列中删掉。因为这些值都没有必要判断了，在一个只会右移的窗口中它们不再具有意义。

#### 如何使用双端队列

1. 当 `right`指针右移时，比较 `chargeTimes[right]`和双端队列的末尾。如果 `chargeTimes[right]`大于或等于队列末尾的元素，那么队列末尾元素就没用了，因为它永远不会成为窗口中的最大值。因此，移除队列末尾的元素，直到队列末尾的元素比 `chargeTimes[right]`大。
2. 把 `right`对应的索引加入队列末尾。
3. 如果滑动窗口的左边界（即 `left`）超出了队列中存储的最大值的范围（即 `deque.peekFirst()`），则移除队列的左端（也就是最大值）。

通过这个方法，队列的左端始终保存当前窗口中的最大值的索引，因此可以快速获取最大值。

#### 每次 `right`指针右移时的操作

实际上根据上面的原理可以写出来，每次 `right`指针的右移会有如下操作：

- **更新双端队列** ：将 `chargeTimes[right]`加入队列，确保队列中始终保持当前窗口的最大充电时间在队首。
- **更新窗口总运行费用** ：累加 `runningCosts[right]`到总费用中。
- **判断窗口总费用是否超过预算** ：如果超出预算，通过移动 `left`指针来缩小窗口，并相应地更新总运行费用和双端队列。
- **计算最大窗口大小** ：更新最大能操作的机器数量。

### 源码

综上能得到下面这份源码：

```java
class Solution {
    public int maximumRobots(int[] chargeTimes, int[] runningCosts, long budget) {
        int length = chargeTimes.length;
        Deque<Integer> deque = new ArrayDeque<>(); // 双端队列，用于维护最大值
        long runningCostSum = 0; // 当前窗口内的总运行费用
        int maxRobots = 0;
        int left = 0;
        for (int right = 0; right < length; right++) {
            // 维护最大充电时间的双端队列
            while (!deque.isEmpty() && chargeTimes[deque.peekLast()] <= chargeTimes[right]) {
                deque.pollLast();
            }
            deque.addLast(right);
            // 累加当前窗口的运行费用
            runningCostSum += runningCosts[right];
            // 判断当前窗口是否超过预算
            while (!deque.isEmpty() && chargeTimes[deque.peekFirst()] + (right - left + 1) * runningCostSum > budget) {
                // 如果超过预算，缩小窗口（移动左边界）
                if (deque.peekFirst() == left) {
                    deque.pollFirst();
                }
                runningCostSum -= runningCosts[left];
                left++;
            }
            // 更新最大机器人数量
            maxRobots = Math.max(maxRobots, right - left + 1);
        }
        return maxRobots;
    }
}
```

![1726167174602](/image/LeetCode-2398-%E9%A2%84%E7%AE%97%E5%86%85%E7%9A%84%E6%9C%80%E5%A4%9A%E6%9C%BA%E5%99%A8%E4%BA%BA%E6%95%B0%E7%9B%AE/1726167174602.png)

虽然没达到100%，仍有进步空间，但感觉也不错了。
