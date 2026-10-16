---
title: 验签部分优化-FTT
date: 2025-03-28 18:48:21
updated: 2025-04-08
tags:
  - AVX2
  - Hawk
---

## 代码分析

### **逐行分析代码：**

1. `static void fx32_FFT(unsigned logn, uint32_t *a)`

  - **函数定义**：静态函数，用于计算定点数快速傅里叶变换（FFT）。
  - **参数**：
      - `logn`：FFT 的级数，表示输入数据大小为 `n = 2^logn`。
      - `a`：指向复数数组的指针，实部和虚部分别存储在前半和后半（如 `a[0]` 是第一个实部，`a[hn]` 是第一个虚部）。

1. `size_t hn = (size_t)1 << (logn - 1);`

  - 计算 `n` 的一半 `hn`，即 `hn = n/2 = 2^(logn-1)`。

1. `size_t t = hn;`

  - 初始化跨度 `t` 为 `hn`，用于控制蝴蝶操作的初始步长。

1. `for (unsigned lm = 1; lm < logn; lm++)`

  - **外层循环**：遍历 FFT 的每个阶段（总共有 `logn-1` 个阶段）。
  - `lm` 表示当前阶段，`m = 2^lm` 是该阶段的子数组大小。

1. `size_t m = (size_t)1 << lm;`

  - 当前阶段的子数组大小 `m`，从 2 开始，每次翻倍（如 `lm=1` 时 `m=2`，`lm=2` 时 `m=4`）。

1. `size_t ht = t >> 1;`

  - 计算当前阶段的半跨度 `ht = t/2`，用于分块处理。

1. `size_t j0 = 0;`

  - 初始化当前块的起始索引 `j0`，用于遍历不同块。

1. `size_t hm = m >> 1;`

  - 计算当前阶段的旋转因子数量 `hm = m/2`。

1. `for (size_t i = 0; i < hm; i++)`

  - **中层循环**：遍历当前阶段的每个旋转因子组。
  - `i` 是旋转因子索引，用于选择预计算的旋转因子。

1. `uint32_t s_re = (uint32_t)FX32_GM[((i + m) << 1) + 0];`

  `uint32_t s_im = (uint32_t)FX32_GM[((i + m) << 1) + 1];`

  - 从全局数组 `FX32_GM` 获取旋转因子的实部 (`s_re`) 和虚部 (`s_im`)，格式为 Q31 定点数。

1. \*\*`for (size_t j = j0; j < j0 + ht; j++)`

  - **内层循环**：执行当前块内的蝴蝶操作。
  - `j` 是当前蝴蝶操作的索引。

1. `uint32_t x1_re = a[j];`

  `uint32_t x1_im = a[j + hn];`

  `uint32_t x2_re = a[j + ht];`

  `uint32_t x2_im = a[j + ht + hn];`

  - 提取两个复数 `x1` 和 `x2` 的实部与虚部：
      - `x1` 的位置：实部在 `a[j]`，虚部在 `a[j + hn]`。
      - `x2` 的位置：实部在 `a[j + ht]`，虚部在 `a[j + ht + hn]`。

1. `#define M(c, d) ...`

  `#define SSX(c) ...`

  - **宏定义**：
      - `M(c, d)`：计算两个 Q31 定点数的有符号乘法，返回 64 位结果。
      - `SSX(c)`：将 Q31 定点数左移 31 位，转换为 64 位 Q63 格式。

1. `uint64_t t_re = M(x2_re, s_re) - M(x2_im, s_im);`

  `uint64_t t_im = M(x2_re, s_im) + M(x2_im, s_re);`

  - 计算旋转因子 `s` 与 `x2` 的乘积 `t = s * x2`，结果为复数（实部 `t_re`，虚部 `t_im`）。

1. \*\*更新数组 `a`\*\*：

  ```c
  a[j] = (SSX(x1_re) + t_re) >> 32;
  a[j + hn] = (SSX(x1_im) + t_im) >> 32;
  a[j + ht] = (SSX(x1_re) - t_re) >> 32;
  a[j + ht + hn] = (SSX(x1_im) - t_im) >> 32;
  ```

  - 执行蝴蝶操作：
      - `x1_new = (x1 + t) / 2`：通过左移 31 位（`SSX`）和右移 32 位实现除法。
      - `x2_new = (x1 - t) / 2`：同理，结果写回数组。

1. **循环更新**：

  - `j0 += t`：移动到下一个块。
  - `t = ht`：更新跨度为当前阶段的一半。

---

### **变量含义总结：**

