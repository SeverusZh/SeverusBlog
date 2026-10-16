---
title: "LeetCode 67: 二进制求和"
date: 2024-09-10 19:06:19
updated: 2025-03-03
tags:
  - LeetCode
---

最近在学Java，所以重新刷一点LeetCode的简单题，尝试用Java来实现。

## 题目

给你两个二进制字符串 `a` 和 `b` ，以二进制字符串的形式返回它们的和。

**示例 1：**

```java
输入:a = "11", b = "1"
输出："100"
```

**示例 2：**

```java
输入：a = "1010", b = "1011"
输出："10101"
```

**提示：**

- `1 <= a.length, b.length <= 10<sup>4</sup>`
- `a` 和 `b` 仅由字符 `'0'` 或 `'1'` 组成
- 字符串如果不是 `"0"` ，就不含前导零

## 初步思路

很显然，初步的思路有把字符串转换成整型进行加法后再转换成字符串和直接在字符串内从后向前遍历并设置进位器进行异或运算两种。从原理上后者似乎更接近硬件实现，但我们两种都可以尝试一下。

## 思路一

源码

```java
class Solution {
    public String addBinary(String a, String b) {
        int a_num = 0;
        int b_num = 0;
        int m = 1;
        for (int i = a.length() - 1; i >= 0; i--) {
            a_num += ((a.charAt(i) - '0') * m);
            m *= 2;
        }
        m = 1;
        for (int i = b.length() - 1; i >= 0; i--) {
            b_num += ((b.charAt(i) - '0') * m);
            m *= 2;
        }
        int sum = a_num + b_num;
        if(sum != 0)
        {
        StringBuilder str = new StringBuilder("");
        sum2str(str, sum);
        return str.toString();
        }
        else return "0";
    }

    public StringBuilder sum2str(StringBuilder str, int sum) {
        if (sum != 0) {
            sum2str(str, sum / 2);
            if (sum % 2 == 0) {
                str.append('0');
            } else
                str.append('1');
        }
        return str;
    }
}
```

这份源码很好懂，总之就是先把字符串变成整数加算后再变回去，变回去的时候用的是递归运算。这份代码还有很大的优化空间，但是没什么必要，因为没通过测试用例。

![1725971001863](/image/LeetCode-67-%E4%BA%8C%E8%BF%9B%E5%88%B6%E6%B1%82%E5%92%8C/1725971001863.png)

原因很简单，我发现我看错了题目，是长度小于10000而不是数值小于10000……

话不多说，直接进思路二。

## 思路二

这个思路就是要求我们从后往前遍历字符串进行累加，倒也不算困难。

主要方法是建立一个含有进位存储器的异或方法，有点像寄存器，然后就可以用循环结构计算了。

在编写的过程中了解到 `StringBuilder`类中还有一个 `Reverse()`方法，可以直接逆序，很方便。

源码：

```java
class Solution {
    public String addBinary(String a, String b) {
        StringBuilder str = new StringBuilder("");
        String large = a.length() >= b.length() ? a : b;
        String small = a.length() >= b.length() ? b : a;
        int i = large.length() - 1;
        int j = small.length() - 1;
        char count ='0';
        while(i>=0)
        {
            if(j>=0)
            {
                char[] temp = {'0','0'};
                temp = xorString(large.charAt(i),small.charAt(j));
                temp = xorString(temp[0],count);
                count = temp[1];
                str.append(temp[0]);
            }
            else
{
                char[] temp = {'0','0'};
                temp = xorString(large.charAt(i),count);
                count = temp[1];
                str.append(temp[0]);
            }
            i--;
            j--;
        }
        if(count == '1')
            str.append('1');
        return str.reverse().toString();
    }
    public char[] xorString(char first, char second) {
        char[] symbol ={'0','0'};
        if (first == second)
        {
            symbol[0] = '0';
            symbol[1] = first;
        }
        else
{
            symbol[0] = '1';
            symbol[1] = '0';
        }
        return symbol;
    }
}
```

然而这份代码也是有问题的，他进位时会发生错误，无奈只能创建一个主类来进行调试了。

```java
public class Main {
    public static void main(String[] args) {
     Solution solution = new Solution();
     String a = "1";
        String b = "1";
     String result = solution.addBinary(a, b);
     System.out.println("Binary sum of " + a + " and " + b + " is: " + result);
    }
}
```

测试时发现，第一步计算 `symbol`时没有出现问题：

![1725977578673](/image/LeetCode-67-%E4%BA%8C%E8%BF%9B%E5%88%B6%E6%B1%82%E5%92%8C/1725977578673.png)

原因出在这里，第二次计算symbol时，又把进位值重置成0了，这就导致进位不生效。

![1725977717193](/image/LeetCode-67-%E4%BA%8C%E8%BF%9B%E5%88%B6%E6%B1%82%E5%92%8C/1725977717193.png)

