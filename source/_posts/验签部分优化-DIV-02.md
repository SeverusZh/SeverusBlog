---
title: 验签部分优化-DIV-02
date: 2025-03-12 18:26:07
tags:
  - AVX2
  - Hawk
---

字数：814，阅读时间：5分钟

# 验签部分优化-DIV-02

## 优化方案

### 声明

```c
static uint32_t
mp_div(uint32_t x, uint32_t y, uint32_t p, uint32_t p0i, uint32_t m16)
```

我们全面修改掉声明的参数和返回值

```c
static __m256i
mp_div_x8(__m256i avx2_256_x, __m256i avx2_256_y, __m256i avx2_256_p,
           __m256i avx2_256_p0i, __m256i avx2_256_m16)
```

### 变量

```c
uint32_t a = y;
uint32_t b = p;
uint32_t u = x;
uint32_t v = 0;
uint32_t af0 = 0;
uint32_t ag0 = 0;
uint32_t af1 = 0;
uint32_t ag1 = 0;
```

```c
__m256i avx2_256_a = avx2_256_y;
__m256i avx2_256_b = avx2_256_p;
__m256i avx2_256_u = avx2_256_x;
__m256i avx2_256_v = _mm256_setzero_si256();
__m256i avx2_256_af0 = _mm256_setzero_si256();
__m256i avx2_256_ag0 = _mm256_setzero_si256();
__m256i avx2_256_af1 = _mm256_setzero_si256();
__m256i avx2_256_ag1 = _mm256_setzero_si256();
```

### 内层循环

```c
for (int j = 0; j < 15; j ++) {
   uint32_t a_odd = -(a & 1);
   uint32_t swap = tbmask(a - b) & a_odd;
   uint32_t t1 = swap & (a ^ b);
   a ^= t1;
   b ^= t1;
   uint32_t t2 = swap & (fg0 ^ fg1);
   fg0 ^= t2;
   fg1 ^= t2;
   a -= a_odd & b;
   fg0 -= a_odd & fg1;
   a >>= 1;
   fg1 <<= 1;
  }
```

```c
for (int j = 0; j < 15; j++) {
    // 计算a是否为奇数
    __m256i avx2_256_a_odd = _mm256_and_si256(avx2_256_a, _mm256_set1_epi32(1));
    avx2_256_a_odd = _mm256_sub_epi32(_mm256_setzero_si256(), avx2_256_a_odd);

    // 计算交换掩码：a > b且a为奇数
    /*
    如果a>b则tbmask返回值为全0，因此这里的计算要反过来才能和原来的逻辑一样
    但我怀疑原来的逻辑有问题
    */
    __m256i avx2_256_a_greater_b = _mm256_cmpgt_epi32(avx2_256_b, avx2_256_a); 
    __m256i avx2_256_swap = _mm256_and_si256(avx2_256_a_greater_b, avx2_256_a_odd);

    // 交换a和b
    __m256i avx2_256_t1 = _mm256_and_si256(avx2_256_swap, _mm256_xor_si256(avx2_256_a, avx2_256_b));
    avx2_256_a = _mm256_xor_si256(avx2_256_a, avx2_256_t1);
    avx2_256_b = _mm256_xor_si256(avx2_256_b, avx2_256_t1);

    // 交换fg0和fg1
    __m256i avx2_256_t2 = _mm256_and_si256(avx2_256_swap, _mm256_xor_si256(avx2_256_fg0, avx2_256_fg1));
    avx2_256_fg0 = _mm256_xor_si256(avx2_256_fg0, avx2_256_t2);
    avx2_256_fg1 = _mm256_xor_si256(avx2_256_fg1, avx2_256_t2);

    // 更新a和fg0
    __m256i avx2_256_b_masked = _mm256_and_si256(avx2_256_a_odd, avx2_256_b);
    avx2_256_a = _mm256_sub_epi32(avx2_256_a, avx2_256_b_masked);

    __m256i avx2_256_fg1_masked = _mm256_and_si256(avx2_256_a_odd, avx2_256_fg1);
    avx2_256_fg0 = _mm256_sub_epi32(avx2_256_fg0, avx2_256_fg1_masked);

    // 右移a和左移fg1
    avx2_256_a = _mm256_srli_epi32(avx2_256_a, 1);
    avx2_256_fg1 = _mm256_slli_epi32(avx2_256_fg1, 1);
}
```

此处计算swap时我发现源代码疑似出现逻辑问题，但如果这个都是错的，那原来的签名方案不是不可靠吗？

> 经过和老师的讨论，认为此处做b-a也没有太大问题，两者本质是可以互换的，只要循环中一直保持就好。to

介绍一下之前没出现过的内敛函数：`_mm256_cmpgt_epi32` 用于对两个包含 8 个 32 位有符号整数的 256 位向量进行逐元素“大于”比较。以下是详细介绍：

---

**函数原型**

```c
__m256i _mm256_cmpgt_epi32(__m256i a, __m256i b);
```

**功能**

