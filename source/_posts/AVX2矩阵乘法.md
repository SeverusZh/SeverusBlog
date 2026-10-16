---
title: AVX2矩阵乘法
date: 2025-02-27 19:05:25
updated: 2025-03-03
tags:
  - AVX2
---

字数：291，阅读时间：2分钟

# AVX2矩阵乘法

## 实践过程

- 练习记录
  - 日期：2025/1/21
  - 练习内容：编写一个使用AVX2指令集优化的矩阵乘法算法
  - 遇到的问题：当矩阵列数不为步长的倍数时，可能发生计算错误或溢出错误
  - 解决方案：将矩阵列数补全为步长的倍数
  - 代码：

```c
//
// Created by 张浩 on 2025/1/21.
//
#include <stdio.h>
#include <immintrin.h>
#include <stdlib.h>
#include <stdalign.h>

// 矩阵乘法函数，使用AVX2指令集
void matrix_multiply_avx2(int *A, int *B, int *C, int rows_A, int cols_A, int cols_B) {
    for (int i = 0; i < rows_A; ++i) {
        for (int j = 0; j < cols_B; j += 8) {
            __m256i c_vec = _mm256_setzero_si256();
            for (int k = 0; k < cols_A; ++k) {
                __m256i a_vec = _mm256_set1_epi32(A[i * cols_A + k]);//i*cols_A+k i行k列的元素
                __m256i b_vec = _mm256_loadu_si256((__m256i*)(B + k * cols_B + j)); //k*cols_B+j 从k行j列开始的8个元素
                c_vec = _mm256_add_epi32(c_vec, _mm256_mullo_epi32(a_vec, b_vec));
            }
            _mm256_storeu_si256((__m256i*)(C + i * cols_B + j), c_vec);
        }
    }
}
//经过分析，认为上面的代码可能存在问题，原因是：如果B矩阵的列数不是8的倍数，则有可能计算到下一行的数据，引发逻辑或溢出错误。
//因此，需要对B矩阵的列数进行判断，如果不是8的倍数，则需要对B矩阵进行补齐，使其列数为8的倍数。

// 补齐矩阵函数
void pad_matrix(int **matrix, int rows, int *cols) {
    int original_cols = *cols;
    int new_cols = (*cols + 7) & ~7; // 计算新的列数，使其为8的倍数
    if (new_cols != original_cols) {
        for (int i = 0; i < rows; ++i) {
            for (int j = original_cols; j < new_cols; ++j) {
                (*matrix)[i * new_cols + j] = 0; // 填充零
            }
        }
        *cols = new_cols; // 更新列数
    }
}
// 打印矩阵函数
void print_matrix(int *matrix, int rows, int cols) {
    for (int i = 0; i < rows; ++i) {
        for (int j = 0; j < cols; ++j) {
            printf("%d ", matrix[i * cols + j]);
        }
        printf("\n");
    }
}

int main() {
    const int rows_A = 8;
    const int cols_A = 8;
    const int cols_B = 8;

    // 为矩阵A、B、C分配内存，并确保32字节对齐
    alignas(32) int *A = (int*)_aligned_malloc(32, rows_A * cols_A * sizeof(int));
    alignas(32) int *B = (int*)_aligned_malloc(32, cols_A * cols_B * sizeof(int));
    alignas(32) int *C = (int*)_aligned_malloc(32, rows_A * cols_B * sizeof(int));

    // 初始化矩阵A和B
    int values_A[] = {
        1, 2, 3, 4, 5, 6, 7, 8,
        9, 10, 11, 12, 13, 14, 15, 16,
        17, 18, 19, 20, 21, 22, 23, 24,
        25, 26, 27, 28, 29, 30, 31, 32,
        33, 34, 35, 36, 37, 38, 39, 40,
        41, 42, 43, 44, 45, 46, 47, 48,
        49, 50, 51, 52, 53, 54, 55, 56,
        57, 58, 59, 60, 61, 62, 63, 64
    };
    int values_B[] = {
        1, 2, 3, 4, 5, 6, 7, 8,
        9, 10, 11, 12, 13, 14, 15, 16,
        17, 18, 19, 20, 21, 22, 23, 24,
        25, 26, 27, 28, 29, 30, 31, 32,
        33, 34, 35, 36, 37, 38, 39, 40,
        41, 42, 43, 44, 45, 46, 47, 48,
        49, 50, 51, 52, 53, 54, 55, 56,
        57, 58, 59, 60, 61, 62, 63, 64
    };
    for (int i = 0; i < rows_A * cols_A; ++i) {
        A[i] = values_A[i];
    }
    for (int i = 0; i < cols_A * cols_B; ++i) {
        B[i] = values_B[i];
    }

    pad_matrix(&B, cols_A, &cols_B); // 补齐B矩阵
    // 调用矩阵乘法函数
    matrix_multiply_avx2(A, B, C, rows_A, cols_A, cols_B);

    // 打印结果矩阵C
    printf("Result Matrix C:\n");
    print_matrix(C, rows_A, cols_B);

    // 释放内存
    free(A);
    free(B);
    free(C);

    return 0;
}
```
