---
title: AVX2移位
date: 2025-02-27 19:06:14
updated: 2025-03-03
tags:
  - AVX2
---

## 实践过程

- 练习记录
  - 日期：2025/1/22
  - 练习内容：编写一个使用AVX2指令集优化的移位算法
  - 遇到的问题：无
  - 解决方案：无
  - 代码：

```c
//
// Created by 张浩 on 2025/1/22.
//
#include <stdio.h>
#include <immintrin.h>

int main() {
    // 初始化一个 __m256i 类型的向量，存储 8 个 32 位整数
    __m256i vec = _mm256_set_epi32(0x00080000, 0x00400000, 0x00000200, 0x10000000, 0x00000008, 0x00040000, 0x00002000, 0x01000000);
    // 初始化一个 __m256i 类型的向量作为移位量，存储 8 个 32 位整数，每个元素表示不同的移位量
    __m256i shift_amount = _mm256_set_epi32(3, 2, 1, 0, 3, 2, 1, 0);

    // 逻辑左移操作
    __m256i slli_vec = _mm256_slli_epi32(vec, 2);
    // 逻辑右移操作
    __m256i srli_vec = _mm256_srli_epi32(vec, 2);
    // 算术右移操作
    __m256i srai_vec = _mm256_srai_epi32(vec, 2);
    // 可变左移操作
    __m256i sllv_vec = _mm256_sllv_epi32(vec, shift_amount);
    // 可变右移操作
    __m256i srlv_vec = _mm256_srlv_epi32(vec, shift_amount);
    // 可变算术右移操作
    __m256i srav_vec = _mm256_srav_epi32(vec, shift_amount);

    // 存储结果的数组
    int slli_result[8], srli_result[8], srai_result[8], sllv_result[8], srlv_result[8], srav_result[8];

    // 将结果存储到相应的数组中
    _mm256_storeu_si256((__m256i*)slli_result, slli_vec);
    _mm256_storeu_si256((__m256i*)srli_result, srli_vec);
    _mm256_storeu_si256((__m256i*)srai_result, srai_vec);
    _mm256_storeu_si256((__m256i*)sllv_result, sllv_vec);
    _mm256_storeu_si256((__m256i*)srlv_result, srlv_vec);
    _mm256_storeu_si256((__m256i*)srav_result, srav_vec);

    // 打印逻辑左移结果
    printf("Logical Shift Left (by 2): ");
    for (int i = 0; i < 8; i++) {
        printf("%x ", slli_result[i]);
    }
    printf("\n");

    // 打印逻辑右移结果
    printf("Logical Shift Right (by 2): ");
    for (int i = 0; i < 8; i++) {
        printf("%x ", srli_result[i]);
    }
    printf("\n");

    // 打印算术右移结果
    printf("Arithmetic Shift Right (by 2): ");
    for (int i = 0; i < 8; i++) {
        printf("%x ", srai_result[i]);
    }
    printf("\n");

    // 打印可变左移结果
    printf("Variable Shift Left: ");
    for (int i = 0; i < 8; i++) {
        printf("%x ", sllv_result[i]);
    }
    printf("\n");

    // 打印可变右移结果
    printf("Variable Shift Right: ");
    for (int i = 0; i < 8; i++) {
        printf("%x ", srlv_result[i]);
    }
    printf("\n");

    // 打印可变算术右移结果
    printf("Variable Arithmetic Shift Right: ");
    for (int i = 0; i < 8; i++) {
        printf("%x ", srav_result[i]);
    }
    printf("\n");

    return 0;
}
```
