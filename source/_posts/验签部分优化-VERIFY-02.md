---
title: 验签部分优化-VERIFY-02
date: 2025-04-08 02:34:56
tags:
  - AVX2
  - Hawk
---

字数：521，阅读时间：3分钟

# 验签部分优化-VERIFY-02

## 蒙哥马利乘法重写

在源代码中，蒙哥马利乘法只用了四行就完成了计算：

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

这个算法的逻辑很简单，但涉及到了32位向64位的扩展以提取高位结果的过程，这使得这个算法在优化指令集下显得异常复杂，也导致了下面算法出现了多个错误。

```c
__m256i avx2_256_mul32_hi(__m256i avx2_256_a, __m256i avx2_256_b)
{																			 // 用于计算32位相乘的高位结果
	__m256i avx2_256_a_re = _mm256_shuffle_epi32(avx2_256_a, _MM_PERM_BADC); // 交换低32位和高32位
	__m256i avx2_256_b_re = _mm256_shuffle_epi32(avx2_256_b, _MM_PERM_BADC);
	__m256i avx2_256_ab_re = _mm256_and_si256(_mm256_mul_epi32(avx2_256_a_re, avx2_256_b_re), _mm256_set1_epi64x(0xFFFFFFFF00000000));
	__m256i avx2_256_ab_im = _mm256_srli_epi64(_mm256_mul_epi32(avx2_256_a, avx2_256_b), 32);
	return _mm256_or_si256(avx2_256_ab_re, avx2_256_ab_im);
}

__m256i avx2_add_overflow_epu32(__m256i a, __m256i b) {
    // 计算 a + b
    __m256i sum = _mm256_add_epi32(a, b);
    // 调整符号位：将无符号比较转换为有符号比较
    const __m256i adjust = _mm256_set1_epi32(0x80000000);
    const __m256i adjusted_a = _mm256_xor_si256(a, adjust);
    const __m256i adjusted_sum = _mm256_xor_si256(sum, adjust);
  
    // 比较 adjusted_a > adjusted_sum（等价于无符号的 sum < a）
    return _mm256_and_si256(_mm256_cmpgt_epi32(adjusted_a, adjusted_sum),_mm256_set1_epi32(0x1));
}

static inline __m256i
mp_montymul_x8(__m256i avx2_256_a, __m256i avx2_256_b,
			   __m256i avx2_256_p, __m256i avx2_256_p0i)
{
	// 64位乘法低32位 (z = a*b)
	__m256i avx2_256_z_lo = _mm256_mullo_epi32(avx2_256_a, avx2_256_b);
	__m256i avx2_256_z_hi = avx2_256_mul32_hi(avx2_256_a, avx2_256_b);
	//uint64_t debug_z0_64 = (((uint64_t)_mm256_extract_epi32(avx2_256_z_hi, 0)) << 32) | (uint64_t)_mm256_extract_epi32(avx2_256_z_lo, 0);
	// 计算w = z_lo * p0i (32位乘法)
	__m256i avx2_256_w = _mm256_mullo_epi32(avx2_256_z_lo, avx2_256_p0i);

	// 计算m = w * p (32位乘法)
	__m256i avx2_256_m_lo = _mm256_mullo_epi32(avx2_256_w, avx2_256_p);
	__m256i avx2_256_m_hi = avx2_256_mul32_hi(avx2_256_w, avx2_256_p);

	// 计算t = (z_lo + m) >> 32 (模拟64位加法的高32位)
	__m256i avx2_256_t = _mm256_add_epi32(avx2_256_z_hi, avx2_256_m_hi);
	avx2_256_t = _mm256_add_epi32(avx2_256_t, avx2_add_overflow_epu32(avx2_256_z_lo, avx2_256_m_lo));

	// 最终结果d = (uint32_t)t - p
	__m256i avx2_256_d = _mm256_sub_epi32(avx2_256_t, avx2_256_p);

	// 条件修正：d + (p & tbmask(d))
	__m256i avx2_256_mask = _mm256_srai_epi32(avx2_256_d, 31);
	return _mm256_add_epi32(avx2_256_d, _mm256_and_si256(avx2_256_p, avx2_256_mask));
}
```

