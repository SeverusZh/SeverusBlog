---
title: AVX2加法
date: 2025-02-27 19:03:48
updated: 2025-03-03
tags:
  - AVX2
---

字数：126，阅读时间：1分钟

# AVX2加法

使用AVX2指令集的指令优化一个最简单的程序

## 实践过程

- 练习记录

  - 日期：2025/1/20
  - 练习内容：编写一个简单的实现数组相加的程序并使用AVX2优化。
  - 遇到的问题：编译无法通过。
  - 解决方案：添加 -mavx2 编译选项
  - 代码：

  ```c
  //
  // Created by 张浩 on 2025/1/20.
  //
  #include <stdio.h>
  #include <immintrin.h>

  int main() {
      int a[8] = {1, 2, 3, 4, 5, 6, 7, 8};
      int b[8] = {8, 7, 6, 5, 4, 3, 2, 1};
      int result[8];

      // 加载数组a和b的数据到AVX2寄存器中
      __m256i va = _mm256_loadu_si256((__m256i*)a);
      __m256i vb = _mm256_loadu_si256((__m256i*)b);

      // 使用AVX2指令集进行向量相加
      __m256i vc = _mm256_add_epi32(va, vb);

      // 将结果存储回内存
      _mm256_storeu_si256((__m256i*)result, vc);

      // 打印结果
      for (int i = 0; i < 8; ++i) {
          printf("%d ", result[i]);
      }
      printf("\n");

      return 0;
  }
  ```
