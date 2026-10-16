---
title: 签名部分优化-GAUSS-01
date: 2025-02-27 19:08:08
updated: 2025-03-03
tags:
  - AVX2
  - Hawk
---

## 低字节提取

这个文件中也有 `extract_lowbit` 函数，我们按照之前的优化函数将其覆盖

```c

static void
extract_lowbit(unsigned logn, uint8_t *restrict f2, const int8_t *restrict f)
{
    size_t n = (size_t)1 << logn;
    const uint8_t *fu = (const uint8_t *)f;
    size_t u = 0;

    /* AVX2 批量处理 (每次处理32字节 -> 生成4字节) */
    const __m256i mask = _mm256_set1_epi8(0x01);
    for (; u + 32 <= n; u += 32) {
        __m256i data = _mm256_loadu_si256((const __m256i*)(fu + u));
        __m256i bits = _mm256_and_si256(data, mask);
        uint32_t mask32 = _mm256_movemask_epi8(bits);

        /* 将32位的mask32拆分为4个字节 */
        f2[u >> 3] = (uint8_t)(mask32 & 0xFF);
        f2[(u >> 3) + 1] = (uint8_t)((mask32 >> 8) & 0xFF);
        f2[(u >> 3) + 2] = (uint8_t)((mask32 >> 16) & 0xFF);
        f2[(u >> 3) + 3] = (uint8_t)(mask32 >> 24);
    }

    /* 处理剩余不足32字节的部分 */
    for (; u < n; u += 8) {
        f2[u >> 3] = (fu[u + 0] & 1u)
            | ((fu[u + 1] & 1u) << 1)
            | ((fu[u + 2] & 1u) << 2)
            | ((fu[u + 3] & 1u) << 3)
            | ((fu[u + 4] & 1u) << 4)
            | ((fu[u + 5] & 1u) << 5)
            | ((fu[u + 6] & 1u) << 6)
            | ((fu[u + 7] & 1u) << 7);
    }
}
```

## 高斯分布

经过分析源代码和阅读代码中留下的注释，我们发现 `sig_gauss` 函数也是可以被优化的。

### 源代码原理

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

```

大致分析，该函数用于生成符合高斯分布的整数数组 `x`，并根据奇偶校验位 `t` 调整分布。其核心步骤如下：

1. **初始化参数**：根据 `logn` 选择预定义的查找表 `tab_hi` 和 `tab_lo`。
2. **随机数生成**：使用 SHAKE 实例或外部 RNG 生成随机数，提取低 64 位 (`lo`) 和高 16 位 (`hi`)。
3. **符号与奇偶处理**：根据 `lo` 的最高位确定符号，根据 `t` 的奇偶性选择查表列。
4. **查表与累加**：遍历查找表，计算样本值 `r`，并累加平方和 `sn`。
5. **结果调整**：应用符号和奇偶调整，存储到 `x` 数组。

### 优化方案设计

该函数最大的优化点应该在于通过 AVX2 向量化，可同时处理四个样本，显著减少循环次数。

首先，考虑sig_gauss中的主循环结构。每个j对应一个SHAKE实例，处理u的块。每个块生成40字节的buf，然后处理四个k的样本。每个样本的lo和hi来自不同的位置。例如，在sig_gauss中，每次处理四个样本（k循环），每个样本需要处理lo和hi。

在AVX2优化中，可能希望同时处理四个样本的数据。例如，将四个样本的lo和hi分别加载到向量寄存器中，然后并行处理它们的计算过程。

例如，处理四个样本的lo值可以组成一个256位的向量（四个64位整数），hi值可以是四个16位的整数，可能需要扩展到32位或64位以适应向量寄存器。不过AVX2对64位整数的操作支持有限，可能需要更多的技巧。

另一个可能的优化点是查表部分。在循环中，对于每个i，从tab_lo和tab_hi中取出两个值，根据p_odd选择tlo0或tlo1，thi0或thi1。这部分可以转换为向量化的选择操作。例如，使用向量比较和混合指令来同时处理多个i值的条件选择。

不过，循环中的hi_len和lo_len可能较大，如果这些表是预先确定的，可以考虑将它们的结构重组为向量友好的形式，或者将循环展开，使得多个i的迭代可以并行处理。

此外，在计算r的累加时，原代码使用标量变量，可能需要转换为向量累加器，每个向量通道对应一个样本的r值。这样，在每次循环迭代中，可以同时更新四个样本的r值。

可能的优化步骤：

1. **向量化SHAKE实例的处理**：如果四个SHAKE实例可以并行执行，那么可以使用AVX2来加速SHAKE的内部处理，例如同时计算四个不同的块。但SHAKE的内部结构可能不容易向量化，这需要具体分析。例如，SHAKE使用的是Keccak算法，其内部状态是1600位，可能难以向量化。但原注释提到，四个实例可以并行处理，例如通过四个独立的上下文，在AVX2中可能用向量寄存器的不同通道处理不同的上下文。这可能需要手动展开循环，将四个SHAKE的状态存储在向量化的结构中，并使用AVX2指令同时处理四个不同的数据块。这可能比较复杂，但或许可行。
2. **向量化样本处理**：在处理每个u块中的四个k样本时，可以将四个样本的数据（如lo、hi、pbit等）打包到AVX2向量中，并行处理。例如，同时处理四个样本的查表、条件判断、符号应用等操作。这需要将标量操作转换为向量操作，并处理数据依赖。

例如，在计算r时，四个样本的r可以分别存储在向量的四个通道中，每个通道对应一个样本的累加。这样，循环中的查表操作可以向量化，同时对四个样本的数据进行处理。

1. **处理奇偶位和符号位**：每个样本的pbit和符号位可以通过位操作转换为向量掩码，然后用向量逻辑指令进行处理。例如，计算p_odd向量，然后用向量异或和与操作来选择表中的值。
2. **查表的向量化**：查表操作可能比较困难，因为每个样本的i循环需要访问不同的表项。但或许可以将表的数据结构重新排列，以便使用向量加载指令一次加载多个表项，然后用向量比较和混合指令来选择合适的值。

例如，假设tab_lo中的每个i对应两个元素tlo0和tlo1，可以将这些元素预先存储为向量的形式，使得每次加载可以处理多个i的条目。例如，将tab_lo组织成两个数组，一个存储tlo0，另一个存储tlo1，然后用向量加载指令同时获取多个i的tlo0和tlo1，再根据p_odd向量选择对应的元素。

1. **条件计算的向量化**：在计算条件（如(lo - tlo) >>63）时，可以使用向量比较指令生成掩码，然后转换为相应的条件结果。例如，AVX2的vpcmpgtq可以比较两个64位整数向量，生成掩码，然后转换为相应的位。
2. **累加的向量化**：在计算r的累加时，可以将每个样本的r值保存在一个向量寄存器中，每次循环迭代更新这四个值。例如，将四个r值存储在\_\_m256i变量中，每次处理多个i条目，将结果向量加到累加器中。

由上面的分析可以得知，这一过程还需要学习一些知识，今天暂时无法开展具体的优化工作。