- 比较两个向量 `a` 和 `b` 的每个 32 位有符号整数元素。
- 若 `a` 中某元素大于 `b` 中对应元素，则结果向量的对应位置为全 1（即 `0xFFFFFFFF`，表示 `true`）；否则为全 0（`0x00000000`，表示 `false`）。

**示例**

假设输入向量为：

```c
a = [10, 20, 30, 40, 50, 60, 70, 80]
b = [5, 25, 30, 45, 55, 50, 80, 70]
```

比较结果为：

```dns
[0xFFFFFFFF, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0xFFFFFFFF, 0x00000000, 0xFFFFFFFF]
```

当以 `int32_t` 打印时，结果为 `[-1, 0, 0, 0, 0, -1, 0, -1]`。

**应用场景**

- **掩码操作**：结合位操作指令（如 `_mm256_and_si256`）或混合指令（如 `_mm256_blendv_epi8`）筛选或处理满足条件的元素。
- **条件计算**：在 SIMD 并行计算中实现基于比较的条件分支。

**注意事项**

1. **数据类型**：输入必须为 32 位有符号整数向量。若需处理无符号整数，需额外转换或使用其他方法。
2. **指令集支持**：需目标平台支持 AVX2。编译时启用相应选项（如 GCC 的 `mavx2`）。
3. **结果解释**：结果向量的每个 32 位元素为掩码值，可通过类型转换或辅助函数解析。

**示例代码**

```c
#include <immintrin.h>
#include <stdio.h>

void print_m256i(__m256i var) {
    int32_t *val = (int32_t*)&var;
    printf("%d %d %d %d %d %d %d %d\n",
           val[0], val[1], val[2], val[3],
           val[4], val[5], val[6], val[7]);
}

int main() {
    int32_t a_data[8] = {10, 20, 30, 40, 50, 60, 70, 80};
    int32_t b_data[8] = {5, 25, 30, 45, 55, 50, 80, 70};

    __m256i a = _mm256_loadu_si256((__m256i*)a_data);
    __m256i b = _mm256_loadu_si256((__m256i*)b_data);

    __m256i res = _mm256_cmpgt_epi32(a, b);

    printf("Result: ");
    print_m256i(res);// 输出: -1 0 0 0 0 -1 0 -1

    return 0;
}
```

**相关指令**

- 等于比较：`_mm256_cmpeq_epi32`
- 16 位整数比较：`_mm256_cmpgt_epi16`
- 无符号比较：需通过其他方法模拟（如偏移法处理符号位）。

通过 `_mm256_cmpgt_epi32` 可高效实现并行条件判断，优化计算密集型任务的性能。

---

## 外层循环

```c
for (int i = 0; i < 4; i ++) {
  uint32_t fg0 = (uint32_t)1;
  uint32_t fg1 = (uint32_t)1 << 16;
  for (int j = 0; j < 15; j ++) {
  ...
  }
  fg0 += 0x7FFF7FFF;
  fg1 += 0x7FFF7FFF;
  uint32_t f0 = (fg0 & 0xFFFF) - (uint32_t)0x7FFF;
  uint32_t g0 = (uint32_t)0x7FFF - (fg0 >> 16);
  uint32_t f1 = (fg1 & 0xFFFF) - (uint32_t)0x7FFF;
  uint32_t g1 = (uint32_t)0x7FFF - (fg1 >> 16);

  /*
   * We apply update factors only once every two outer
   * iterations. af0, ag0... are the factors from the
   * previous round. The aggregate factors (for two rounds)
   * are thus:
   *   bf0 = af0*f0 - af1*g0
   *   bg0 = ag0*f0 - ag1*g0
   *   bf1 = af0*f1 - af1*g1
   *   bg1 = ag0*f1 - ag1*g1
   * The aggregate update factors are, in fact, exactly the
   * value we would obtain from running 30 inner iterations,
   * so they follow the rules explained in:
   *    https://eprint.iacr.org/2020/972
   * In particular, these factors are at most 2^30 in
   * absolute value. Thus, they do not overflow and we can
   * use them with mp_lin().
   */

  if ((i & 1) == 0) {
   af0 = f0;
   ag0 = g0;
   af1 = f1;
   ag1 = g1;
  } else {
   uint32_t bf0 = af0*f0 - af1*g0;
   uint32_t bg0 = ag0*f0 - ag1*g0;
   uint32_t bf1 = af0*f1 - af1*g1;
   uint32_t bg1 = ag0*f1 - ag1*g1;
   uint32_t nu = mp_lin(u, v, bf0, bg0, p, p0i);
   uint32_t nv = mp_lin(u, v, bf1, bg1, p, p0i);
   u = nu;
   v = nv;
  }
 }
```

