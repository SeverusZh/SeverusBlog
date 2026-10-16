---
title: 签名部分优化-ENCODE-01
date: 2025-03-09 17:10:51
tags:
  - AVX2
  - Hawk
---

## 解析 `encode_sig`函数

在完成了GAUSS函数相关优化后，我们来到了签名部分的最后一个优化点——`encode_sig`函数，签名部分其他的函数或者宏几乎都是串行执行的指令且没有经过循环过程，并不适合开展并行化。

接下来我们开始解析 `encode_sig`函数。

```c
static uint32_t
sig_gauss(unsigned logn,
 void (*rng)(void *ctx, void *dst, size_t len), void *rng_context,
 const shake_context *sc_extra, int8_t *x, const uint8_t *t)
{
 const uint16_t *tab_hi;
 const uint64_t *tab_lo;
 size_t hi_len, lo_len;

 switch (logn) {
 case 8:
  tab_hi = sig_gauss_hi_Hawk_256;
  tab_lo = sig_gauss_lo_Hawk_256;
  hi_len = SG_MAX_HI_Hawk_256;
  lo_len = SG_MAX_LO_Hawk_256;
  break;
 case 9:
  tab_hi = sig_gauss_hi_Hawk_512;
  tab_lo = sig_gauss_lo_Hawk_512;
  hi_len = SG_MAX_HI_Hawk_512;
  lo_len = SG_MAX_LO_Hawk_512;
  break;
 default: /* 10 */
  tab_hi = sig_gauss_hi_Hawk_1024;
  tab_lo = sig_gauss_lo_Hawk_1024;
  hi_len = SG_MAX_HI_Hawk_1024;
  lo_len = SG_MAX_LO_Hawk_1024;
  break;
 }

 /*
  * We produce 2*n samples. Each sample requires two elements
  * from the RNG: a low part (64 bits) and a high part (16 bits).
  * A SHAKE instance produces 64-bit words in groups of five
  * (little-endian encoding is assumed); the first four words are
  * the low parts for four samples (lo0, lo1, lo2 and lo3), and the
  * fifth word contains the high parts for the four samples
  * (hi0 + (hi1 << 16) + (hi2 << 32) + (hi3 << 48)).
  *
  * We formally use four parallel SHAKE instances, instantiated
  * over seeds obtained from the source RNG. For j = 0 to 3,
  * instance j produces samples of index 16*i + 4*j + k, with
  * k = 0, 1, 2 or 3. A small, RAM-constrained implementation
  * will use the four instances sequentially, reusing the space
  * for the SHAKE context; a large system with vector instructions
  * (e.g. AVX2) might run the four SHAKE instances at the same time.
  */
 size_t n = (size_t)1 << logn;
 uint8_t seed[41];
 rng(rng_context, seed, 40);

 uint32_t sn = 0;
 for (size_t j = 0; j < 4; j ++) {
  shake_context sc;
  if (sc_extra != NULL) {
   sc = *sc_extra;
  } else {
   shake_init(&sc, 256);
  }
  seed[40] = (uint8_t)j;
  shake_inject(&sc, seed, 41);
  shake_flip(&sc);
  for (size_t u = 0; u < (n << 1); u += 16) {
   union {
    uint8_t b[40];
    uint16_t w[20];
    uint64_t q[5];
   } buf;
   shake_extract(&sc, buf.b, 40);
   for (size_t k = 0; k < 4; k ++) {
    size_t v = u + (j << 2) + k;
    uint64_t lo = dec64le(buf.b + (k << 3));
    uint32_t hi = dec16le(buf.b + 32 + (k << 1));

    /* Extract sign bit. */
    uint32_t neg = -(uint32_t)(lo >> 63);
    lo &= 0x7FFFFFFFFFFFFFFF;
    hi &= 0x7FFF;

    /* Use even or odd column depending on
       parity of t. */
    uint32_t pbit = (t[v >> 3] >> (v & 7)) & 1;
    uint64_t p_odd = -(uint64_t)pbit;
    uint32_t p_oddw = (uint32_t)p_odd;

    uint32_t r = 0;
    for (size_t i = 0; i < hi_len; i += 2) {
     uint64_t tlo0 = tab_lo[i + 0];
     uint64_t tlo1 = tab_lo[i + 1];
     uint64_t tlo = tlo0
      ^ (p_odd & (tlo0 ^ tlo1));
     uint32_t cc =
      (uint32_t)((lo - tlo) >> 63);
     uint32_t thi0 = tab_hi[i + 0];
     uint32_t thi1 = tab_hi[i + 1];
     uint32_t thi = thi0
      ^ (p_oddw & (thi0 ^ thi1));
     r += (hi - thi - cc) >> 31;
    }
    uint32_t hinz = (hi - 1) >> 31;
    for (size_t i = hi_len; i < lo_len; i += 2) {
     uint64_t tlo0 = tab_lo[i + 0];
     uint64_t tlo1 = tab_lo[i + 1];
     uint64_t tlo = tlo0
      ^ (p_odd & (tlo0 ^ tlo1));
     uint32_t cc =
      (uint32_t)((lo - tlo) >> 63);
     r += hinz & cc;
    }

    /* Multiply by 2 and apply parity. */
    r = (r << 1) - p_oddw;

    /* Apply sign bit. */
    r = (r ^ neg) - neg;

    x[v] = (int8_t)*(int32_t *)&r;
    sn += r * r;
   }
  }
 }
 return sn;

}
```

### 逐行解析

1. **参数声明**：

  ```c
  static int encode_sig(unsigned logn, void *sig, size_t sig_len,
      const uint8_t *salt, size_t salt_len, const int16_t *s1)
  ```

  - **功能**：定义函数，接受多项式的对数 `logn`、输出签名缓冲区 `sig`及其长度 `sig_len`、盐值 `salt`及其长度 `salt_len`，以及签名多项式 `s1`。

