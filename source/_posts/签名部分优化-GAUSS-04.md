---
title: 签名部分优化-GAUSS-04
date: 2025-02-27 19:08:20
updated: 2025-03-03
tags:
  - AVX2
  - Hawk
---

字数：5710，阅读时间：29分钟

# GAUSS函数具体优化

## 采样前处理

经过前三次分析，我们不难发现，由于算法内部比较难以优化，事实上目前最可行的方案就是并行化四个SHAKE实例的处理，这也是开发者留下的天然的用于AVX2优化的部分。

因此，下面这段我们暂且全部保留。

```c
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
size_t n = (size_t)1 << logn;
uint8_t seed[41];
rng(rng_context, seed, 40);
```

接下来，首先把高斯分布表展开成AVX2向量（这是当时尝试的方案，后面没有用到）：

```c
 __m256i avx2_256_tab_hi[hi_len];
__m256i avx2_256_tab_low[lo_len];
for (size_t i = 0; i < hi_len; i ++) {
 avx2_256_tab_hi[i] = _mm256_set1_epi64x(tab_hi[i]);
}
for (size_t i = 0; i < lo_len; i ++) {
 avx2_256_tab_low[i] = _mm256_set1_epi64x(tab_lo[i]);
}
```

`mm256_set1_epi64x` 是 Intel AVX 指令集中的一个内联函数，其核心作用是将一个 64 位有符号整数（`long long` 或 `__int64` 类型）重复填充到 256 位 SIMD 向量寄存器（`__m256i` 类型）的所有 64 位元素中。

此处需要说明一下hi\_len和lo\_len变量，事实上，二者是由这一段代码定义的：

```c
static const uint16_t sig_gauss_hi_Hawk_256[] = {
 0x4D70, 0x268B,
 0x0F80, 0x04FA,
 0x0144, 0x0041,
 0x000A, 0x0001
};
#define SG_MAX_HI_Hawk_256  ((sizeof sig_gauss_hi_Hawk_256) / sizeof(uint16_t))

static const uint64_t sig_gauss_lo_Hawk_256[] = {
 0x71FBD58485D45050, 0x1408A4B181C718B1,
 0x54114F1DC2FA7AC9, 0x614569CC54722DC9,
 0x42F74ADDA0B5AE61, 0x151C5CDCBAFF49A3,
 0x252E2152AB5D758B, 0x23460C30AC398322,
 0x0FDE62196C1718FC, 0x01355A8330C44097,
 0x00127325DDF8CEBA, 0x0000DC8DE401FD12,
 0x000008100822C548, 0x0000003B0FFB28F0,
 0x0000000152A6E9AE, 0x0000000005EFCD99,
 0x000000000014DA4A, 0x0000000000003953,
 0x000000000000007B, 0x0000000000000000
};
#define SG_MAX_LO_Hawk_256  ((sizeof sig_gauss_lo_Hawk_256) / sizeof(uint64_t))

static const uint16_t sig_gauss_hi_Hawk_512[] = {
 0x580B, 0x35F9,
 0x1D34, 0x0DD7,
 0x05B7, 0x020C,
 0x00A2, 0x002B,
 0x000A, 0x0001
};
#define SG_MAX_HI_Hawk_512  ((sizeof sig_gauss_hi_Hawk_512) / sizeof(uint16_t))

static const uint64_t sig_gauss_lo_Hawk_512[] = {
 0x0C27920A04F8F267, 0x3C689D9213449DC9,
 0x1C4FF17C204AA058, 0x7B908C81FCE3524F,
 0x5E63263BE0098FFD, 0x4EBEFD8FF4F07378,
 0x56AEDFB0876A3BD8, 0x4628BC6B23887196,
 0x061E21D588CC61CC, 0x7F769211F07B326F,
 0x2BA568D92EEC18E7, 0x0668F461693DFF8F,
 0x00CF0F8687D3B009, 0x001670DB65964485,
 0x000216A0C344EB45, 0x00002AB6E11C2552,
 0x000002EDF0B98A84, 0x0000002C253C7E81,
 0x000000023AF3B2E7, 0x0000000018C14ABF,
 0x0000000000EBCC6A, 0x000000000007876E,
 0x00000000000034CF, 0x000000000000013D,
 0x0000000000000006, 0x0000000000000000
};
#define SG_MAX_LO_Hawk_512  ((sizeof sig_gauss_lo_Hawk_512) / sizeof(uint64_t))

static const uint16_t sig_gauss_hi_Hawk_1024[] = {
 0x58B0, 0x36FE,
 0x1E3A, 0x0EA0,
 0x0632, 0x024A,
 0x00BC, 0x0034,
 0x000C, 0x0002
};
#define SG_MAX_HI_Hawk_1024 ((sizeof sig_gauss_hi_Hawk_1024) / sizeof(uint16_t))

static const uint64_t sig_gauss_lo_Hawk_1024[] = {
 0x3AAA2EB76504E560, 0x01AE2B17728DF2DE,
 0x70E1C03E49BB683E, 0x6A00B82C69624C93,
 0x55CDA662EF2D1C48, 0x2685DB30348656A4,
 0x31E874B355421BB7, 0x430192770E205503,
 0x57C0676C029895A7, 0x5353BD4091AA96DB,
 0x3D4D67696E51F820, 0x09915A53D8667BEE,
 0x014A1A8A93F20738, 0x0026670030160D5F,
 0x0003DAF47E8DFB21, 0x0000557CD1C5F797,
 0x000006634617B3FF, 0x0000006965E15B13,
 0x00000005DBEFB646, 0x0000000047E9AB38,
 0x0000000002F93038, 0x00000000001B2445,
 0x000000000000D5A7, 0x00000000000005AA,
 0x0000000000000021, 0x0000000000000000
};
#define SG_MAX_LO_Hawk_1024 ((sizeof sig_gauss_lo_Hawk_1024) / sizeof(uint64_t))
```

其实这里的define写的挺莫名奇妙的，因为无论是256还是512或是1024的 `SG_MAX_LO`和 `SG_MAX_HI`都是一个固定的常数，也就是20/26/26和8/10/10，暂不清楚为什么要采取这样的除法定义，或许是当时写的时候为了方便泛用？

接下来，我们初始化四个SHAKE上下文。

```c
shake_context sc[4];
 for (int i = 0; i < 4; i ++) {
  if (sc_extra != NULL) {
   sc[i] = *sc_extra;
  } else {
   shake_init(&sc[i], 256);
  }
  seed[40] = (uint8_t)i;
  shake_inject(&sc[i], seed, 41);
 }
```

接下来的flip操作需要进行一定的修改，我们发现开发者已经为优化预留出了结构 `shake_x4_context` 和函数 `shake_x4_flip`

```c
typedef struct {
 uint64_t A[100];
 unsigned dptr, rate;
} shake_x4_context;
```