```c
for (int i = 0; i < 4; i++) {
    __m256i avx2_256_fg0 = _mm256_set1_epi32(1);
    __m256i avx2_256_fg1 = _mm256_set1_epi32(1 << 16);

    for (int j = 0; j < 15; j++) {
  ...
    }

    // 更新fg0和fg1的累加值
    avx2_256_fg0 = _mm256_add_epi32(avx2_256_fg0, _mm256_set1_epi32(0x7FFF7FFF));
    avx2_256_fg1 = _mm256_add_epi32(avx2_256_fg1, _mm256_set1_epi32(0x7FFF7FFF));

    // 分解更新因子
    __m256i avx2_256_f0 = _mm256_sub_epi32(
        _mm256_and_si256(avx2_256_fg0, _mm256_set1_epi32(0xFFFF)),
        _mm256_set1_epi32(0x7FFF));
    __m256i avx2_256_g0 = _mm256_sub_epi32(
        _mm256_set1_epi32(0x7FFF),
        _mm256_srli_epi32(avx2_256_fg0, 16));
    __m256i avx2_256_f1 = _mm256_sub_epi32(
        _mm256_and_si256(avx2_256_fg1, _mm256_set1_epi32(0xFFFF)),
        _mm256_set1_epi32(0x7FFF));
    __m256i avx2_256_g1 = _mm256_sub_epi32(
        _mm256_set1_epi32(0x7FFF),
        _mm256_srli_epi32(avx2_256_fg1, 16));

    if ((i & 1) == 0) {
        avx2_256_af0 = avx2_256_f0;
        avx2_256_ag0 = avx2_256_g0;
        avx2_256_af1 = avx2_256_f1;
        avx2_256_ag1 = avx2_256_g1;
    } else {
        // 计算聚合因子
        __m256i avx2_256_bf0 = _mm256_sub_epi32(
            _mm256_mullo_epi32(avx2_256_af0, avx2_256_f0),
            _mm256_mullo_epi32(avx2_256_af1, avx2_256_g0));
        __m256i avx2_256_bg0 = _mm256_sub_epi32(
            _mm256_mullo_epi32(avx2_256_ag0, avx2_256_f0),
            _mm256_mullo_epi32(avx2_256_ag1, avx2_256_g0));
        __m256i avx2_256_bf1 = _mm256_sub_epi32(
            _mm256_mullo_epi32(avx2_256_af0, avx2_256_f1),
            _mm256_mullo_epi32(avx2_256_af1, avx2_256_g1));
        __m256i avx2_256_bg1 = _mm256_sub_epi32(
            _mm256_mullo_epi32(avx2_256_ag0, avx2_256_f1),
            _mm256_mullo_epi32(avx2_256_ag1, avx2_256_g1));

        // 应用线性变换
        __m256i avx2_256_nu = mp_lin_x8(avx2_256_u, avx2_256_v, avx2_256_bf0, avx2_256_bg0, avx2_256_p, avx2_256_p0i);
        __m256i avx2_256_nv = mp_lin_x8(avx2_256_u, avx2_256_v, avx2_256_bf1, avx2_256_bg1, avx2_256_p, avx2_256_p0i);
        avx2_256_u = avx2_256_nu;
        avx2_256_v = avx2_256_nv;
    }
}
```

我们在此处假设 `mp_lin_x8`和后续的 `mp_montymul_x8`函数已经存在，事实上这些函数的处理和本函数原理上差异不大。

## 蒙哥马利处理

```c
/*
  * Each inner loop computed the update factors with an implicit
  * 2^15 factor; two inner iteration lead to a 2^30 factor, but
  * mp_lin() divided by R = 2^32. In total, we divided by (2^2)^2,
  * which we must compensate here by multiplying by 16.
  */
 v = mp_montymul(v, m16, p, p0i);

 /* GCD is in b; it is 1 if and only if y was invertible.
    Otherwise, the GCD is greater than 1. */
 return v & tbmask(b - 2);
```

```c
// 最终蒙哥马利修正
avx2_256_v = mp_montymul_x8(avx2_256_v, avx2_256_m16, avx2_256_p, avx2_256_p0i);

// 计算结果有效性掩码（当b=1时有效）
__m256i avx2_256_b_valid = _mm256_cmpeq_epi32(avx2_256_b, _mm256_set1_epi32(1));
return _mm256_and_si256(avx2_256_v, avx2_256_b_valid);
```

## **关键转换说明**

1. **变量向量化**

  所有 `uint32_t`变量转换为 `__m256i`类型，并按 `avx2_256_xx`格式命名，例如 `a`变为 `avx2_256_a`，每个变量包含8个并行操作的32位整数。

2. **AVX2指令替换**

  - 算术运算：使用 `_mm256_add_epi32`、`_mm256_sub_epi32`等
  - 位运算：使用 `_mm256_and_si256`、`_mm256_xor_si256`等
  - 移位操作：使用 `_mm256_srli_epi32`、`_mm256_slli_epi32`
  - 比较操作：使用 `_mm256_cmpgt_epi32`生成掩码

3. **条件处理**

  标量条件逻辑转换为向量掩码操作，例如通过 `_mm256_and_si256`结合比较结果实现条件分支的向量化。

4. **辅助函数向量化**

  假设 `avx2_mp_lin`和 `avx2_mp_montymul`已实现为向量版本，分别处理8个并行模运算。

5. **掩码生成优化**

  使用 `_mm256_cmpeq_epi32`直接生成有效性掩码替代原 `tbmask`，更直观高效。