| **变量** | **类型** | **含义** |
| --- | --- | --- |
| `logn` | `unsigned` | FFT 的级数，输入数据大小为 `n = 2^logn`。 |
| `a` | `uint32_t*` | 复数数组指针，实部和虚部分别存储在前半和后半（Q31 定点数）。 |
| `hn` | `size_t` | `n` 的一半，`hn = 2^(logn-1)`。 |
| `t` | `size_t` | 当前蝴蝶操作的跨度，初始为 `hn`，每阶段减半。 |
| `lm` | `unsigned` | 外层循环变量，表示当前阶段（从 1 到 `logn-1`）。 |
| `m` | `size_t` | 当前阶段的子数组大小，`m = 2^lm`。 |
| `ht` | `size_t` | 当前阶段的半跨度，`ht = t/2`。 |
| `j0` | `size_t` | 当前块的起始索引，每次增加 `t` 以处理下一个块。 |
| `hm` | `size_t` | 当前阶段的旋转因子数量，`hm = m/2`。 |
| `i` | `size_t` | 中层循环变量，遍历旋转因子组。 |
| `s_re`, `s_im` | `uint32_t` | 旋转因子的实部和虚部（Q31 格式，取自 `FX32_GM`）。 |
| `j` | `size_t` | 内层循环变量，执行蝴蝶操作的索引。 |
| `x1_re`, `x1_im` | `uint32_t` | 蝴蝶操作中的第一个复数的实部和虚部。 |
| `x2_re`, `x2_im` | `uint32_t` | 蝴蝶操作中的第二个复数的实部和虚部。 |
| `t_re`, `t_im` | `uint64_t` | 中间变量，存储 `s * x2` 的乘积结果（实部和虚部）。 |

---

### **关键逻辑：**

- **FFT 阶段分解**：通过三层循环逐级分解 FFT，外层控制阶段，中层处理旋转因子，内层执行蝴蝶操作。
- **定点数运算**：使用 Q31 格式存储数据，通过宏 `M` 和 `SSX` 实现高精度乘法和舍入。
- **内存布局**：实部和虚部分开存储，前半为实部，后半为虚部，蝴蝶操作通过索引偏移访问数据。

---

## 优化方案

我们观察到，在循环中最内层循环显然可以被并行化，当ht≥4时，循环至少进行四次且其中变量互不干扰。当ht≤4时，需要单独处理，但这部分对性能影响很小。

```c
for (size_t j = j0; j < j0 + ht; j ++) {
    uint32_t x1_re = a[j];
    uint32_t x1_im = a[j + hn];
    uint32_t x2_re = a[j + ht];
    uint32_t x2_im = a[j + ht + hn];

#define M(c, d)   ((uint64_t)((int64_t)*(int32_t *)&(c) \
                   * (int64_t)*(int32_t *)&(d)))
#define SSX(c)    ((uint64_t)*(int32_t *)&(c) << 31)
    /*
     * t <- s*x2
     * (x1, x2) <- ((x1 + t)/2, (x2 - t)/2)
     */
    uint64_t t_re = M(x2_re, s_re) - M(x2_im, s_im);
    uint64_t t_im = M(x2_re, s_im) + M(x2_im, s_re);
    a[j]           = (SSX(x1_re) + t_re) >> 32;
    a[j + hn]      = (SSX(x1_im) + t_im) >> 32;
    a[j + ht]      = (SSX(x1_re) - t_re) >> 32;
    a[j + ht + hn] = (SSX(x1_im) - t_im) >> 32;
#undef M
#undef SSX
   }
```

同时利用AVX2指令集的特性，我们几乎可以忽略其中的有符号数和无符号数变换。我们将并行操作项定为四项，这是因为其中有对64位变量的操作，以及合理规避掉\_mm256_mullo_epi64这个无法使用的内联函数，转而使用\_mm256_mul_epi32来同时完成位数扩展和符号处理。同时在这里我们需要使用两个自建函数，一个功能是将4个32位数加载到256位变量中并分别扩展到64位，另一个功能是从256位变量中取出每64位的低32位并组合为128位变量，后者同时也减少了一次移位操作。

