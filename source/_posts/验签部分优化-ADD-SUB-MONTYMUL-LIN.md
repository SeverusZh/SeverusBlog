---
title: 验签部分优化-ADD/SUB/MONTYMUL/LIN
date: 2025-03-12 18:26:22
tags:
  - AVX2
  - Hawk
---

## 模加

```c
static inline uint32_t
mp_add(uint32_t a, uint32_t b, uint32_t p)
{
 uint32_t d = a + b - p;
 return d + (p & tbmask(d));
}
```

```c
/* 向量化模加 */
static inline __m256i
mp_add_x8(__m256i avx2_256_a, __m256i avx2_256_b, __m256i avx2_256_p)
{
 // a + b - p 的向量化实现
 __m256i avx2_256_d = _mm256_sub_epi32(
  _mm256_add_epi32(avx2_256_a, avx2_256_b),
  avx2_256_p
 );

 // 条件修正：d + (p & tbmask(d))
 __m256i avx2_256_mask = _mm256_srai_epi32(avx2_256_d,31);
 return _mm256_add_epi32(
  avx2_256_d,
  _mm256_and_si256(avx2_256_p, avx2_256_mask)
 );
}
```

---

介绍一下 `_mm256_srai_epi32`：`_mm256_srai_epi32` 是 Intel AVX2 指令集中的一个内联函数，用于对包含 8 个 32 位有符号整数的向量（256 位）执行**算术右移**操作。以下是详细介绍：

**函数原型**

```cpp
__m256i _mm256_srai_epi32(__m256i a, int imm8);
```

- **参数**：
  - `a`：输入的 256 位向量，包含 8 个 32 位有符号整数。
  - `imm8`：右移的位数（立即数），范围需在 **0–31** 之间。
- **返回值**：新的 256 位向量，每个 32 位整数均为 `a` 中对应元素算术右移 `imm8` 位的结果。

---

**功能说明**

1. **算术右移（Arithmetic Shift Right）**：
   - 对有符号整数右移时，高位用符号位（0 正，1 负）填充。
   - 等价于对有符号整数进行 **除以 2imm8** 的运算（向负无穷舍入）。
2. **操作示例**：
   - 若 `a` 中的元素为 `0x80000000`（-2147483648），右移 3 位后结果为 `0xF0000000`（-268435456）。
   - 若 `imm8 = 2`，则每个元素右移 2 位，相当于除以 4。
3. **对比逻辑右移**：
   - 逻辑右移（`_mm256_srli_epi32`）用 0 填充高位，适用于无符号整数。

---

**应用场景**

- **快速除法**：对有符号整数进行高效的 2*k* 除法（如图像处理、信号缩放）。
- **数值调整**：批量处理负数的高位扩展或数据压缩。

---

**代码示例**

```cpp
cpp
#include <immintrin.h>
#include <stdio.h>

void print_epi32(__m256i vec) {
    int32_t values[8];
    _mm256_storeu_si256((__m256i*)values, vec);
    for (int i = 0; i < 8; i++)
        printf("%d ", values[i]);
    printf("\n");
}

int main() {
// 初始化向量：[-8, -4, 0, 4, 8, 16, 32, 64]
    __m256i a = _mm256_set_epi32(-8, -4, 0, 4, 8, 16, 32, 64);

// 算术右移2位：相当于除以4
    __m256i result = _mm256_srai_epi32(a, 2);

    print_epi32(result);
// 输出：-2 -1 0 1 2 4 8 16
    return 0;
}
```

---

**注意事项**

1. **立即数范围**：`imm8` 必须为 0–31，超出可能导致未定义行为。
2. **硬件支持**：需支持 AVX2 指令集（如 Intel Haswell 及以后架构、AMD Ryzen 等）。
3. **性能**：通常单周期完成，适合数据并行的批量计算。

---

## 模减

```c
static inline uint32_t
mp_sub(uint32_t a, uint32_t b, uint32_t p)
{
 uint32_t d = a - b;
 return d + (p & tbmask(d));
}
```

```c
/* 向量化模减 */
static inline __m256i
mp_sub_x8(__m256i avx2_256_a, __m256i avx2_256_b, __m256i avx2_256_p)
{
 // a - b 的向量化实现
 __m256i avx2_256_d = _mm256_sub_epi32(avx2_256_a, avx2_256_b);

 // 条件修正：d + (p & tbmask(d))
 __m256i avx2_256_mask = _mm256_srai_epi32(avx2_256_d,31);
 return _mm256_add_epi32(
  avx2_256_d,
  _mm256_and_si256(avx2_256_p, avx2_256_mask)
 );
}
```

## 蒙哥马利乘法

首先扩展实现一下对256位变量中对每一个32位整数相乘求高位的函数：

```c
__m256i avx2_256_mul32_hi(__m256i avx2_256_a, __m256i avx2_256_b) { //用于计算32位相乘的高位结果
 __m256i indices = _mm256_setr_epi32(1, 0, 3, 2, 5, 4, 7, 6);//索引交换
 __m256i avx2_256_a_re = _mm256_permutevar8x32_epi32(avx2_256_a, indices);
 __m256i avx2_256_b_re = _mm256_permutevar8x32_epi32(avx2_256_b, indices);
 return _mm256_add_epi32(_mm256_permutevar8x32_epi32(_mm256_srli_epi32(
  _mm256_mul_epu32(avx2_256_a_re,avx2_256_b_re),32),indices),
  _mm256_srli_epi32(_mm256_mul_epu32(avx2_256_b,avx2_256_a),32));
}
```

