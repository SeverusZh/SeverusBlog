---
title: 验签部分优化-iFTT
date: 2025-04-08 02:34:28
tags:
  - AVX2
  - Hawk
---

原理和FTT一样，只是算法顺序逆置，稍微注意一下处理顺序和第二个旋转因子要取负数即可。

```c
static void
fx32_iFFT(unsigned logn, uint32_t *a)
{
	size_t hn = (size_t)1 << (logn - 1);
	size_t ht = 1;
	for (unsigned lm = logn - 1; lm >= logn - 2; lm--)
	{
		size_t m = (size_t)1 << lm;
		size_t t = ht << 1;
		size_t j0 = 0;
		size_t hm = m >> 1;
		for (size_t i = 0; i < hm; i++)
		{
			uint32_t s_re = (uint32_t)FX32_GM[((i + m) << 1) + 0];
			uint32_t s_im = -(uint32_t)FX32_GM[((i + m) << 1) + 1];
			for (size_t j = j0; j < j0 + ht; j++)
			{
				uint32_t x1_re = a[j];
				uint32_t x1_im = a[j + hn];
				uint32_t x2_re = a[j + ht];
				uint32_t x2_im = a[j + ht + hn];

#define M(c, d) ((uint64_t)((int64_t)*(int32_t *)&(c) * (int64_t)*(int32_t *)&(d)))
#define H(c) ((uint32_t)(*(int32_t *)&(c) >> 1))
				/*
				 * t1 <- x1 + x2
				 * t2 <- s*(x1 - x2)
				 * (x1, x2) <- (t1/2, t2/2)
				 */
				uint32_t t1_re = x1_re + x2_re;
				uint32_t t1_im = x1_im + x2_im;
				uint32_t t2_re = x1_re - x2_re;
				uint32_t t2_im = x1_im - x2_im;

				a[j] = H(t1_re);
				a[j + hn] = H(t1_im);
				a[j + ht] = (M(t2_re, s_re) - M(t2_im, s_im)) >> 32;
				a[j + ht + hn] = (M(t2_re, s_im) + M(t2_im, s_re)) >> 32;
#undef M
#undef H
			}
			j0 += t;
		}
		ht = t;
	}
	for (unsigned lm = logn - 3; lm > 0; lm--)
	{
		size_t m = (size_t)1 << lm;
		size_t t = ht << 1;
		size_t j0 = 0;
		size_t hm = m >> 1;
		for (size_t i = 0; i < hm; i++)
		{
			uint32_t s_re = (uint32_t)FX32_GM[((i + m) << 1) + 0];
			uint32_t s_im = -(uint32_t)FX32_GM[((i + m) << 1) + 1];
			__m256i avx2_256_s_re = _mm256_set1_epi64x((int64_t)*(int32_t *)&s_re);
			__m256i avx2_256_s_im = _mm256_set1_epi64x((int64_t)*(int32_t *)&s_im);
			for (size_t j = j0; j < j0 + ht; j += 4)
			{
				__m256i avx2_256_x1_re = load_4x32bits_sign_extend(a + j);
				__m256i avx2_256_x1_im = load_4x32bits_sign_extend(a + j + hn);
				__m256i avx2_256_x2_re = load_4x32bits_sign_extend(a + j + ht);
				__m256i avx2_256_x2_im = load_4x32bits_sign_extend(a + j + ht + hn);

				__m256i avx2_256_t1_re = _mm256_add_epi64(avx2_256_x1_re, avx2_256_x2_re);
				__m256i avx2_256_t1_im = _mm256_add_epi64(avx2_256_x1_im, avx2_256_x2_im);
				__m256i avx2_256_t2_re = _mm256_sub_epi64(avx2_256_x1_re, avx2_256_x2_re);
				__m256i avx2_256_t2_im = _mm256_sub_epi64(avx2_256_x1_im, avx2_256_x2_im);

				__m256i avx2_256_t_re = _mm256_sub_epi64(_mm256_mul_epi32(avx2_256_t2_re, avx2_256_s_re), _mm256_mul_epi32(avx2_256_t2_im, avx2_256_s_im));
				__m256i avx2_256_t_im = _mm256_add_epi64(_mm256_mul_epi32(avx2_256_t2_re, avx2_256_s_im), _mm256_mul_epi32(avx2_256_t2_im, avx2_256_s_re));
				_mm_store_si128((__m128i *)(a + j), extract_low32_from_256(_mm256_srli_epi64(avx2_256_t1_re, 1)));
				_mm_store_si128((__m128i *)(a + j + hn), extract_low32_from_256(_mm256_srli_epi64(avx2_256_t1_im, 1)));
				_mm_store_si128((__m128i *)(a + j + ht), extract_high32_from_256(avx2_256_t_re));
				_mm_store_si128((__m128i *)(a + j + ht + hn), extract_high32_from_256(avx2_256_t_im));
			}
			j0 += t;
		}
		ht = t;
	}
}
```