```c
void
shake_x4_flip(shake_x4_context *scx4, const shake_context *sc)
{
 for (int i = 0; i < 4; i ++) {
  shake_context sct = sc[i];
  shake_flip(&sct);
  memcpy(scx4->A + (i * 25), sct.A, 25 * sizeof(uint64_t));
 }
 scx4->dptr = scx4->rate = sc[0].rate;
}
```

因此我们直接使用就好。

```c
shake_x4_context scx4;
shake_x4_flip(&scx4, sc);
```

## 主采样循环

首先要理解一下原来的union结构的含义。

```c
union {
    uint8_t b[40];
    uint16_t w[20];
    uint64_t q[5];
   } buf;
```

这个union结构的作用是向内存写入8位的变量b，然后使用16位的w和64位的q来进行访问，通过对一段内存的共享和视图访问来解决了复制造成的内存占用和时间开销。虽然在源代码中开发者根本没用到这一点，使得这一写法显得意义不明，但是在优化过程中我们却可以使用这个特点。可以在调用 `shake_x4_extract_words(&scx4, buf.q, 5)` （没错，开发者也在 `sha3.c`中实现了这个函数）时，数据被写入 `q` 数组（视为 5 个 64 位字），然后通过 `y` 数组将数据视为 `__m256i` 向量，直接用于 AVX2 指令。
接下来的指令是 `shake_extract`的AVX2化版本 `shake_x4_extract_words`，我们有必要了解一下这个函数的作用：

```c
void
shake_extract(shake_context *sc, void *out, size_t len)
{
 size_t dptr, rate;
 uint8_t *buf;

 dptr = sc->dptr;
 rate = sc->rate;
 buf = out;
 while (len > 0) {
  size_t clen;

  if (dptr == rate) {
   process_block(sc->A);
   dptr = 0;
  }
  clen = rate - dptr;
  if (clen > len) {
   clen = len;
  }
  len -= clen;
  while (clen -- > 0) {
   *buf ++ = (uint8_t)(sc->A[dptr >> 3]
    >> ((dptr & 7) << 3));
   dptr ++;
  }
 }
 sc->dptr = (unsigned)dptr;
}

void
shake_x4_extract_words(shake_x4_context *scx4, uint64_t *dst, size_t num_x4)
{
 size_t dptr = scx4->dptr;
 size_t rate = scx4->rate;
 while (num_x4 -- > 0) {
  if (dptr == rate) {
   for (int i = 0; i < 4; i ++) {
    process_block(scx4->A + (i * 25));
   }
   dptr = 0;
  }
  for (int i = 0; i < 4; i ++) {
   dst[i] = scx4->A[(i * 25) + (dptr >> 3)];
  }
  dptr += 8;
  dst += 4;
 }
 scx4->dptr = (unsigned)dptr;
}
```

### **`shake_extract()`：单实例数据提取**

### **功能**

此函数用于 **单个SHAKE实例的挤压阶段**，将内部状态中的数据按字节提取到输出缓冲区。

### **核心逻辑**

1. **状态指针管理**：
  - `dptr`：当前处理位置（字节级偏移）。
  - `rate`：海绵结构的“速率”（单位：字节），即每次挤压阶段输出的最大数据量。
2. **块置换触发**：
  - 当 `dptr == rate` 时，调用 `process_block(sc->A)` 执行 **Keccak-f置换**（哈希核心操作），生成新的状态数据，并重置 `dptr` 为0。
3. **逐字节提取**：
  - 通过 `sc->A[dptr >> 3]` 定位到对应的64位字（`dptr >> 3` 等价于除以8）。
  - 通过 `(dptr & 7) << 3` 计算字节在64位字内的偏移（左移3位等价于乘以8，得到比特偏移）。
  - 示例：若 `dptr = 5`，则从 `sc->A[0]` 中提取第5个字节。

### **应用场景**

- 生成任意长度的哈希输出（如SHAKE-128/256）。

---

### **`shake_x4_extract_words()`：四实例并行提取**

### **功能**

此函数用于 **四个并行SHAKE实例的挤压阶段**，批量提取64位字到目标数组，常用于SIMD优化或批量哈希计算。

### **核心逻辑**

1. **四实例状态管理**：
  - 每个实例的状态存储在 `scx4->A` 中，内存布局为 **四个连续的状态块**，每个块占25个 `uint64_t`（对应SHA-3的1600位状态）。
2. **块置换触发（并行）**：
  - 当 `dptr == rate` 时，对四个实例依次调用 `process_block()`，执行Keccak-f置换。
3. **批量提取64位字**：
  - 每次从四个实例的状态中提取一个64位字（`dptr >> 3` 定位到字索引）。
  - 示例：若 `dptr = 8`，则从每个实例的 `A[1]`（第二个64位字）提取数据。

### **关键设计**

- **内存布局**：四个实例的状态在内存中连续分布，间隔25个 `uint64_t`，便于向量化操作。
- **高效提取**：每次循环提取4个实例的64位字，直接写入目标数组，减少冗余操作。

### **应用场景**

- 高性能计算（如同时生成多个哈希流）。
- 与SIMD指令（如AVX2）结合，加速批量哈希提取。

顺便扩展一下Keccak-f 置换操作的细节，但在此处我们不需要优化它的实现。

Keccak-f 置换操作是 **SHA-3 哈希算法家族（包括 SHAKE、SHA3-256 等）的核心组件**，也是 Keccak 海绵结构的关键步骤。它通过多轮非线性变换对固定大小的内部状态（如 1600 比特）进行混淆和扩散，确保哈希输出的不可预测性和抗攻击性。

---

**1. Keccak-f 的基本结构**

- **状态表示**：

  Keccak-f 将内部状态视为一个 **5×5×w 的三维数组**（`w = 2^ℓ`，例如 `w=64` 对应 1600 比特状态）。每个元素是一个 `w` 比特的“车道（lane）”。

  - SHA-3 使用 `b=1600` 比特（即 `w=64`, `5×5×64=1600`）。
  - 状态可视为 `5x5` 的矩阵，每个元素是一个 64 位整数。

- **轮数**：

  Keccak-f\[b\] 的轮数 `n` 取决于状态大小 `b`：

  - `b=1600`（SHA-3）时，轮数 `n=24`。
  - 每轮包含 **5 个非线性变换步骤**（θ, ρ, π, χ, ι）。

---

**2. Keccak-f 的 5 个步骤**

每轮操作对状态按顺序执行以下 5 个步骤：

**(1) θ（Theta）: 线性混合**

- **目标**：增加状态的扩散性（Diffusion）。
- **操作**：每个比特的值受其相邻列和行的比特异或（XOR）影响。
  - 计算每列的奇偶校验（Parity）并异或到相邻列。