由于三个个位二进制数加和永远不可能大于四，所以这里我们可以作如下修改：

```java
char[] temp = {'0','0'};
temp = xorString(large.charAt(i),small.charAt(j));
temp[0] = xorString(temp[0],count)[0];
count = temp[1];
str.append(temp[0]);
```

本地测试一下，能进位了：

![1725977972721](/image/LeetCode-67-%E4%BA%8C%E8%BF%9B%E5%88%B6%E6%B1%82%E5%92%8C/1725977972721.png)

直接在LeetCode上提交，然后又错了：

![1725978307432](/image/LeetCode-67-%E4%BA%8C%E8%BF%9B%E5%88%B6%E6%B1%82%E5%92%8C/1725978307432.png)

又调试了一遍，还是这个进位的问题，忽视了进位与原数再产生进位的情况。

![1725978389306](/image/LeetCode-67-%E4%BA%8C%E8%BF%9B%E5%88%B6%E6%B1%82%E5%92%8C/1725978389306.png)

修改如下：

```java
char[] temp = {'0','0'};
temp = xorString(large.charAt(i),small.charAt(j));
char[] tmp_count = {temp[1],'0'};
temp = xorString(temp[0],count);
tmp_count[1] = temp[1];
count = xorString(tmp_count[0],tmp_count[1])[0];
str.append(temp[0]);
```

因为实际上三个数相加最多产生一次进位，为了不忽视两次运算的进位情况，将两次进位值异或即可。

再次提交就通过了。

![1725979173341](/image/LeetCode-67-%E4%BA%8C%E8%BF%9B%E5%88%B6%E6%B1%82%E5%92%8C/1725979173341.png)

时间复杂度和空间复杂度都是O(n)，显然不是最佳解法，看了一下题解，较好的方案把每个字符化成整型然后加法再变回字符和进位。相当于是我的思路一与思路二的结合体，我这种可能更接近于硬件方案吧。最后稍微优化了一些结构，源码及注释如下：

```java
public class Main {
    public static void main(String[] args) {
        // 创建 Solution 类的实例
        Solution solution = new Solution();

        // 测试用例，两个二进制字符串
        String a = "110010";
        String b = "10111";

        // 调用 addBinary 方法计算二进制字符串的和
        String result = solution.addBinary(a, b);

        // 输出结果
        System.out.println("Binary sum of " + a + " and " + b + " is: " + result);
    }
}

class Solution {
    // 该方法用于计算两个二进制字符串的和
    public String addBinary(String a, String b) {
        // 创建一个用于存储结果的 StringBuilder
        StringBuilder str = new StringBuilder("");
  
        // 确定较长的字符串 large 和较短的字符串 small
        String large = a.length() >= b.length() ? a : b;
        String small = a.length() >= b.length() ? b : a;
  
        // 初始化指针 i 和 j 分别指向 large 和 small 的最后一个字符
        int i = large.length() - 1;
        int j = small.length() - 1;
  
        // count 用于存储进位，初始值为 '0'
        char count = '0';
  
        // 遍历 large 字符串从右到左进行二进制加法
        while (i >= 0) {
            if (j >= 0) { // 当 small 字符串还有未处理的字符时
                // 使用 xorString 方法进行字符相加，返回两个值：当前位和进位
                char[] temp = xorString(large.charAt(i), small.charAt(j));
        
                // 如果产生进位，将当前位与之前的进位相加
                if (temp[1] == '1') {
                    temp[0] = count;
                } else {
                    temp = xorString(temp[0], count);
                }
        
                // 更新进位值
                count = temp[1];
        
                // 将当前位添加到结果中
                str.append(temp[0]);
            } else { // 当 small 字符串已处理完时，仅处理 large 字符串
                char[] temp = xorString(large.charAt(i), count);
        
                // 更新进位值
                count = temp[1];
        
                // 将当前位添加到结果中
                str.append(temp[0]);
            }
            // 移动指针
            i--;
            j--;
        }
  
        // 如果最后还有进位，添加到结果中
        if (count == '1') {
            str.append('1');
        }
  
        // 由于我们是从右到左构造的字符串，需要将其反转并返回
        return str.reverse().toString();
    }

    // 该方法用于计算两个字符的二进制加法，返回的数组中，第一个元素为结果，第二个元素为进位
    public char[] xorString(char first, char second) {
        // 初始化一个数组 symbol 存储加法结果和进位
        char[] symbol = {'0', '0'};
  
        // 如果两个字符相同，则结果为 '0'，进位为该字符的值
        if (first == second) {
            symbol[0] = '0';
            symbol[1] = first;
        } else {
            // 如果两个字符不同，则结果为 '1'，进位为 '0'
            symbol[0] = '1';
            symbol[1] = '0';
        }
  
        return symbol;
    }
}

```