由于错误还涉及到了一些内存彼此覆盖的内容，导致可能第一个结果正确，而第二个却出现错误。因此我们必须重写该乘法函数。

最直观的方法当然是使用 `AVX512`指令集，将256位扩展到512位来实现，但很不幸的是我的CPU并不支持 `AVX512`指令集，因此该方案只能被排除。

```c
__m256i extract_high32_from_512(__m512i input)
{
	// 设置索引以提取每个64位的高32位（原低32位）
	const __m512i perm_indices = _mm512_setr_epi32(1, 3, 5, 7, 9, 11, 13, 15,
												   0, 2, 4, 6, 8, 10, 12, 14);
	__m512i permuted_low = _mm512_permutexvar_epi32(input, perm_indices);
	return _mm512_castsi512_si256(permuted_low);
}
static inline __m256i
mp_montymul_512_x8(__m256i avx2_256_a, __m256i avx2_256_b,
				   __m256i avx2_256_p, __m256i avx2_256_p0i)
{
	__m256i avx2_256_z_lo = _mm256_mullo_epi32(avx2_256_a, avx2_256_b);
	__m512i avx2_512_z = _mm512_mullo_epi64(_mm512_cvtepu32_epi64(avx2_256_a), _mm512_cvtepu32_epi64(avx2_256_b));
	__m256i avx2_256_w = _mm256_mullo_epi32(avx2_256_z_lo, avx2_256_p0i);
	__m512i avx2_512_m = _mm512_add_epi64(_mm512_mullo_epi64(_mm512_cvtepu32_epi64(avx2_256_w), _mm512_cvtepu32_epi64(avx2_256_p)), avx2_512_z);
	__m256i avx2_256_d = _mm256_sub_epi32(extract_high32_from_512(avx2_512_m), avx2_256_p);
	avx2_256_d = _mm256_add_epi32(avx2_256_d, _mm256_and_si256(avx2_256_p, _mm256_srai_epi32(avx2_256_d, 31)));
	return avx2_256_d;
}
```

显然此时只剩最后一个方案，要想在256位下完善地处理32位扩展到64位乘法，我们只能舍弃一半的操作项数，因此我给这个方案命名为 `mp_montymul_x4x2`。

```c
static inline __m256i
mp_montymul_x4x2(__m256i avx2_256_a, __m256i avx2_256_b,
			   __m256i avx2_256_p, __m256i avx2_256_p0i)
{
	__m256i indices = _mm256_setr_epi32(1,0,3,2,5,4,7,6);
	__m256i avx2_256_a_re = _mm256_permutevar8x32_epi32(avx2_256_a, indices); // 交换低32位和高32位
	__m256i avx2_256_b_re = _mm256_permutevar8x32_epi32(avx2_256_b, indices);
	__m256i avx2_256_z1 = _mm256_mul_epu32(avx2_256_a, avx2_256_b);
	__m256i avx2_256_z2 = _mm256_mul_epu32(avx2_256_a_re, avx2_256_b_re);
	__m256i avx2_256_z_low = _mm256_mullo_epi32(avx2_256_a, avx2_256_b);
	__m256i avx2_256_w = _mm256_mullo_epi32(avx2_256_z_low, avx2_256_p0i);
	__m256i avx2_256_w_re = _mm256_permutevar8x32_epi32(avx2_256_w, indices);
	__m256i avx2_256_p_re = _mm256_permutevar8x32_epi32(avx2_256_p, indices);
	__m256i avx2_256_wp = _mm256_mul_epu32(avx2_256_w, avx2_256_p);
	__m256i avx2_256_wp_re = _mm256_mul_epu32(avx2_256_w_re, avx2_256_p_re);
	__m256i avx2_256_t1 = _mm256_permutevar8x32_epi32(_mm256_and_si256(_mm256_add_epi64(avx2_256_z1, avx2_256_wp),_mm256_set1_epi64x(0xFFFFFFFF00000000)),indices);
	__m256i avx2_256_t2 = _mm256_and_si256(_mm256_add_epi64(avx2_256_z2, avx2_256_wp_re),_mm256_set1_epi64x(0xFFFFFFFF00000000));
	__m256i avx2_256_d = _mm256_sub_epi32(_mm256_add_epi32(avx2_256_t1, avx2_256_t2),avx2_256_p);
	__m256i avx2_256_mask = _mm256_srai_epi32(avx2_256_d, 31);
	return _mm256_add_epi32(avx2_256_d, _mm256_and_si256(avx2_256_p, avx2_256_mask));
}
```

