---
title: 验签部分优化-VERIFY-03
date: 2025-04-08 02:34:59
tags:
  - AVX2
  - Hawk
---

## VERIFY剩余部分优化

这是三个主体部分最后剩余的部分了，完成这一部分可以说基本的优化已经完成了。而剩下的部分中也有一部分是串行计算的，其余的其实只要将对应函数换成AVX2版本，调整一下逻辑结构即可。

```c
for (int i = 0; i < 2; i++)
	{
		uint32_t p = (i == 0) ? P1 : P2;
		uint32_t p0i = (i == 0) ? P1_0i : P2_0i;
		uint32_t R3 = (i == 0) ? P1_R3 : P2_R3;
		uint32_t m16 = (i == 0) ? P1_m16 : P2_m16;
		const uint32_t *gm = (i == 0) ? GM_p1 : GM_p2;

		/* c2 <- t1 */
		if (sig_len == (size_t)-1)
		{
			memcpy(c2hi, s1, n * sizeof(int16_t));
		}
		else
		{
			(void)decode_s1(logn, c2hi, s1buf, s1buf_len);
		}
		make_t1(logn, c2hi, h + (n >> 3));
		mp_poly_to_NTT(logn, c2, c2hi, p, p0i, gm);

		/* c1 <- q00 (auto-adjoint) */
		if (pub_len != (size_t)-1)
		{
			q00 = c1hi;
			(void)decode_q00(logn, q00, q00buf, q00buf_len);
		}
		mp_poly_to_NTT_autoadj(logn, c1, q00, p, p0i, gm);

		/*
		 * c1 <- 1/c1
		 * We use Montgomery's trick to invert the n/2 values.
		 * For any x and y:
		 *   1/x = y*(1/(x*y))
		 *   1/y = x*(1/(x*y))
		 * Applied recursively, this allows inverting m values at
		 * the cost of a single true inversion, and 3*(m-1)
		 * much cheaper multiplications.
		 *
		 * This requires some temporary storage, but the upper
		 * half of c1[] is free at this point.
		 */
		uint32_t bx = c1[0];
		c1[hn] = bx;
		for (size_t u = 1; u < hn; u++)
		{
			bx = mp_montymul(bx, c1[u], p, p0i);
			c1[u + hn] = bx;
		}
		bx = mp_div(1, bx, p, p0i, m16);
		for (size_t u = hn - 1; u > 0; u--)
		{
			uint32_t ix = mp_montymul(bx, c1[u + hn - 1], p, p0i);
			bx = mp_montymul(bx, c1[u], p, p0i);
			c1[u] = ix;
		}
		c1[0] = bx;

		/* c2 <- c2*c1 = t1/q00
		   nnacc = Tr_p(t1*adj(t1)/q00) */
		uint32_t nnacc = 0;
		for (size_t u = 0; u < hn; u++)
		{
			uint32_t x1 = c2[u];
			uint32_t x2 = c2[(n - 1) - u];
			uint32_t qx = c1[u];
			x1 = mp_montymul(x1, qx, p, p0i);
			nnacc = mp_add(nnacc, mp_montymul(x1, x2, p, p0i), p);
			x2 = mp_montymul(x2, qx, p, p0i);
			c2[u] = x1;
			c2[(n - 1) - u] = x2;
		}
		/* nnacc is in double-anti-Montgomery representation
		   (i.e. divided by R = 2^64) */

		/* c1 <- q01 */
		if (pub_len != (size_t)-1)
		{
			q01 = c1hi;
			(void)decode_q01(logn, q01, q01buf, q01buf_len);
		}
		mp_poly_to_NTT(logn, c1, q01, p, p0i, gm);

		/* c1 <- c1*c2 = q01*t1/q00 */
		for (size_t u = 0; u < n; u++)
		{
			c1[u] = mp_montymul(
				mp_montymul(c1[u], c2[u], p, p0i), R3, p, p0i);
		}

		/* c2 <- t0 */
		mp_poly_to_NTT(logn, c2, t0, p, p0i, gm);

		/* c2 <- c2 + c1 = t0 + q01*t1/q00 = e */
		for (size_t u = 0; u < n; u++)
		{
			c2[u] = mp_add(c2[u], c1[u], p);
		}

		/* c1 <- q00 (auto-adjoint) */
		if (pub_len != (size_t)-1)
		{
			q00 = c1hi;
			(void)decode_q00(logn, q00, q00buf, q00buf_len);
		}
		mp_poly_to_NTT_autoadj(logn, c1, q00, p, p0i, gm);

		/* nnacc <- nnacc + Tr_p(c1*c2*adj(c2) = q00*e*adj(e)) */
		for (size_t u = 0; u < hn; u++)
		{
			uint32_t x1 = c2[u];
			uint32_t x2 = c2[(n - 1) - u];
			uint32_t qx = c1[u];
			nnacc = mp_add(nnacc, mp_montymul(qx, mp_montymul(x1, x2, p, p0i), p, p0i), p);
		}

		/* nnacc is in double-anti-Montgomery representation;
		   convert it to normal representation */
		nnacc = mp_montymul(nnacc, R3, p, p0i);

		if (ss != NULL)
		{
			memcpy((uint8_t *)ss + 4 * n + 4 * i, &nnacc, 4);
		}

#if HAWK_DEBUG
		printf("# Qnorm(t)^2 mod %lu\n", (unsigned long)p);
		printf("qnt = %lu\n", (unsigned long)nnacc);
#endif

		if (i == 0)
		{
			tnorm = nnacc;
		}
		else
		{
			if (tnorm != nnacc)
			{
				/* Not the same value modulo p1 and p2;
				   thus, the value is greater than p2,
				   hence too large. */
				return 0;
			}
		}
	}
```

