---
title: 签名部分优化-XOR
date: 2025-02-27 19:07:11
updated: 2025-03-03
tags:
  - AVX2
  - Hawk
---

字数：628，阅读时间：4分钟

## 头文件特殊解析

在官方提供的AVX2优化方案中，头文件 `hawk_inner.h` 中多出了下面这一段。

```c
/*
 * This implementation uses AVX2 intrinsics.
 */
#include <immintrin.h>
#if defined __GNUC__ || defined __clang__
#include <x86intrin.h>
#endif
#ifndef HAWK_LE
#define HAWK_LE   1
#endif
#ifndef HAWK_UNALIGNED
#define HAWK_UNALIGNED   1
#endif
#if defined __GNUC__
#define TARGET_AVX2         __attribute__((target("avx2,bmi,pclmul")))
#define TARGET_AVX2_ONLY    __attribute__((target("avx2")))
#define ALIGNED_AVX2   __attribute__((aligned(32)))
#elif defined _MSC_VER && _MSC_VER
#pragma warning( disable : 4752 )
#endif
```

这段代码可以作如下解释

- `#include <immintrin.h>`：这是Intel提供的头文件，包含了AVX2和其他SIMD指令集的内联函数定义。
- `#if defined __GNUC__ || defined __clang__`：这是一个条件编译指令，检查编译器是否是GCC（GNU Compiler Collection）或Clang。
  - 如果是GCC或Clang，则包含 `<x86intrin.h>`头文件，该头文件提供了x86架构特有的内联函数支持。
- `HAWK_LE`：如果未定义，则定义为1。可能用于指示代码是小端（Little Endian）模式。
- `HAWK_UNALIGNED`：如果未定义，则定义为1。可能用于指示是否支持非对齐内存访问（unaligned memory access）。
- **GCC或Clang**：
  - `TARGET_AVX2`：定义一个属性 `__attribute__((target("avx2,bmi,pclmul")))`，指示编译器生成的代码需要支持AVX2、BMI（Bit Manipulation Instructions）和PCLMUL（Carry-Less Multiplication）指令集。
  - `TARGET_AVX2_ONLY`：定义一个属性 `__attribute__((target("avx2")))`，指示编译器生成的代码只需要支持AVX2指令集。
  - `ALIGNED_AVX2`：定义一个属性 `__attribute__((aligned(32)))`，指示数据需要32字节对齐（AVX2指令集通常要求数据对齐）。
- **MSVC（Microsoft Visual C++）**：
  - `#pragma warning( disable : 4752 )`：禁用警告4752。该警告通常与浮点优化相关，禁用它是为了避免编译器在优化AVX2代码时产生不必要的警告。

所以我们可以看到，在官方提供的AVX2优化方案中，有一部分函数前加上了如 `TARGET_AVX2` 的属性，这一点在之后的优化需要加以注意。

## XOR函数优化

虽然我现在还不完全能看明白签名部分的算法原理，但这并不影响找到一些可优化点。很容易发现，在代码中存在着 `bp_xor_64` 、`bp_xor_128` 、`bp_xor_256` 、`bp_xor_512` 、`bp_xor_1024` 这一类异或函数，其中的计算都是可并行化的，符合使用AVX2优化的要求。

```c
static inline void
bp_xor_64(uint8_t *d, const uint8_t *a, const uint8_t *b)
{
#if HAWK_UNALIGNED
 *(uint64_t *)d = *(const uint64_t *)a ^ *(const uint64_t *)b;
#else
 for (size_t u = 0; u < 8; u ++) {
  d[u] = a[u] ^ b[u];
 }
#endif
}

static inline void
bp_xor_128(uint8_t *d, const uint8_t *a, const uint8_t *b)
{
#if HAWK_UNALIGNED
 const uint64_t *aq = (uint64_t *)a;
 const uint64_t *bq = (uint64_t *)b;
 uint64_t *dq = (uint64_t *)d;
 for (size_t u = 0; u < 2; u ++) {
  dq[u] = aq[u] ^ bq[u];
 }
#else
 for (size_t u = 0; u < 16; u ++) {
  d[u] = a[u] ^ b[u];
 }
#endif
}

static inline void
bp_xor_256(uint8_t *d, const uint8_t *a, const uint8_t *b)
{
#if HAWK_UNALIGNED
 const uint64_t *aq = (uint64_t *)a;
 const uint64_t *bq = (uint64_t *)b;
 uint64_t *dq = (uint64_t *)d;
 for (size_t u = 0; u < 4; u ++) {
  dq[u] = aq[u] ^ bq[u];
 }
#else
 for (size_t u = 0; u < 32; u ++) {
  d[u] = a[u] ^ b[u];
 }
#endif
}

static inline void
bp_xor_512(uint8_t *d, const uint8_t *a, const uint8_t *b)
{
#if HAWK_UNALIGNED
 const uint64_t *aq = (uint64_t *)a;
 const uint64_t *bq = (uint64_t *)b;
 uint64_t *dq = (uint64_t *)d;
 for (size_t u = 0; u < 8; u ++) {
  dq[u] = aq[u] ^ bq[u];
 }
#else
 for (size_t u = 0; u < 64; u ++) {
  d[u] = a[u] ^ b[u];
 }
#endif
}

static inline void
bp_xor_1024(uint8_t *d, const uint8_t *a, const uint8_t *b)
{
#if HAWK_UNALIGNED
 const uint64_t *aq = (uint64_t *)a;
 const uint64_t *bq = (uint64_t *)b;
 uint64_t *dq = (uint64_t *)d;
 for (size_t u = 0; u < 16; u ++) {
  dq[u] = aq[u] ^ bq[u];
 }
#else
 for (size_t u = 0; u < 128; u ++) {
  d[u] = a[u] ^ b[u];
 }
#endif
}
```