- **公式**：*A*′\[*x*\]\[*y*\]\[*z*\]=*A*\[*x*\]\[*y*\]\[*z*\]⊕(⨁*y*′=04*A*\[*x*−1\]\[*y*′\]\[*z*\]⊕⨁*y*′=04*A*\[*x*+1\]\[*y*′\]\[*z*−1\])

**(2) ρ（Rho）: 比特循环移位**

- **目标**：引入比特位置的混乱（Confusion）。
- **操作**：对每个车道（lane）进行固定偏移量的循环左移（Rotate）。
  - 偏移量由预定义的表格决定，例如 `A[1][0]` 循环左移 1 位。

**(3) π（Pi）: 行置换**

- **目标**：打破对称性，增强非线性扩散。
- **操作**：将 `5x5` 矩阵的行按固定规则重新排列。
  - 新位置 `(x', y') = (y, (2x + 3y) \mod 5)`。

**(4) χ（Chi）: 非线性变换**

- **目标**：引入非线性，抵抗线性密码分析。
- **操作**：对每行应用逻辑运算，使用 AND 和 NOT 操作。
  - 公式：*A*′\[*x*\]\[*y*\]=*A*\[*x*\]\[*y*\]⊕((*NOT* *A*\[*x*+1\]\[*y*\]) *AND* *A*\[*x*+2\]\[*y*\])

**(5) ι（Iota）: 轮常量异或**

- **目标**：打破每轮的对称性，防止固定点攻击。
- **操作**：在特定位置（`A[0][0]`）异或一个预定义的轮常量（Round Constant）。
  - 轮常量由伪随机算法生成，每轮不同。

---

**3. Keccak-f 的安全性与设计特点**

- **抗攻击性**：
  - 通过多轮非线性步骤（尤其是 χ）抵抗差分和线性攻击。
  - ι 的轮常量防止攻击者利用对称性简化计算。
- **效率**：
  - 位操作（AND/XOR/Shift）在硬件和软件中高效实现。
  - 并行性：θ、ρ、π 步骤可并行计算（χ 需顺序处理）。
- **灵活性**：Keccak-f 支持不同状态大小（如 200、400、800、1600 比特），适用于多种场景。

---

**4. Keccak-f 在海绵结构中的角色**

在 **海绵结构（Sponge Construction）** 中，Keccak-f 负责 **吸收（Absorb）** 和 **挤压（Squeeze）** 阶段的处理：

1. **吸收阶段**：
  - 输入数据分块与状态异或，每填充一个块后执行 Keccak-f 置换。
2. **挤压阶段**：
  - 从状态中提取输出数据，每次提取后可能需要执行 Keccak-f 置换以生成新状态。

---

**5. 示例：SHA3-256 中的 Keccak-f**

- **参数**：
  - 状态大小 `b=1600` 比特（`5×5×64`）。
  - 轮数 `n=24`。
- **流程**：
  1. 输入消息填充为 `r=1088` 比特的块（速率 `rate`）。
  2. 每个块异或到状态的前 `r` 比特，执行 Keccak-f\[1600\] 置换。
  3. 最终挤压出 256 比特哈希值。

---

**6. 对比其他哈希函数的核心操作**

| **哈希函数** | **核心操作** | **特点** |
| --- | --- | --- |
| SHA-3 | Keccak-f 置换 | 基于比特操作，抗量子攻击，高灵活性 |
| SHA-2 | 压缩函数（加法、布尔函数） | 依赖算术运算（如模加），易受侧信道攻击 |
| BLAKE3 | 置换 + 树形结构 | 高度并行，SIMD 优化 |

---

**总结**

Keccak-f 置换通过 **多轮非线性变换** 和 **比特级混淆**，为 SHA-3 提供了极高的安全性和效率。其设计平衡了抗攻击能力与实现灵活性，成为后量子时代哈希算法的标杆。

## 内部采样循环

接下来要优化的部分是这一段，也是最关键的一段：

```c
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
```

因此我们要一步步来看。

### 奇偶列构建

```c
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
```

在这里我们可以细致的讲一下这些变量为什么要这么计算，由于开发者极其随意的命名风格，这些变量很难看出到底是什么和怎么计算，这也困扰了我相当长一段时间。

- 变量v

  v实际上是**全局索引**，它的计算方式是 `size_t v = u + (j << 2) + k`

  其中：

  - `u`：外层循环变量，表示当前处理的样本块起始索引（步长16）。
  - `j`：外层循环变量（0\~3），对应四个并行的SHAKE实例。
  - `k`：内层循环变量（0\~3），对应每个SHAKE实例生成的4个样本。

  所以我们得知这里的**处理逻辑**是：

  - 每个SHAKE实例每次生成 **4个样本**（通过 `k` 循环）。
  - 四个SHAKE实例（`j` 循环）共生成 **16个样本**（`4实例 × 4样本`）。
  - 因此，`u` 每次递增16，处理下一个样本块。

  而**全局索引** `v` 的构造：

  - `(j << 2)` 等价于 `j * 4`，表示每个SHAKE实例的样本偏移。
  - `u + (j << 2)` 表示当前SHAKE实例的起始索引。
  - `k` 表示当前实例内的样本偏移。
  - **最终**：`v` 的取值为 `0, 1, 2, ..., 2n-1`，覆盖所有样本。

- 数组t

  `t` 数组是一个 **紧凑的位数组**，存储每个样本的 **奇偶列选择位**（`pbit`），即：

  - `pbit = 0`：选择高斯分布表的偶数列。
  - `pbit = 1`：选择高斯分布表的奇数列。

  存储方式

  1. **每个样本占1位**：
      - 每个样本的 `pbit` 只需1位（0或1），因此一个字节（8位）可以存储 **8个样本** 的 `pbit`。由于我们总共也就只要处理四个SHAKE实例即16个样本，因此两字节大小的t数组实际上就已经足够了。
  2. **索引计算**：
      - **字节索引**：`v >> 3`（等价于 `v / 8`）。
      - **位偏移**：`v & 7`（等价于 `v % 8`）。

- 变量pbit

  提取**奇偶列选择位**pbit: `uint32_t pbit = (t[v >> 3] >> (v & 7)) & 1;`

  - 例如，样本 `v = 9`：
      - 字节索引：`9 >> 3 = 1` → 使用 `t[1]`。
      - 位偏移：`9 & 7 = 1` → 提取 `t[1]` 的第1位。

---

**示例**

假设 `t` 数组内容为：

```c
t[0] = 0b10101010;// 二进制，对应样本0~7的pbit
t[1] = 0b11001100;// 二进制，对应样本8~15的pbit
```

- 样本 `v = 0`：`t[0]` 的第0位 → `0b10101010 >> 0 & 1 = 0`。
- 样本 `v = 1`：`t[0]` 的第1位 → `0b10101010 >> 1 & 1 = 1`。
- 样本 `v = 9`：`t[1]` 的第1位 → `0b11001100 >> 1 & 1 = 0`。