```c
for (int i = 0; i < 2; i++)
	{
		uint32_t p = (i == 0) ? P1 : P2;
		uint32_t p0i = (i == 0) ? P1_0i : P2_0i;
		uint32_t R3 = (i == 0) ? P1_R3 : P2_R3;
		uint32_t m16 = (i == 0) ? P1_m16 : P2_m16;
		const uint32_t *gm = (i == 0) ? GM_p1 : GM_p2;

		/* c2 <- t1 */
		if (sig_len == (size_t)-1)
		{
			memcpy(c2hi, s1, n * sizeof(int16_t));
		}
		else
		{
			(void)decode_s1(logn, c2hi, s1buf, s1buf_len);
		}
		make_t1(logn, c2hi, h + (n >> 3));
		mp_poly_to_NTT_avx2(logn, c2, c2hi, p, p0i, gm);

		/* c1 <- q00 (auto-adjoint) */
		if (pub_len != (size_t)-1)
		{
			q00 = c1hi;
			(void)decode_q00(logn, q00, q00buf, q00buf_len);
		}
		mp_poly_to_NTT_autoadj_avx2(logn, c1, q00, p, p0i, gm);

		/*
		 * c1 <- 1/c1
		 * We use Montgomery's trick to invert the n/2 values.
		 * For any x and y:
		 *   1/x = y*(1/(x*y))
		 *   1/y = x*(1/(x*y))
		 * Applied recursively, this allows inverting m values at
		 * the cost of a single true inversion, and 3*(m-1)
		 * much cheaper multiplications.
		 *
		 * This requires some temporary storage, but the upper
		 * half of c1[] is free at this point.
		 */
		uint32_t bx = c1[0];
		c1[hn] = bx;
		__m256i avx2_256_p = _mm256_set1_epi32(p);
		__m256i avx2_256_p0i = _mm256_set1_epi32(p0i);
		__m256i avx2_256_R3 = _mm256_set1_epi32(R3);
		for (size_t u = 1; u < hn; u++)
		{
			bx = mp_montymul(bx, c1[u], p, p0i); // 串行计算，无法优化
			c1[u + hn] = bx;
		}
		bx = mp_div(1, bx, p, p0i, m16);
		for (size_t u = hn - 1; u > 0; u--)
		{
			uint32_t ix = mp_montymul(bx, c1[u + hn - 1], p, p0i);
			bx = mp_montymul(bx, c1[u], p, p0i);
			c1[u] = ix;
		}
		c1[0] = bx;

		/* c2 <- c2*c1 = t1/q00
		   nnacc = Tr_p(t1*adj(t1)/q00) */
		uint32_t nnacc = 0;
		for (size_t u = 0; u < hn; u += 8)
		{
			/*
			uint32_t x1 = c2[u];
			uint32_t x2 = c2[(n - 1) - u];
			uint32_t qx = c1[u];
			*/

			__m256i avx2_256_x2 = _mm256_setr_epi32(c2[(n - 1) - u], c2[(n - 1) - u - 1], c2[(n - 1) - u - 2], c2[(n - 1) - u - 3], c2[(n - 1) - u - 4], c2[(n - 1) - u - 5], c2[(n - 1) - u - 6], c2[(n - 1) - u - 7]);
			__m256i avx2_256_x1 = _mm256_loadu_si256((__m256i *)&c2[u]);
			__m256i avx2_256_qx = _mm256_loadu_si256((__m256i *)&c1[u]);

			/*
			x1 = mp_montymul(x1, qx, p, p0i);
			nnacc = mp_add(nnacc, mp_montymul(x1, x2, p, p0i), p);
			x2 = mp_montymul(x2, qx, p, p0i);
			*/

			avx2_256_x1 = mp_montymul_x4x2(avx2_256_x1, avx2_256_qx, avx2_256_p, avx2_256_p0i);
			__m256i avx2_256_tmp = mp_montymul_x4x2(avx2_256_x1, avx2_256_x2, avx2_256_p, avx2_256_p0i);
			uint32_t *local_tmp = (uint32_t *)&avx2_256_tmp;
			for (size_t z = 0; z < 8; z++)
			{
				nnacc = mp_add(nnacc, local_tmp[z], p);
			}
			avx2_256_x2 = mp_montymul_x4x2(avx2_256_x2, avx2_256_qx, avx2_256_p, avx2_256_p0i);

			/*
			c2[u] = x1;
			c2[(n - 1) - u] = x2;
			*/
			_mm256_storeu_si256((__m256i *)&c2[u], avx2_256_x1);
			_mm256_storeu_si256((__m256i *)&c2[n - u - 8], _mm256_permutevar8x32_epi32(avx2_256_x2, _mm256_setr_epi32(7, 6, 5, 4, 3, 2, 1, 0)));
		}
		/* nnacc is in double-anti-Montgomery representation
		   (i.e. divided by R = 2^64) */

		/* c1 <- q01 */
		if (pub_len != (size_t)-1)
		{
			q01 = c1hi;
			(void)decode_q01(logn, q01, q01buf, q01buf_len);
		}
		mp_poly_to_NTT_avx2(logn, c1, q01, p, p0i, gm);

		/* c1 <- c1*c2 = q01*t1/q00 */
		for (size_t u = 0; u < n; u += 8)
		{
			__m256i avx2_256_c1 = _mm256_loadu_si256((__m256i *)&c1[u]);
			__m256i avx2_256_c2 = _mm256_loadu_si256((__m256i *)&c2[u]);
			avx2_256_c1 = mp_montymul_x4x2(mp_montymul_x4x2(avx2_256_c1, avx2_256_c2, avx2_256_p, avx2_256_p0i), avx2_256_R3, avx2_256_p, avx2_256_p0i);
			_mm256_storeu_si256((__m256i *)&c1[u], avx2_256_c1);
			/*
			c1[u] = mp_montymul(
				mp_montymul(c1[u], c2[u], p, p0i), R3, p, p0i);
				*/
		}

		/* c2 <- t0 */
		mp_poly_to_NTT_avx2(logn, c2, t0, p, p0i, gm);

		/* c2 <- c2 + c1 = t0 + q01*t1/q00 = e */
		for (size_t u = 0; u < n; u += 8)
		{
			__m256i avx2_256_c1 = _mm256_loadu_si256((__m256i *)&c1[u]);
			__m256i avx2_256_c2 = _mm256_loadu_si256((__m256i *)&c2[u]);
			avx2_256_c2 = mp_add_x8(avx2_256_c2, avx2_256_c1, avx2_256_p);
			_mm256_storeu_si256((__m256i *)&c2[u], avx2_256_c2);
			// c2[u] = mp_add(c2[u], c1[u], p);
		}

		/* c1 <- q00 (auto-adjoint) */
		if (pub_len != (size_t)-1)
		{
			q00 = c1hi;
			(void)decode_q00(logn, q00, q00buf, q00buf_len);
		}
		mp_poly_to_NTT_autoadj_avx2(logn, c1, q00, p, p0i, gm);

		/* nnacc <- nnacc + Tr_p(c1*c2*adj(c2) = q00*e*adj(e)) */
		for (size_t u = 0; u < hn; u += 8)
		{
			/*
			uint32_t x1 = c2[u];
			uint32_t x2 = c2[(n - 1) - u];
			uint32_t qx = c1[u];
			*/
			__m256i avx2_256_x2 = _mm256_setr_epi32(c2[(n - 1) - u], c2[(n - 1) - u - 1], c2[(n - 1) - u - 2], c2[(n - 1) - u - 3], c2[(n - 1) - u - 4], c2[(n - 1) - u - 5], c2[(n - 1) - u - 6], c2[(n - 1) - u - 7]);
			__m256i avx2_256_x1 = _mm256_loadu_si256((__m256i *)&c2[u]);
			__m256i avx2_256_qx = _mm256_loadu_si256((__m256i *)&c1[u]);
			// nnacc = mp_add(nnacc, mp_montymul(qx, mp_montymul(x1, x2, p, p0i), p, p0i), p);
			__m256i avx2_256_tmp = mp_montymul_x4x2(avx2_256_x1, avx2_256_x2, avx2_256_p, avx2_256_p0i);
			avx2_256_tmp = mp_montymul_x4x2(avx2_256_qx, avx2_256_tmp, avx2_256_p, avx2_256_p0i);
			uint32_t *tmp = (uint32_t *)&avx2_256_tmp;
			for (size_t z = 0; z < 8; z++)
			{
				nnacc = mp_add(nnacc, tmp[z], p);
			}
		}

		/* nnacc is in double-anti-Montgomery representation;
		   convert it to normal representation */
		nnacc = mp_montymul(nnacc, R3, p, p0i);

		if (ss != NULL)
		{
			memcpy((uint8_t *)ss + 4 * n + 4 * i, &nnacc, 4);
		}

#if HAWK_DEBUG
		printf("# Qnorm(t)^2 mod %lu\n", (unsigned long)p);
		printf("qnt = %lu\n", (unsigned long)nnacc);
#endif

		if (i == 0)
		{
			tnorm = nnacc;
		}
		else
		{
			if (tnorm != nnacc)
			{
				/* Not the same value modulo p1 and p2;
				   thus, the value is greater than p2,
				   hence too large. */
				return 0;
			}
		}
	}
```

> **非常非常**值得注意的是，在循环中使用 `_mm256_loadu_si256` 函数和 `_mm256_storeu_si256` 函数时，**一定**要采用类如 `(__m256i *)&c1[u]` 的传参形式，如果采用 `(__m256i *)c1 + u` 的形式，编译器极有可能在编译过程中错判地址，从而导致地址错读，函数功能失效，而且这一错误**不会被编译器发现并提醒**，甚至你对这一行下不下断点都会影响地址是否错读，调试也不一定能发现该错误。因此一定要采用推荐的传参形式。如果你不在循环中使用而只调用一次，不会产生此类错误，但为避免出错仍建议采用该形式。

接下来我将转入辅助函数的优化或测试环节。