这里的 `#if HAWK_UNALIGNED` 实际上是一种降低可执行文件大小的方法，意为如果 `HAWK_UNALIGNED` 为1，则编译这一段代码，否则直接编译另一段代码，也是一种节约内存和文件大小的技巧，因此，在优化方案中也要同时设计对齐和非对齐的处理方案。

而优化这一段代码的方案也比较简单，所需要做的只是使用AVX2指令从内存中加载，然后使用AVX2的异或指令即可。而且因为异或操作并不涉及进位，所以在512位前直接加载即可，不需要设计数组。

```c
static inline void
bp_xor_64(uint8_t *d, const uint8_t *a, const uint8_t *b)
{
#if HAWK_UNALIGNED
 __m128i a_vec = _mm_loadu_si128((__m128i*)a);  // 加载128位数据
    __m128i b_vec = _mm_loadu_si128((__m128i*)b);
    __m128i d_vec = _mm_xor_si128(a_vec, b_vec);   // 执行XOR操作
    _mm_storeu_si128((__m128i*)d, d_vec);          // 存储结果
#else
 __m128i a_vec = _mm_load_si128((__m128i*)a);  // 已经对齐，可以直接加载
 __m128i b_vec = _mm_load_si128((__m128i*)b);
 __m128i d_vec = _mm_xor_si128(a_vec, b_vec); 
 _mm_store_si128((__m128i*)d, d_vec);  
#endif
}

static inline void
bp_xor_128(uint8_t *d, const uint8_t *a, const uint8_t *b)
{
#if HAWK_UNALIGNED
 __m128i a_vec = _mm_loadu_si128((__m128i*)a);
    __m128i b_vec = _mm_loadu_si128((__m128i*)b);
    __m128i d_vec = _mm_xor_si128(a_vec, b_vec);
    _mm_storeu_si128((__m128i*)d, d_vec);
#else
 __m128i a_vec = _mm_load_si128((__m128i*)a);
 __m128i b_vec = _mm_load_si128((__m128i*)b);
 __m128i d_vec = _mm_xor_si128(a_vec, b_vec);
 _mm_store_si128((__m128i*)d, d_vec);
#endif
}

static inline void
bp_xor_256(uint8_t *d, const uint8_t *a, const uint8_t *b)
{
#if HAWK_UNALIGNED
 __m256i a_vec = _mm256_loadu_si256((__m256i*)a);  // 加载256位数据
    __m256i b_vec = _mm256_loadu_si256((__m256i*)b);
    __m256i d_vec = _mm256_xor_si256(a_vec, b_vec);
    _mm256_storeu_si256((__m256i*)d, d_vec);
#else
 __m256i a_vec = _mm256_load_si256((__m256i*)a);  
 __m256i b_vec = _mm256_load_si256((__m256i*)b);
 __m256i d_vec = _mm256_xor_si256(a_vec, b_vec);
 _mm256_store_si256((__m256i*)d, d_vec);
#endif
}

static inline void
bp_xor_512(uint8_t *d, const uint8_t *a, const uint8_t *b)
{
#if HAWK_UNALIGNED
 __m256i *a_vec = (__m256i*)a;
    __m256i *b_vec = (__m256i*)b;
    __m256i *d_vec = (__m256i*)d;
    for (size_t u = 0; u < 2; u++) {  // 512位数据分为2个256位数据，使用AVX2_512或可避免使用数组？
        __m256i av = _mm256_loadu_si256(&a_vec[u]);
        __m256i bv = _mm256_loadu_si256(&b_vec[u]);
        __m256i dv = _mm256_xor_si256(av, bv);
        _mm256_storeu_si256(&d_vec[u], dv);
        }
#else
 __m256i *a_vec = (__m256i*)a;
 __m256i *b_vec = (__m256i*)b;
 __m256i *d_vec = (__m256i*)d;
 for (size_t u = 0; u < 2; u++) {
  __m256i av = _mm256_load_si256(&a_vec[u]);
  __m256i bv = _mm256_load_si256(&b_vec[u]);
  __m256i dv = _mm256_xor_si256(av, bv);
  _mm256_store_si256(&d_vec[u], dv);
 }
#endif
}

static inline void
bp_xor_1024(uint8_t *d, const uint8_t *a, const uint8_t *b)
{
#if HAWK_UNALIGNED
 __m256i *a_vec = (__m256i*)a;
    __m256i *b_vec = (__m256i*)b;
    __m256i *d_vec = (__m256i*)d;
    for (size_t u = 0; u < 4; u++) {
        __m256i av = _mm256_loadu_si256(&a_vec[u]);
        __m256i bv = _mm256_loadu_si256(&b_vec[u]);
        __m256i dv = _mm256_xor_si256(av, bv);
        _mm256_storeu_si256(&d_vec[u], dv);
        }
#else
 __m256i *a_vec = (__m256i*)a;
 __m256i *b_vec = (__m256i*)b;
 __m256i *d_vec = (__m256i*)d;
 for (size_t u = 0; u < 4; u++) {
  __m256i av = _mm256_load_si256(&a_vec[u]);
  __m256i bv = _mm256_load_si256(&b_vec[u]);
  __m256i dv = _mm256_xor_si256(av, bv);
  _mm256_store_si256(&d_vec[u], dv);
 }
#endif
}
```