---

在读懂这一部分之后，大家不免产生一个问题，那就是这个pbit变量明明只有0和1两种情况，一个bool类型也能表示了，为什么要用uint32\_t类型？这不是浪费空间吗？答案是确实是这样的，取32位的作用纯粹是为了计算下面的两个掩码（没错，p\_odd和p\_oddw都是掩码，虽然odd的翻译是奇数，但我实在没想明白odd和掩码有什么关系）。

```c
uint64_t p_odd = -(uint64_t)pbit;//64位掩码
uint32_t p_oddw = (uint32_t)p_odd;//32位掩码
```

这行代码的目的是将布尔值 `pbit`（0或1）转换为一个 **全0或全1的64位掩码**，具体规则如下：

- 若 `pbit = 0`，则 `p_odd = 0x0000000000000000`（全0）。
- 若 `pbit = 1`，则 `p_odd = 0xFFFFFFFFFFFFFFFF`（全1）。

**实现原理**

1. **类型转换**：
  - `(uint64_t)pbit`：将 `pbit`（0或1）强制转换为64位无符号整数。
  - 此时结果为 `0x0000000000000000` 或 `0x0000000000000001`。
2. **取负数操作**：
  - 在补码表示中，负数 `x` 等价于 `~x + 1`（按位取反后加1）。
  - 当 `pbit = 0` 时：
      - `0x0000000000000000 = 0x0000000000000000`（全0）。
  - 当 `pbit = 1` 时：
      - `0x0000000000000001 = 0xFFFFFFFFFFFFFFFF`（全1）。

---

在上面的内容都能理解后。我们就可以得到AVX2指令集下的优化方案了。

首先，我们一次要并行处理四个SHAKE实例也就是十六个样本，因此可以直接取消掉j层循环，16个样本对应t数组的两个元素，u的步长是16所以取 `t[(u >> 3) + 0]`和 `t[(u >> 3) + 1]` 就可以得到两个字节了，但具体怎么使用这些奇偶位还需要结合后面的过程来分析。

### 高斯分布查表

我们首先查看接下来的一段循环：

```c
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
```

这段看着全是赋值和运算，让人摸不清头脑。然而，这一段在逻辑上其实是四个条件选择结构。

我们可以把查表部分和运算部分先分离：

```c
uint64_t tlo0 = tab_lo[i + 0];
uint64_t tlo1 = tab_lo[i + 1];
uint32_t thi0 = tab_hi[i + 0];
uint32_t thi1 = tab_hi[i + 1];
 
uint64_t tlo = tlo0
 ^ (p_odd & (tlo0 ^ tlo1));
uint32_t cc =
 (uint32_t)((lo - tlo) >> 63);
uint32_t thi = thi0
 ^ (p_oddw & (thi0 ^ thi1));
r += (hi - thi - cc) >> 31;
```

查表部分所查询的表

```c
static const uint16_t sig_gauss_hi_Hawk_256[] = {
 0x4D70, 0x268B,
 0x0F80, 0x04FA,
 0x0144, 0x0041,
 0x000A, 0x0001
};
static const uint64_t sig_gauss_lo_Hawk_256[] = {
 0x71FBD58485D45050, 0x1408A4B181C718B1,
 0x54114F1DC2FA7AC9, 0x614569CC54722DC9,
 0x42F74ADDA0B5AE61, 0x151C5CDCBAFF49A3,
 0x252E2152AB5D758B, 0x23460C30AC398322,
 0x0FDE62196C1718FC, 0x01355A8330C44097,
 0x00127325DDF8CEBA, 0x0000DC8DE401FD12,
 0x000008100822C548, 0x0000003B0FFB28F0,
 0x0000000152A6E9AE, 0x0000000005EFCD99,
 0x000000000014DA4A, 0x0000000000003953,
 0x000000000000007B, 0x0000000000000000
};
```

这些表中存储了累积分布的阈值，通过查表法达到近似高斯分布。因为一次查两个数据，因此循环步长为2。

来到运算部分，我们从之前的分析中得知，p\_odd和p\_oddw这二者要么全0要么全1，那么实际上可以做出这样的分析：

```c
// p_odd全0
tlo = tlo0 ^ (p_odd & (tlo0 ^ tlo1));
--> tlo = tlo0 ^ (0 & (tlo0 ^ tlo1));
--> tlo = tlo0;
// p_odd全1
tlo = tlo0 ^ (p_odd & (tlo0 ^ tlo1));
--> tlo = tlo0 ^ (1 & (tlo0 ^ tlo1));
--> tlo = tlo0 ^ tlo0 ^ tlo1;
--> tlo = tlo1;
```

可见，这其实是根据p\_odd的取值来为tlo赋值。thi的情况与其一致。

```c
tlo = tlo0 ^ (p_odd & (tlo0 ^ tlo1));  // 等效于 p_odd ? tlo1 : tlo0
thi = thi0 ^ (p_oddw & (thi0 ^ thi1)); // 等效于 p_oddw ? thi1 : thi0
```

然后是

```c
uint32_t cc = (uint32_t)((lo - tlo) >> 63);
r += (hi - thi - cc) >> 31;
```

cc的计算实际上也是一个低位比较。这里计算 `lo - tlo`的符号位（`cc`），若 `lo < tlo`则 `cc = 1`，否则 `cc = 0`。也可以等效为 `cc = lo < tlo ? 1:0;`

而r的计算可以认为是高位比较结果的累加。r是在循环外定义的，这里计算计算 `hi - thi - cc`的符号位，若结果为负则累加 `1`到 `r`。

可能到这里大家有点忘了hi和lo是什么，因为这个函数里变量实在太多了。回忆一下：

```c
uint64_t lo = dec64le(buf.b + (k << 3));
uint32_t hi = dec16le(buf.b + 32 + (k << 1));
lo &= 0x7FFFFFFFFFFFFFFF;
hi &= 0x7FFF;
```

`lo`**：从随机字节流中提取的** 64位无符号整数\*\*，通过 `dec64le(buf.b + (k << 3))` 解码（小端序），再置最高位为0。

`hi`**：从随机字节流中提取的** 16位无符号整数\*\*，通过 `dec16le(buf.b + 32 + (k << 1))` 解码（小端序），再置高17位为0。

两者共同构成一个 **80位精度** 的随机数（`hi`占高16位，`lo`占低64位）。

至于为什么要 `(k << 3)`和 `(k << 1)`，这里要回到结构体：

```c
union {
    uint8_t b[40];   // 40字节的原始字节流
    uint16_t w[20];  // 以16位（2字节）为单位解析
    uint64_t q[5];   // 以64位（8字节）为单位解析
} buf;
```

这40字节的内存布局被设计为：