```c
__m256i load_4x32bits_sign_extend(uint32_t *data)
{
 __m128i vec128 = _mm_loadu_si128((const __m128i *)data); // 加载4个32位整数
 return _mm256_cvtepi32_epi64(vec128);      // 符号扩展为64位
}
__m128i extract_high32_from_256(__m256i vec) {
    // 重排列索引：收集各64位的高32位到前四个32位位置
    __m256i idx = _mm256_setr_epi32(1,3,5,7,0,2,4,6);
    __m256i permuted = _mm256_permutevar8x32_epi32(vec, idx);
  
    // 提取低128位作为结果
    return _mm256_castsi256_si128(permuted);
}

static void
fx32_FFT(unsigned logn, uint32_t *a)
{
 size_t hn = (size_t)1 << (logn - 1);
 size_t t = hn;
 for (unsigned lm = 1; lm < logn - 2; lm++)
 { 
  size_t m = (size_t)1 << lm;
  size_t ht = t >> 1;
  size_t j0 = 0;
  size_t hm = m >> 1;
  for (size_t i = 0; i < hm; i++)
  {
   uint32_t s_re = (uint32_t)FX32_GM[((i + m) << 1) + 0];
   uint32_t s_im = (uint32_t)FX32_GM[((i + m) << 1) + 1];
   __m256i avx2_256_s_re = _mm256_set1_epi64x((int64_t)*(int32_t *)&s_re);
   __m256i avx2_256_s_im = _mm256_set1_epi64x((int64_t)*(int32_t *)&s_im);
   for (size_t j = j0; j < j0 + ht; j += 4)
   {
    /*
    uint32_t x1_re = a[j];
    uint32_t x1_im = a[j + hn];
    uint32_t x2_re = a[j + ht];
    uint32_t x2_im = a[j + ht + hn];
    */
    __m256i avx2_256_x1_re = load_4x32bits_sign_extend(a + j);
    __m256i avx2_256_x1_im = load_4x32bits_sign_extend(a + j + hn);
    __m256i avx2_256_x2_re = load_4x32bits_sign_extend(a + j + ht);
    __m256i avx2_256_x2_im = load_4x32bits_sign_extend(a + j + ht + hn);

//#define M(c, d) ((uint64_t)((int64_t)*(int32_t *)&(c) * (int64_t)*(int32_t *)&(d)))
//#define SSX(c) ((uint64_t)*(int32_t *)&(c) << 31)
    /*
     * t <- s*x2
     * (x1, x2) <- ((x1 + t)/2, (x2 - t)/2)
     */
    /*
    uint64_t t_re = M(x2_re, s_re) - M(x2_im, s_im);
    uint64_t t_im = M(x2_re, s_im) + M(x2_im, s_re);
    */
    uint64_t t_re;
    __m256i avx2_256_t_re = _mm256_sub_epi64(_mm256_mul_epi32(avx2_256_x2_re, avx2_256_s_re), _mm256_mul_epi32(avx2_256_x2_im, avx2_256_s_im));
    t_re = _mm256_extract_epi64(avx2_256_t_re, 1);
    uint64_t t_im;
    __m256i avx2_256_t_im = _mm256_add_epi64(_mm256_mul_epi32(avx2_256_x2_re, avx2_256_s_im), _mm256_mul_epi32(avx2_256_x2_im, avx2_256_s_re));
    t_im = _mm256_extract_epi64(avx2_256_t_im, 1);
    /*
    a[j] = (SSX(x1_re) + t_re) >> 32;
    a[j + hn] = (SSX(x1_im) + t_im) >> 32;
    a[j + ht] = (SSX(x1_re) - t_re) >> 32;
    a[j + ht + hn] = (SSX(x1_im) - t_im) >> 32;
    */

    avx2_256_x1_re = _mm256_slli_epi64(avx2_256_x1_re, 31);
    avx2_256_x1_im = _mm256_slli_epi64(avx2_256_x1_im, 31);
    _mm_store_si128((__m128i *)(a + j), extract_high32_from_256(_mm256_add_epi64(avx2_256_x1_re, avx2_256_t_re)));
    _mm_store_si128((__m128i *)(a + j + hn), extract_high32_from_256(_mm256_add_epi64(avx2_256_x1_im, avx2_256_t_im)));
    _mm_store_si128((__m128i *)(a + j + ht), extract_high32_from_256(_mm256_sub_epi64(avx2_256_x1_re, avx2_256_t_re)));
    _mm_store_si128((__m128i *)(a + j + ht + hn), extract_high32_from_256(_mm256_sub_epi64(avx2_256_x1_im, avx2_256_t_im)));

//#undef SSX
   }
   j0 += t;
  }
  t = ht;
 }
 for (unsigned lm = logn - 2; lm < logn; lm++)
 { 
  size_t m = (size_t)1 << lm;
  size_t ht = t >> 1;
  size_t j0 = 0;
  size_t hm = m >> 1;
  for (size_t i = 0; i < hm; i++)
  {
   uint32_t s_re = (uint32_t)FX32_GM[((i + m) << 1) + 0];
   uint32_t s_im = (uint32_t)FX32_GM[((i + m) << 1) + 1];
   for (size_t j = j0; j < j0 + ht; j++)
   {
    uint32_t x1_re = a[j];
    uint32_t x1_im = a[j + hn];
    uint32_t x2_re = a[j + ht];
    uint32_t x2_im = a[j + ht + hn];

#define M(c, d) ((uint64_t)((int64_t)*(int32_t *)&(c) * (int64_t)*(int32_t *)&(d)))
#define SSX(c) ((uint64_t)*(int32_t *)&(c) << 31)
    /*
     * t <- s*x2
     * (x1, x2) <- ((x1 + t)/2, (x2 - t)/2)
     */
    uint64_t t_re = M(x2_re, s_re) - M(x2_im, s_im);
    uint64_t t_im = M(x2_re, s_im) + M(x2_im, s_re);
    a[j] = (SSX(x1_re) + t_re) >> 32;
    a[j + hn] = (SSX(x1_im) + t_im) >> 32;
    a[j + ht] = (SSX(x1_re) - t_re) >> 32;
    a[j + ht + hn] = (SSX(x1_im) - t_im) >> 32;
#undef M
#undef SSX
   }
   j0 += t;
  }
  t = ht;
 }
}
```
