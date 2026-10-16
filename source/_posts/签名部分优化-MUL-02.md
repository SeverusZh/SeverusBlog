---
title: 签名部分优化-MUL-02
date: 2025-02-27 19:07:55
updated: 2025-03-03
tags:
  - AVX2
  - Hawk
---

昨天完成了对 `bp_mul_32`的优化工作，今天的任务则是优化 `bp_muladd_64`

## 源代码分析

```c
static void
bp_muladd_64(uint8_t *restrict d, const uint8_t *restrict a,
 const uint8_t *restrict b, uint8_t *restrict tmp)
{
 (void)tmp;

 uint32_t a0 = dec32le(a);
 uint32_t a1 = dec32le(a + 4);
 uint32_t b0 = dec32le(b);
 uint32_t b1 = dec32le(b + 4);

 uint64_t c0 = bp_mul_32(a0, b0);
 uint64_t c1 = bp_mul_32(a1, b1);
 uint64_t c2 = bp_mul_32(a0 ^ a1, b0 ^ b1) ^ c0 ^ c1;

 enc64le(d, dec64le(d) ^ c0 ^ (c2 << 32));
 enc64le(d + 8, dec64le(d + 8) ^ c1 ^ (c2 >> 32));
}
```

bp_muladd_64原始代码的实现步骤如下：

**输入分解**：

将输入的 a 和 b 各分为两个32位块：a0（低32位）、a1（高32位），b0（低32位）、b1（高32位）。

例如：a = a0 | (a1 << 32)，b = b0 | (b1 << 32)。

**部分乘积计算**：

计算四个部分积：

c0 = a0 * b0（低32位乘积）

c1 = a1 * b1（高32位乘积）

c2 = (a0 ^ a1) * (b0 ^ b1)（交叉项的乘积）

**结果组合**：

通过异或操作合并部分积：

c0 和 c2 的低32位组合到结果的低64位。

c1 和 c2 的高32位组合到结果的高64位。

**累加到目标数组**：

将最终结果异或到目标数组 d 中。

## 优化方案

经过昨天的工作，其实这里能做的工作已然不多，只能加速一下异或和乘法操作了。

其中最重要的是下面这两行。

```c
enc64le(d, dec64le(d) ^ c0 ^ (c2 << 32));
enc64le(d + 8, dec64le(d + 8) ^ c1 ^ (c2 >> 32));
```

这两行代码在实现上是对一个二进制多项式的特定部分进行更新。具体来说，它们对 `d`指向的内存区域的两个连续的64位二进制数进行操作。以下是详细的操作步骤：

1. **读取现有数据**:
  - 使用 `dec64le(d)`从 `d`指向的内存位置读取一个64位的二进制数。
  - 使用 `dec64le(d + 8)`从 `d + 8`指向的内存位置读取另一个64位的二进制数。
1. **计算新值**:
  - 对于第一个64位数，计算其与 `c0`和 `c2`左移32位的结果的异或。
  - 对于第二个64位数，计算其与 `c1`和 `c2`右移32位的结果的异或。
1. **写回内存**:
  - 将计算得到的新值以小端序的形式编码回 `d`指向的内存位置。
  - 将计算得到的另一个新值以小端序的形式编码回 `d + 8`指向的内存位置。

```c
bp_muladd_64(uint8_t *restrict d, const uint8_t *restrict a,
 const uint8_t *restrict b, uint8_t *restrict tmp)
{
     // 加载a和b的低32位和高32位
    __m256i a_vec = _mm256_loadu_si256((__m256i*)a);
    __m256i b_vec = _mm256_loadu_si256((__m256i*)b);

    // 提取a0, a1, b0, b1
    uint32_t a0 = _mm256_extract_epi32(a_vec, 0);
    uint32_t a1 = _mm256_extract_epi32(a_vec, 1);
    uint32_t b0 = _mm256_extract_epi32(b_vec, 0);
    uint32_t b1 = _mm256_extract_epi32(b_vec, 1);

    // 计算c0, c1, c2
    uint64_t c0 = bp_mul_32(a0, b0);
    uint64_t c1 = bp_mul_32(a1, b1);
    uint64_t c2 = bp_mul_32(a0 ^ a1, b0 ^ b1) ^ c0 ^ c1;

    // 使用AVX2加速XOR操作
    __m256i d_vec = _mm256_loadu_si256((__m256i*)d);
    __m256i c0_vec = _mm256_set1_epi64x(c0);
    __m256i c1_vec = _mm256_set1_epi64x(c1);
    __m256i c2_vec = _mm256_set1_epi64x(c2);

    d_vec = _mm256_xor_si256(d_vec, c0_vec);
    d_vec = _mm256_xor_si256(d_vec, _mm256_slli_epi64(c2_vec, 32));
    _mm256_storeu_si256((__m256i*)d, d_vec);

    d_vec = _mm256_loadu_si256((__m256i*)(d + 8));
    d_vec = _mm256_xor_si256(d_vec, c1_vec);
    d_vec = _mm256_xor_si256(d_vec, _mm256_srli_epi64(c2_vec, 32));
    _mm256_storeu_si256((__m256i*)(d + 8), d_vec);
}
```