注：在较新的CPU上 `_mm256_permutevar8x32_epi32`与 `_mm256_shuffle_epi32`效率基本相同。

## `NTT`函数与 `NTT_autoadj`函数纠正

优化循环次数应为 `logn-3`次，相应的剩余处理循环次数为3次。

```c
static void
mp_NTT_avx2(unsigned logn, uint32_t *restrict a,
			const uint32_t *restrict gm, uint32_t p, uint32_t p0i)
{
	size_t t = (size_t)1 << logn;
	__m256i avx2_256_p = _mm256_set1_epi32(p);
	__m256i avx2_256_p0i = _mm256_set1_epi32(p0i);
	for (unsigned lm = 0; lm < logn - 3; lm++)
	{
		size_t m = (size_t)1 << lm;
		size_t ht = t >> 1;
		size_t v0 = 0;
		for (size_t u = 0; u < m; u++)
		{
			__m256i avx2_256_s = _mm256_set1_epi32(gm[u + m]); // 向量化加载s值
			for (size_t v = 0; v < ht; v += 8)
			{
				size_t k1 = v0 + v;
				size_t k2 = k1 + ht;
				// 加载8个元素的数据块
				__m256i avx2_256_x1 = _mm256_loadu_si256((__m256i *)(a + k1));
				__m256i avx2_256_x2 = _mm256_loadu_si256((__m256i *)(a + k2));
				// Montgomery乘法向量化
				avx2_256_x2 = mp_montymul_x4x2(avx2_256_x2, avx2_256_s, avx2_256_p, avx2_256_p0i);
				// 模加模减存储结果
				_mm256_storeu_si256((__m256i *)(a + k1), mp_add_x8(avx2_256_x1, avx2_256_x2, avx2_256_p));
				_mm256_storeu_si256((__m256i *)(a + k2), mp_sub_x8(avx2_256_x1, avx2_256_x2, avx2_256_p));
			}
			v0 += t;
		}
		t = ht;
	}
	for (unsigned lm = logn - 3; lm < logn; lm++)
	{
		size_t m = (size_t)1 << lm;
		size_t ht = t >> 1;
		size_t v0 = 0;
		for (size_t u = 0; u < m; u++)
		{
			uint32_t s = gm[u + m];
			for (size_t v = 0; v < ht; v++)
			{
				size_t k1 = v0 + v;
				size_t k2 = k1 + ht;
				uint32_t x1 = a[k1];
				uint32_t x2 = mp_montymul(a[k2], s, p, p0i);
				a[k1] = mp_add(x1, x2, p);
				a[k2] = mp_sub(x1, x2, p);
			}
			v0 += t;
		}
		t = ht;
	}
}
```

`mp_NTT_autoadj_avx2` 函数中 `t`初始化为 `logn-1`，且 `lm`循环起始量为 `1`。所以不能直接调用 `NTT`函数，需要内置。