- **前32字节（`q[0]`\~&#96;q\[3\]&#96;）**：存储4个64位的 `lo` 值（每个占8字节）。
- **后8字节（`q[4]`）**：存储4个16位的 `hi` 值（每个占2字节），共8字节。

`(k << 3)`和 `(k << 1)`分别对代表8字节和2字节，是lo和hi每次取值时的字节步长。

---

`r`的值反映了随机数 `(hi, lo)`在表中连续区间的位置，最终用于生成采样值。

可以简略认为该函数作用是定位随机数在表中的位置。

接下来看下一段循环：

```c
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
```

首先我们要理解这个 `hinz`是什么，虽然我很想解读其为 `hi_not_zero`，但不幸的是，它的意思恰好相反，首先hi是一个占了32位空间的16位无符号整数，那么当且仅当 `hi == 0` 时，`hi - 1` 的二进制为 `0xFFFF`（无符号溢出为最大值），右移31位后 `hinz = 1`。当 `hi > 0` 时，`hi - 1` 是正数，右移31位后 `hinz = 0`。`0 & cc` 等于0，所以当hinz等于0时，下面那个循环是没用的，也就是说，仅当hi等于0时，下面的循环才生效，又因为hi等于0了，只用计算低位比较即可。

我当然没想明白为什么开发者宁愿空转至少4个循环也不愿意写一个判断语句，这真的能更快的运行吗？tlo和cc甚至在上个循环结构中已经做出过判断了，我认为这一部分完全可以被合并到上个循环结构中。

---

### **奇偶性调整**

```c
r = (r << 1) - p_oddw;
```

- **操作分解**：
  - `r << 1`：将累加值 `r` 乘以2。
  - `p_oddw`：减去奇偶标志（0或1）。
- **数学意义**：
  - 当 `p_oddw = 0`（偶数列）：`r = 2r`，保持原权重。
  - 当 `p_oddw = 1`（奇数列）：`r = 2r - 1`，调整权重以反映奇偶差异。
- **目的**：根据奇偶性对采样值进行微调，可能用于处理对称分布的不同分支（如左右两侧概率不同）。

---

### **符号处理**

```c
r = (r ^ neg) - neg;
```

- \*\*变量 `neg`\*\*：
  - `neg = -(uint32_t)(lo >> 63)`，即 `lo` 的最高位（符号位）为1时，`neg = 0xFFFFFFFF`（-1），否则 `neg = 0`。
- **操作分解**：
  - 若 `neg = 0`：`r ^ 0 = r`，`r - 0 = r`，符号不变。
  - 若 `neg = 0xFFFFFFFF`：`r ^ 0xFFFFFFFF` 等价于按位取反，再减去 `0xFFFFFFFF`（即加1），相当于 `r - 1 + 1 = -r`。
- **数学意义**：将 `r` 转换为有符号数：
  - 若 `lo` 的符号位为1（`neg = -1`），则 `r = -r`。
  - 否则保持 `r` 不变。
- **目的**：根据随机数的符号位，确定采样值的正负，确保生成对称的高斯分布。

---

### **存储采样值并累加平方和**

```c
x[v] = (int8_t)*(int32_t *)&r;
sn += r * r;
```

- **强制类型转换**：
  - `(int32_t *)&r`：将 `r` 的地址解释为 `int32_t` 指针（确保符号扩展）。
  - `(int8_t)`：截断为8位有符号整数。
- `sn` 的作用：
  - `r * r` 计算采样值的平方。
  - `sn` 累加所有采样值的平方和，可能用于后续验证（如计算范数或噪声水平）。

---

以上，我们终于彻底讲清楚采样部分的代码原理，接下来开始进行优化。‘

### 随机数选取

首先我们关注到

```c
union {
    uint8_t b[40];
    uint16_t w[20];
    uint64_t q[5];
   } buf;
shake_extract(&sc, buf.b, 40);

union {
   __m256i avx2_view[5];//256位视图
   uint64_t u64_view[20];//64位视图
  } buf;
shake_x4_extract_words(&scx4, buf.u64_view, 5);
```

我们已经知道 `shake_x4_extract_words`是 `shake_extract`的并行版本，然而这其中却有着一些特点，如果在 `shake_extract`中使用四个连续的sc生成buf，若忽略覆盖问题，假设有四个独立的buf， 那么会生成四个连续的结果，但调用 `shake_x4_extract_words` 会从四个并行的 sc（scx4）中提取数据。他们输出的数据是完全一样的，但内存布局却是不一样的，具体表现为 `shake_x4_extract_words`产生的数据以 **四个sc的交错顺序** 存储。

```c
//如果独立调用四次 shake_extract（每次提取一个 sc 的 5 个 uint64_t），则内存布局为：
buf1_sc1.q[5] = [sc1_1, sc1_2, sc1_3, sc1_4, sc1_5]  // 第一个 `sc`
buf2_sc2.q[5] = [sc2_1, sc2_2, sc2_3, sc2_4, sc2_5]  // 第二个 `sc`
buf3_sc3.q[5] = [sc3_1, sc3_2, sc3_3, sc3_4, sc3_5]  // 第三个 `sc`
buf4_sc4.q[5] = [sc4_1, sc4_2, sc4_3, sc4_4, sc4_5]  // 第四个 `sc`

//而 shake_x4_extract_words 的布局是 将这四个独立缓冲区的数据按列展开。
buf.u64_view[] = [
    sc1_1, sc2_1, sc3_1, sc4_1, 
    sc1_2, sc2_2, sc3_2, sc4_2,  
    sc1_3, sc2_3, sc3_3, sc4_3,  
    sc1_4, sc2_4, sc3_4, sc4_4, 
    sc1_5, sc2_5, sc3_5, sc4_5,  
]

```

我们已知40字节的内存布局被设计为：

- **前32字节（`q[0]`\~&#96;q\[3\]&#96;）**：存储4个64位的 `lo` 值（每个占8字节）。
- **后8字节（`q[4]`）**：存储4个16位的 `hi` 值（每个占2字节），共8字节。。

那么在 `buf.u64_view`下的内存布局将是

- **前128字节（**`avx2_view**[0]`\~**`avx2_view**[3]`）**：存储4个256位的 `lo` 值。
  - 每256位：被分为4个64位，分别存储sc1/sc2/sc3/sc4的第n个 `lo`值。
- **后32字节（**`avx2_view**[4]`）\*\*：存储1个256位的 `hi` 值。
  - 被分为4个64位，分别连续存储sc1/sc2/sc3/sc4的所有 `hi`值。

于是我们先分离高位：

```c
__m256i avx2_256_hi = buf.avx2_view[4];
```

### 主采样循环优化

首先我们把它99.9984741109375%(开玩笑的，受电磁干扰可能会置全0)都要空转的循环代码先合并：

```c
uint32_t r = 0;
uint32_t hinz = (hi - 1) >> 31;
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
     r += hinz & cc;//尊重一下开发者不写if的优化方案
    }
```