1. **计算多项式项数**：

  ```c
  size_t n = (size_t)1 << logn;
  ```

  - **含义**：计算多项式的项数 `n`为 `2^logn`。

1. **设置低位位数**：

  ```c
  int low = (logn == 10) ? 6 : 5;//吐槽一下：之前不是怎么样都不愿意用if或者三元表达式吗，怎么现在又用了，是换了个人写吗？
  ```

  - **含义**：根据 `logn`确定编码时低位的位数。若 `logn`为10（1024项），`low`设为6，否则为5。

1. **初始化缓冲区指针**：

  ```c
  uint8_t *buf = (uint8_t *)sig;
  size_t buf_len = sig_len;
  ```

  - **含义**：将输出缓冲区 `sig`转换为 `uint8_t`指针 `buf`，并记录剩余长度 `buf_len`。

1. **检查最小缓冲区大小**：

  ```c
  if (buf_len < salt_len + ((uint32_t)(low + 2) << (logn - 3))) {
      return 0;
  }
  ```

  - **含义**：确保缓冲区足够容纳盐值和固定部分。若不足，返回失败。

1. **复制盐值到缓冲区**：

  ```c
  memcpy(buf, salt, salt_len);
  buf += salt_len;
  buf_len -= salt_len;
  ```

  - **含义**：将盐值复制到缓冲区，调整指针和剩余长度。

1. **编码符号位**：

  ```c
  for (size_t u = 0; u < n; u += 8) {
      unsigned x = 0;
      for (size_t v = 0; v < 8; v ++) {
          x |= (*(const uint16_t *)(s1 + u + v) >> 15) << v;
      }
      buf[u >> 3] = x;
  }
  ```

  - **含义**：提取 `s1`数组中每个元素的符号位（最高位），每8个符号位组合成一个字节，存入缓冲区。

1. **调整缓冲区指针**：

  ```c
  buf += (n >> 3);
  buf_len -= (n >> 3);
  ```

  - **含义**：跳过符号部分，更新剩余长度。

1. **处理固定大小的低位部分**：

  ```c
  uint32_t low_mask = ((uint32_t)1 << low) - 1;
  for (size_t u = 0; u < n; u += 8) {
      uint64_t x = 0;
      for (size_t v = 0, vv = 0; v < 8; v ++, vv += low) {
          uint32_t w = (uint32_t)s1[u + v];
          w ^= tbmask(w);
          x |= (uint64_t)(w & low_mask) << vv;
      }
      for (int i = 0; i < (low << 3); i += 8) {
          *buf ++ = (uint8_t)(x >> i);
      }
  }
  ```

  - **含义**：将每个元素的低 `low`位（绝对值）打包成字节。`tbmask`用于处理符号，将负数转换为正数，`low_mask`提取低位。

1. **更新剩余缓冲区长度**：

  ```c
  buf_len -= (size_t)low << (logn - 3);
  ```

1. **处理可变长度的高位部分**：

  ```c
  uint32_t acc = 0;
  int acc_len = 0;
  for (size_t u = 0; u < n; u ++) {
      uint32_t w = (uint32_t)s1[u];
      int k = (int)((w ^ tbmask(w)) >> low);
      acc |= (uint32_t)1 << (acc_len + k);
      acc_len += 1 + k;
      while (acc_len >= 8) {
          *buf++ = (uint8_t)acc;
          buf_len--;
          acc >>= 8;
          acc_len -= 8;
      }
  }
  ```

  - **含义**：将高位部分编码为一元码，累积到 `acc`中，每满8位写入一个字节。

1. **处理剩余的位**：

  ```c
  if (acc_len > 0) {
      *buf++ = (uint8_t)acc;
      buf_len--;
  }
  ```

1. **填充剩余缓冲区**：

  ```c
  memset(buf, 0, buf_len);
  ```

### **变量列表及含义**

| **变量名** | **类型** | **含义** |
| --- | --- | --- |
| `logn` | `unsigned` | 多项式的对数次数，n=2^logn。 |
| `sig` | `void*` | 输出签名的缓冲区指针。 |
| `sig_len` | `size_t` | 输出缓冲区的总长度。 |
| `salt` | `const uint8_t*` | 盐值的指针。 |
| `salt_len` | `size_t` | 盐值的长度。 |
| `s1` | `const int16_t*` | 待编码的签名多项式系数数组。 |
| `n` | `size_t` | 多项式的项数，等于2^logn。 |
| `low` | `int` | 编码时低位的位数，logn=10时为6，否则为5。 |
| `buf` | `uint8_t*` | 当前写入位置的指针，指向输出缓冲区。 |
| `buf_len` | `size_t` | 输出缓冲区剩余可用长度。 |
| `low_mask` | `uint32_t` | 低位掩码，用于提取每个系数的低 `low`位，如0x1F或0x3F。 |
| `u`, `v`, `vv` | `size_t` | 循环变量，用于遍历多项式的系数和位操作。 |
| `x` | `uint64_t` | 临时变量，用于存储固定部分打包后的位数据。 |
| `i` | `int` | 循环变量，处理字节内的位偏移。 |
| `acc` | `uint32_t` | 累积变量，用于存储可变长度编码的位流。 |
| `acc_len` | `int` | 当前累积的位数。 |
| `k` | `int` | 当前元素的高位部分的位数，用于生成一元码。 |
| `w` | `uint32_t` | 临时变量，存储当前处理的 `s1`元素的值（转换为无符号）。 |
| `tbmask` | 宏或函数 | 处理符号位的函数，将负数转换为正数（如符号位扩展后异或）。 |