```c
static void
mp_NTT_autoadj_avx2(unsigned logn, uint32_t *restrict a,
					const uint32_t *restrict gm, uint32_t p, uint32_t p0i)
{
	size_t hn = (size_t)1 << (logn - 1);
	__m256i avx2_256_s1 = _mm256_set1_epi32(gm[1]);
	uint32_t s1 = gm[1];
	size_t qn = hn >> 1;
	__m256i avx2_256_p = _mm256_set1_epi32(p);
	__m256i avx2_256_p0i = _mm256_set1_epi32(p0i);
	__m256i indices = _mm256_setr_epi32(7, 6, 5, 4, 3, 2, 1, 0);
	for (size_t u = 1; u < qn - 7; u += 8)
	{
		__m256i avx2_256_x1 = _mm256_loadu_si256((const __m256i *)(a + u));
		// 如果运行时间长可以换成顺序加载再重排反序
		__m256i avx2_256_x2 = _mm256_setr_epi32(a[hn - u], a[hn - u - 1], a[hn - u - 2], a[hn - u - 3], a[hn - u - 4], a[hn - u - 5], a[hn - u - 6], a[hn - u - 7]);
		_mm256_storeu_epi32(&a[u], mp_sub_x8(avx2_256_x1, mp_montymul_x4x2(avx2_256_x2, avx2_256_s1, avx2_256_p, avx2_256_p0i), avx2_256_p));
		_mm256_storeu_epi32(&a[hn - u - 7], _mm256_permutevar8x32_epi32(mp_sub_x8(avx2_256_x2, mp_montymul_x4x2(avx2_256_x1, avx2_256_s1, avx2_256_p, avx2_256_p0i), avx2_256_p), indices));
	}
	for (size_t u = qn - 7; u < qn; u++)
	{
		uint32_t x1 = a[u];
		uint32_t x2 = a[hn - u];
		a[u] = mp_sub(x1, mp_montymul(x2, s1, p, p0i), p);
		a[hn - u] = mp_sub(x2, mp_montymul(x1, s1, p, p0i), p);
	}
	a[qn] = mp_sub(a[qn], mp_montymul(a[qn], s1, p, p0i), p);

	size_t t = (size_t)1 << logn - 1;
	for (unsigned lm = 1; lm < logn - 3; lm++)
	{
		size_t m = (size_t)1 << lm;
		size_t ht = t >> 1;
		size_t v0 = 0;
		for (size_t u = 0; u < m; u++)
		{
			__m256i avx2_256_s = _mm256_set1_epi32(gm[u + m]); // 向量化加载s值
			for (size_t v = 0; v < ht; v += 8)
			{
				size_t k1 = v0 + v;
				size_t k2 = k1 + ht;
				// 加载8个元素的数据块
				__m256i avx2_256_x1 = _mm256_loadu_si256((__m256i *)(a + k1));
				__m256i avx2_256_x2 = _mm256_loadu_si256((__m256i *)(a + k2));
				// Montgomery乘法向量化
				avx2_256_x2 = mp_montymul_x4x2(avx2_256_x2, avx2_256_s, avx2_256_p, avx2_256_p0i);
				// 模加模减存储结果
				_mm256_storeu_si256((__m256i *)(a + k1), mp_add_x8(avx2_256_x1, avx2_256_x2, avx2_256_p));
				_mm256_storeu_si256((__m256i *)(a + k2), mp_sub_x8(avx2_256_x1, avx2_256_x2, avx2_256_p));
			}
			v0 += t;
		}
		t = ht;
	}
	for (unsigned lm = logn - 3; lm < logn; lm++)
	{
		size_t m = (size_t)1 << lm;
		size_t ht = t >> 1;
		size_t v0 = 0;
		for (size_t u = 0; u < m; u++)
		{
			uint32_t s = gm[u + m];
			for (size_t v = 0; v < ht; v++)
			{
				size_t k1 = v0 + v;
				size_t k2 = k1 + ht;
				uint32_t x1 = a[k1];
				uint32_t x2 = mp_montymul(a[k2], s, p, p0i);
				a[k1] = mp_add(x1, x2, p);
				a[k2] = mp_sub(x1, x2, p);
			}
			v0 += t;
		}
		t = ht;
	}
}

```