经过前面的分析，我们不难判断出，每一个 `pbit`都对应着一个64位无符号数。而由上面的内存布局来看，我们其实完全可以构建一个4\*4的二维数组来存储并使用 `pbit` 。

```c
// 构建奇偶列
int pbit[4][4];
for(size_t j = 0; j < 4; j ++) {
 for(size_t i = 0; i < 4; i ++) {
  int tmp = (i + 1) * (j + 1);
  pbit[i][j] = ( t[tmp >> 3] >> (tmp & 7) ) & 1;
 }
}
```

同时我们也要创建 `neg`，这里我们要使用一个新的内联函数 `_mm256_cmpeq_epi64`，稍后做出介绍：

```c
for(size_t i = 0; i < 4; i ++) {
 avx2_256_lo[i] = _mm256_and_si256(buf.avx2_view[i], avx2_256_lo_mask);
 avx2_256_negative_mask[i] = _mm256_cmpeq_epi64(_mm256_srli_epi64(buf.avx2_view[i],63), _mm256_set1_epi64x(0x1));
}
```

---

**`_mm256_cmpeq_epi64` 详解**

**函数原型**

```c
__m256i _mm256_cmpeq_epi64(__m256i a, __m256i b);
```

**功能**

- 对输入向量 `a` 和 `b` 中的每个 **64 位有符号整数元素** 进行相等比较。
- **返回值**：一个 256 位向量，每个 64 位元素根据比较结果设置：
  - 若 `a[i] == b[i]`，对应位置为全 1（`0xFFFFFFFFFFFFFFFF`）。
  - 若 `a[i] != b[i]`，对应位置为全 0（`0x0000000000000000`）。

---

同时也不能忽略高位为0的情况：

```c
__m256i avx2_256_hi_equals_zero = _mm256_srli_epi64(_mm256_cmpeq_epi64(avx2_256_hi, _mm256_setzero_si256()),63);
```

接下来要做的就是把循环结构并行化，我们在这里必须搞清楚，把64位无符号数作为操作基准，不然很容易陷入到混乱的思维中。（亲身经历）

首先，对于一个64位无符号数，必然有一个 `pbit`与之对应，又因为并行生成的 `buf`是交错存储结果的，无处理情况下，通过 `buf.avx2_view`获取到的256位变量实际上存储的是未优化情况下循环的第一个64位整数的集合，即：

```c
sc1_1, sc2_1, sc3_1, sc4_1
```

而每一个64位无符号数要四次循环，选取 `tab`中的值进行运算来确定随机数在高斯分布表的位置，因此我们可以做如下优化：

```c
for(size_t j = 0; j < 4; j ++) {
    __m256i avx2_256_tab_low = _mm256_setr_epi64x(
     tab_lo[pbit[i][0] + 2 * j],
     tab_lo[pbit[i][1] + 2 * j],
     tab_lo[pbit[i][2] + 2 * j],
     tab_lo[pbit[i][3] + 2 * j]);
    __m256i avx2_256_tab_hi = _mm256_setr_epi64x(
     (uint64_t)tab_hi[pbit[i][0] + 2 * j],
     (uint64_t)tab_hi[pbit[i][1] + 2 * j],
     (uint64_t)tab_hi[pbit[i][2] + 2 * j],
     (uint64_t)tab_hi[pbit[i][3] + 2 * j]);
    __m256i avx2_256_cc = _mm256_srli_epi64(_mm256_sub_epi64(avx2_256_lo[i], avx2_256_tab_low),63);
    sna1 = _mm256_add_epi64(_mm256_srli_epi64(_mm256_sub_epi64(avx2_256_hi,
     _mm256_add_epi64(avx2_256_cc, avx2_256_tab_hi)),63), sna1);
    sna1 = _mm256_add_epi64(_mm256_and_si256(avx2_256_hi_equals_zero,avx2_256_cc),sna1);
   }
```

我们一共要完成对16个无符号数的处理，而通过AVX2指令我们得以一次完成对四个无符号数的处理。但我们仍然需要一次外循环来帮助我们处理完16个数，同时我们要完成对 `sna`的处理，`sna1`是针对与一个整数进行计算的结果，而 `sna`则是全局的累加结果。也不能忽略掉 `x`对 `sna`1的存储。

```c
for(size_t i = 0; i < 4; i ++) {
   for(size_t j = 0; j < 4; j ++) {
    __m256i avx2_256_tab_low = _mm256_setr_epi64x(
     tab_lo[pbit[i][0] + 2 * j],
     tab_lo[pbit[i][1] + 2 * j],
     tab_lo[pbit[i][2] + 2 * j],
     tab_lo[pbit[i][3] + 2 * j]);
    __m256i avx2_256_tab_hi = _mm256_setr_epi64x(
     (uint64_t)tab_hi[pbit[i][0] + 2 * j],
     (uint64_t)tab_hi[pbit[i][1] + 2 * j],
     (uint64_t)tab_hi[pbit[i][2] + 2 * j],
     (uint64_t)tab_hi[pbit[i][3] + 2 * j]);
    __m256i avx2_256_cc = _mm256_srli_epi64(_mm256_sub_epi64(avx2_256_lo[i], avx2_256_tab_low),63);
    sna1 = _mm256_add_epi64(_mm256_srli_epi64(_mm256_sub_epi64(avx2_256_hi,
     _mm256_add_epi64(avx2_256_cc, avx2_256_tab_hi)),63), sna1);
    sna1 = _mm256_add_epi64(_mm256_and_si256(avx2_256_hi_equals_zero,avx2_256_cc),sna1);
   }

   sna1 = _mm256_sub_epi64(_mm256_slli_epi64(sna1,1),_mm256_setr_epi64x(
    pbit[i][0],
    pbit[i][1],
    pbit[i][2],
    pbit[i][3]));

   sna1 = _mm256_sub_epi64(_mm256_xor_epi64(sna1, avx2_256_negative_mask[i]), avx2_256_negative_mask[i]);

   for(size_t j = 0; j < 4; j ++) {
    uint32_t tmp = _mm256_extract_epi32(sna1, 2 * j);
    x[4 * i + j] = (int8_t)*(int32_t *)&tmp;
   }

   sna = _mm256_add_epi64(_mm256_mullo_epi64(sna1,sna1),sna);
  }
```