由于我们低位高位分开计算且后面还需要给高位加上低位的进位，所以扩展一下判断低位加和是否产生进位：

```c
__m256i check_overflow_avx2(__m256i a, __m256i b) {
 // 计算原始和与溢出掩码
 __m256i sum = _mm256_add_epi32(a, b);
 const __m256i sign_offset = _mm256_set1_epi32(0x80000000);
 __m256i a_signed = _mm256_sub_epi32(a, sign_offset);
 __m256i sum_signed = _mm256_sub_epi32(sum, sign_offset);

 // 获取原始溢出掩码（全1或全0）
 __m256i overflow_mask = _mm256_cmpgt_epi32(a_signed, sum_signed);

 // 将全1掩码转换为0x1，全0保持为0x0
 const __m256i bitmask = _mm256_set1_epi32(0x1);
 __m256i result = _mm256_and_si256(overflow_mask, bitmask);

 return result;
}
```

乘法本身比较好实现：

```c
static inline uint32_t
mp_montymul(uint32_t a, uint32_t b, uint32_t p, uint32_t p0i)
{
 uint64_t z = (uint64_t)a * (uint64_t)b;
 uint32_t w = (uint32_t)z * p0i;
 uint32_t d = (uint32_t)((z + (uint64_t)w * (uint64_t)p) >> 32) - p;
 return d + (p & tbmask(d));
}
```

```c
/* 向量化蒙哥马利乘法 */
static inline __m256i
mp_montymul_x8(__m256i avx2_256_a, __m256i avx2_256_b,
      __m256i avx2_256_p, __m256i avx2_256_p0i)
{
 // 64位乘法低32位 (z = a*b)
 __m256i avx2_256_z_lo = _mm256_mullo_epi32(avx2_256_a, avx2_256_b);
 __m256i avx2_256_z_hi = avx2_256_mul32_hi(avx2_256_a, avx2_256_b);

 // 计算w = z_lo * p0i (32位乘法)
 __m256i avx2_256_w = _mm256_mullo_epi32(avx2_256_z_lo, avx2_256_p0i);

 // 计算m = w * p (32位乘法)
 __m256i avx2_256_m_lo = _mm256_mullo_epi32(avx2_256_w, avx2_256_p);
 __m256i avx2_256_m_hi = avx2_256_mul32_hi(avx2_256_w, avx2_256_p);

 // 计算t = (z_lo + m) >> 32 (模拟64位加法的高32位)
 __m256i avx2_256_t = _mm256_add_epi32(avx2_256_z_hi, avx2_256_m_hi);
 avx2_256_t = _mm256_add_epi32(avx2_256_t, check_overflow_avx2(avx2_256_z_lo, avx2_256_m_lo));

 // 最终结果d = (uint32_t)t - p
 __m256i avx2_256_d = _mm256_sub_epi32(
  _mm256_and_si256(avx2_256_t, _mm256_set1_epi32(0xFFFFFFFF)),  // 取低32位
  avx2_256_p
 );

 // 条件修正：d + (p & tbmask(d))
 __m256i avx2_256_mask = _mm256_srai_epi32(avx2_256_d,31);
 return _mm256_add_epi32(
  avx2_256_d,
  _mm256_and_si256(avx2_256_p, avx2_256_mask)
 );
}
```

## LIN函数

```c
static inline uint32_t
mp_lin(uint32_t u, uint32_t v, uint32_t f, uint32_t g, uint32_t p, uint32_t p0i)
{
 uint32_t sf = tbmask(f);
 f = (f ^ sf) - sf;
 uint32_t sg = tbmask(g);
 g = (g ^ sg) - sg;

 /* We can do a simpler conditional negation because Montgomery
    reduction works over values up to p*2^32, so we can allow
    intermediate values to go up to p. */
 u += sf & (p - (u << 1));
 v += sg & (p - (v << 1));
 return mp_sub(mp_montymul(u, f, p, p0i), mp_montymul(v, g, p, p0i), p);
}
```

```c
static inline uint32_t
mp_lin(uint32_t u, uint32_t v, uint32_t f, uint32_t g, uint32_t p, uint32_t p0i)
{
 uint32_t sf = tbmask(f);
 f = (f ^ sf) - sf;
 uint32_t sg = tbmask(g);
 g = (g ^ sg) - sg;

 /* We can do a simpler conditional negation because Montgomery
    reduction works over values up to p*2^32, so we can allow
    intermediate values to go up to p. */
 u += sf & (p - (u << 1));
 v += sg & (p - (v << 1));
 return mp_sub(mp_montymul(u, f, p, p0i), mp_montymul(v, g, p, p0i), p);
}
```

---

今天将这些函数一并优化的主要原因是优化他们的原理差不太多，都是比较简单的在原有基础上把32位扩展到256位，`montymul`除外，可能扩展到AVX512会更简单。