完成这些后。该函数的优化工作就已经完成了，以下是优化后的函数整体：

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

 size_t n = (size_t)1 << logn;
 uint8_t seed[41];
 rng(rng_context, seed, 40);

    // 初始化四个SHAKE上下文并inject
 shake_context sc[4];
 for (int i = 0; i < 4; i ++) {
  if (sc_extra != NULL) {
   sc[i] = *sc_extra;
  } else {
   shake_init(&sc[i], 256);
  }
  seed[40] = (uint8_t)i;
  shake_inject(&sc[i], seed, 41);
 }
 shake_x4_context scx4;
 shake_x4_flip(&scx4, sc);

    //设置掩码
 __m256i avx2_256_hi_mask = _mm256_set1_epi64x(0x7FFF);
 __m256i avx2_256_lo_mask = _mm256_set1_epi64x(0x7FFFFFFFFFFFFFFF);

    //设置平方范数累加器 Square norm accumulator
 __m256i sna = _mm256_setzero_si256();

 for (size_t u = 0; u < (n << 1); u += 16) {
  union {
   __m256i avx2_view[5];//256位视图
   uint64_t u64_view[20];//64位视图
  } buf;

  shake_x4_extract_words(&scx4, buf.u64_view, 5);
  __m256i avx2_256_hi = _mm256_and_si256(buf.avx2_view[4], avx2_256_hi_mask);

  // 构建奇偶列
  int pbit[4][4];
  for(size_t j = 0; j < 4; j ++) {
   for(size_t i = 0; i < 4; i ++) {
    int tmp = (i + 1) * (j + 1);
    pbit[i][j] = ( t[tmp >> 3] >> (tmp & 7) ) & 1;
   }
  }

  __m256i avx2_256_hi_equals_zero = _mm256_srli_epi64(_mm256_cmpeq_epi64(avx2_256_hi, _mm256_setzero_si256()),63);

  __m256i avx2_256_lo[4];
  __m256i avx2_256_negative_mask[4];

  for(size_t i = 0; i < 4; i ++) {
   avx2_256_lo[i] = _mm256_and_si256(buf.avx2_view[i], avx2_256_lo_mask);
   avx2_256_negative_mask[i] = _mm256_cmpeq_epi64(_mm256_srli_epi64(buf.avx2_view[i],63), _mm256_set1_epi64x(0x1));
  }

  __m256i sna1 = _mm256_setzero_si256();

  for(size_t i = 0; i < 4; i ++) {
   for(size_t j = 0; j < 4; j ++) {
    __m256i avx2_256_tab_low = _mm256_setr_epi64x(
     tab_lo[pbit[i][0] + 2 * j],
     tab_lo[pbit[i][1] + 2 * j],
     tab_lo[pbit[i][2] + 2 * j],
     tab_lo[pbit[i][3] + 2 * j]);
    __m256i avx2_256_tab_hi = _mm256_setr_epi64x(
     (uint64_t)tab_hi[pbit[i][0] + 2 * j],
     (uint64_t)tab_hi[pbit[i][1] + 2 * j],
     (uint64_t)tab_hi[pbit[i][2] + 2 * j],
     (uint64_t)tab_hi[pbit[i][3] + 2 * j]);
    __m256i avx2_256_cc = _mm256_srli_epi64(_mm256_sub_epi64(avx2_256_lo[i], avx2_256_tab_low),63);
    sna1 = _mm256_add_epi64(_mm256_srli_epi64(_mm256_sub_epi64(avx2_256_hi,
     _mm256_add_epi64(avx2_256_cc, avx2_256_tab_hi)),63), sna1);
    sna1 = _mm256_add_epi64(_mm256_and_si256(avx2_256_hi_equals_zero,avx2_256_cc),sna1);
   }

   sna1 = _mm256_sub_epi64(_mm256_slli_epi64(sna1,1),_mm256_setr_epi64x(
    pbit[i][0],
    pbit[i][1],
    pbit[i][2],
    pbit[i][3]));

   sna1 = _mm256_sub_epi64(_mm256_xor_epi64(sna1, avx2_256_negative_mask[i]), avx2_256_negative_mask[i]);

   for(size_t j = 0; j < 4; j ++) {
    uint32_t tmp = _mm256_extract_epi32(sna1, 2 * j);
    x[4 * i + j] = (int8_t)*(int32_t *)&tmp;
   }

   sna = _mm256_add_epi64(_mm256_mullo_epi64(sna1,sna1),sna);
  }
 }
}
```

在与这个函数鏖战数日之后，我决定致敬一下开发者，把乘法都换成位运算。以下是修正后并添加了注释的版本。

```c
/* 高斯采样核心函数（使用AVX2加速） */
static uint32_t
sig_gauss(unsigned logn,
          void (*rng)(void *ctx, void *dst, size_t len), void *rng_context,
          const shake_context *sc_extra, int8_t *x, const uint8_t *t)
{
    /* 高斯分布表指针和长度 */
    const uint16_t *tab_hi;  // 高位数分布表
    const uint64_t *tab_lo;  // 低位数分布表
    size_t hi_len, lo_len;   // 分布表长度

    /* 根据安全级别选择预计算的高斯分布表 */
    switch (logn)  // logn决定密码学方案的安全级别
    {
    case 8:  // 256位安全级别
        tab_hi = sig_gauss_hi_Hawk_256;
        tab_lo = sig_gauss_lo_Hawk_256;
        hi_len = SG_MAX_HI_Hawk_256;
        lo_len = SG_MAX_LO_Hawk_256;
        break;
    case 9:  // 512位安全级别
        tab_hi = sig_gauss_hi_Hawk_512;
        tab_lo = sig_gauss_lo_Hawk_512;
        hi_len = SG_MAX_HI_Hawk_512;
        lo_len = SG_MAX_LO_Hawk_512;
        break;
    default: /* 10 */  // 1024位安全级别
        tab_hi = sig_gauss_hi_Hawk_1024;
        tab_lo = sig_gauss_lo_Hawk_1024;
        hi_len = SG_MAX_HI_Hawk_1024;
        lo_len = SG_MAX_LO_Hawk_1024;
        break;
    }

    /* 初始化基础参数 */
    size_t n = (size_t)1 << logn;  // 计算向量维度：n = 2^logn
    uint8_t seed[41];              // 随机种子缓冲区（40字节随机数 + 1字节标识）

    /* 生成随机种子 */
    rng(rng_context, seed, 40);  // 调用随机数生成器填充40字节种子

    // 初始化四个SHAKE上下文并inject
    shake_context sc[4];  // 4个并行SHAKE上下文
    for (int i = 0; i < 4; i++)
    {
        /* 上下文初始化：继承或新建 */
        if (sc_extra != NULL)  // 如果存在外部上下文
        {
            sc[i] = *sc_extra;  // 直接复制已有上下文
        }
        else  // 否则初始化新上下文
        {
            shake_init(&sc[i], 256);  // 初始化256位安全级别的SHAKE
        }
        /* 注入带标识的种子 */
        seed[40] = (uint8_t)i;         // 最后1字节设置为上下文标识
        shake_inject(&sc[i], seed, 41); // 注入41字节种子（40+1）
    }
    /* 初始化四路并行处理上下文 */
    shake_x4_context scx4;          // 四路并行处理结构
    shake_x4_flip(&scx4, sc);       // 转换到输出模式

    /* AVX2掩码初始化 */
    __m256i avx2_256_hi_mask = _mm256_set1_epi64x(0x7FFF);          // 高位掩码（保留15位）
    __m256i avx2_256_lo_mask = _mm256_set1_epi64x(0x7FFFFFFFFFFFFFFF); // 低位掩码（保留63位）

    /* 平方范数累加器初始化 */
    __m256i sna = _mm256_setzero_si256();  // 使用256位SIMD寄存器存储累加值

    /* 主处理循环：每次处理16个元素 */
    for (size_t u = 0; u < (n << 1); u += 16)  // 总处理量是2n，步长16
    {
        /* 随机数据缓冲区（联合体实现双视图访问） */
        union
        {
            __m256i avx2_view[5];  // AVX2向量视图（5个256位寄存器）
            uint64_t u64_view[20]; // 等价于20个64位整数值
        } buf;

        /* 从四路SHAKE上下文中提取随机数据 */
        shake_x4_extract_words(&scx4, buf.u64_view, 5);  // 提取5个256位数据块
        __m256i avx2_256_hi = _mm256_and_si256(buf.avx2_view[4], avx2_256_hi_mask);  // 处理第5个块的高位部分

        /* 构建4x4奇偶校验位矩阵 */
        int pbit[4][4];  // 奇偶校验位存储矩阵
        for (size_t j = 0; j < 4; j++)  // 列循环
        {
            for (size_t i = 0; i < 4; i++)  // 行循环
            {
                int tmp = (i + 1) * (j + 1);  // 计算t数组的索引位置
                pbit[i][j] = (t[tmp >> 3] >> (tmp & 7)) & 1;  // 位操作提取特定位（tmp/8字节，tmp%8位）
            }
        }

        /* 计算高位部分是否为零的条件掩码 */
        __m256i avx2_256_hi_equals_zero = _mm256_srli_epi64(
            _mm256_cmpeq_epi64(avx2_256_hi, _mm256_setzero_si256()), 63);  // 生成64位全1掩码

        /* 准备AVX2运算数据 */
        __m256i avx2_256_lo[4];          // 低位数据存储
        __m256i avx2_256_negative_mask[4]; // 符号位掩码
        for (size_t i = 0; i < 4; i++)  // 处理前4个256位块
        {
            avx2_256_lo[i] = _mm256_and_si256(buf.avx2_view[i], avx2_256_lo_mask);  // 提取低位数据
            avx2_256_negative_mask[i] = _mm256_cmpeq_epi64(
                _mm256_srli_epi64(buf.avx2_view[i], 63), _mm256_set1_epi64x(0x1)); // 提取符号位（1表示负数）
        }

        /* 临时平方范数累加器 */
        __m256i sna1 = _mm256_setzero_si256();  // 每轮计算的临时累加

        /* 四通道并行处理 */
        for (size_t i = 0; i < 4; i++)  // 处理4个通道
        {
            for (size_t j = 0; j < 4; j++)  // 每个通道4个步骤
            {
                /* 加载高斯分布表值（低64位） */
                __m256i avx2_256_tab_low = _mm256_setr_epi64x(
                    tab_lo[pbit[i][0] + (j << 1)],  // 通道0的表索引
                    tab_lo[pbit[i][1] + (j << 1)],  // 通道1的表索引
                    tab_lo[pbit[i][2] + (j << 1)],  // 通道2的表索引
                    tab_lo[pbit[i][3] + (j << 1)]); // 通道3的表索引
    
                /* 加载高斯分布表值（高16位转64位） */
                __m256i avx2_256_tab_hi = _mm256_setr_epi64x(
                    (uint64_t)tab_hi[pbit[i][0] + (j << 1)],  // 高位扩展
                    (uint64_t)tab_hi[pbit[i][1] + (j << 1)],
                    (uint64_t)tab_hi[pbit[i][2] + (j << 1)],
                    (uint64_t)tab_hi[pbit[i][3] + (j << 1)]);

                /* 计算进位标志 */
                __m256i avx2_256_cc = _mm256_srli_epi64(
                    _mm256_sub_epi64(avx2_256_lo[i], avx2_256_tab_low), 63); // 比较低位差值的符号位

                /* 更新临时累加器 */
                sna1 = _mm256_add_epi64(
                    _mm256_srli_epi64(
                        _mm256_sub_epi64(avx2_256_hi, _mm256_add_epi64(avx2_256_cc, avx2_256_tab_hi)), 
                        63), 
                    sna1);  // 高位差值的符号位累加
                sna1 = _mm256_add_epi64(
                    _mm256_and_si256(avx2_256_hi_equals_zero, avx2_256_cc), 
                    sna1);  // 高位为零时的进位累加
            }

            /* 调整累加器符号 */
            sna1 = _mm256_sub_epi64(
                _mm256_slli_epi64(sna1, 1),  // 左移1位（乘2）
                _mm256_setr_epi64x(         // 减去奇偶校验位
                    pbit[i][0],
                    pbit[i][1],
                    pbit[i][2],
                    pbit[i][3]));

            /* 应用符号掩码 */
            sna1 = _mm256_sub_epi64(
                _mm256_xor_epi64(sna1, avx2_256_negative_mask[i]), 
                avx2_256_negative_mask[i]);  // 根据符号位调整正负号

            /* 存储采样结果到输出数组 */
            for (size_t j = 0; j < 4; j++)  // 处理4个通道结果
            {
                uint32_t tmp = _mm256_extract_epi32(sna1, 2 * j);  // 提取32位中间结果
                x[(j << 1) + j] = (int8_t)*(int32_t *)&tmp;        // 转换为8位有符号整数存储
            }

            /* 更新平方范数累加器 */
            sna = _mm256_add_epi64(
                _mm256_mullo_epi64(sna1, sna1),  // 计算平方
                sna);  // 累加到总平方和
        }
    }
}
```

---

## 感想

说实话，连着做了几天这个函数，没有一点感想是不可能的，事实上，最后完成优化的部分并没有多长，反而是之前为了理解这个函数的作用，理解变量的意义（尤其在作者命名意义不明的时候），源代码在一部分程度上的优化（比如位运算），理解源代码对内存布局的安排花了大量的学习时间和思考时间，即便到现在我认为我已经完成了对这个函数的优化，但我仍然不能完全理解这个函数某些计算的意义，恐怕还得恶补大量的数学基础才能更加进一步的优化了。但我时间有限，还要完成对其他许多函数的优化，而且开发者在注释中提及的也大概是这个方向，只能到此为止了。不过这段时间的花费绝非没有意义。虽然有点折磨和费脑子，但确实能够提升我在这个方向上的知识和工作能力。最少也产出了这篇记录，不至于之后回头来看不懂自己的代码了😂
