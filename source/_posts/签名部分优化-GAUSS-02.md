---
title: 签名部分优化-GAUSS-02
date: 2025-02-27 19:08:12
updated: 2025-03-03
tags:
  - AVX2
  - Hawk
---

## 函数核心逻辑

1. **高斯采样背景**：
   - 在基于格的密码学中，高斯采样用于生成签名噪声，确保安全性。
   - 函数生成的值 `x` 符合均值为 `t/2`、标准差为 `sigma_sign` 的高斯分布，实际输出为 `2*x`（避免浮点运算）。
2. **核心逻辑**：
   - 使用预计算的表 `tab_hi` 和 `tab_lo` 加速采样，表中存储离散高斯分布的累积概率分布。
   - 通过随机数决定符号和绝对值，根据奇偶校验位 `t` 选择不同列，调整采样结果以满足特定约束。
3. **随机数生成**：
   - `sig_gauss` 使用 SHAKE 哈希（基于种子生成伪随机流）。
   - `sig_gauss_alt` 直接调用外部 RNG，减少哈希计算开销。

## **逐行解析**

### **1. `sig_gauss` 函数**

```c
static uint32_t
sig_gauss(unsigned logn,
 void (*rng)(void *ctx, void *dst, size_t len), void *rng_context,
 const shake_context *sc_extra, int8_t *x, const uint8_t *t)
{
 // 根据 logn 选择预计算的表
 const uint16_t *tab_hi;
 const uint64_t *tab_lo;
 size_t hi_len, lo_len;
 switch (logn) {
 case 8: // 256-bit 安全级别
  tab_hi = sig_gauss_hi_Hawk_256;
  tab_lo = sig_gauss_lo_Hawk_256;
  hi_len = SG_MAX_HI_Hawk_256;
  lo_len = SG_MAX_LO_Hawk_256;
  break;
 // ...类似处理 logn=9 和 10...
 }

 size_t n = (size_t)1 << logn; // 计算 n = 2^logn
 uint8_t seed[41];
 rng(rng_context, seed, 40); // 生成 40 字节随机种子

 uint32_t sn = 0; // 平方范数累加器
 for (size_t j = 0; j < 4; j ++) { // 4 个 SHAKE 实例
  shake_context sc;
  // 初始化 SHAKE 上下文（可能复用 sc_extra）
  if (sc_extra != NULL) sc = *sc_extra;
  else shake_init(&sc, 256);
  seed[40] = (uint8_t)j; // 添加计数器
  shake_inject(&sc, seed, 41); // 注入种子
  shake_flip(&sc); // 切换至输出模式

  for (size_t u = 0; u < (n << 1); u += 16) { // 处理每个块
   union { uint8_t b[40]; uint64_t q[5]; } buf;
   shake_extract(&sc, buf.b, 40); // 提取 40 字节
   for (size_t k = 0; k < 4; k ++) { // 每个块含 4 个样本
    size_t v = u + (j << 2) + k; // 当前样本索引
    uint64_t lo = dec64le(buf.b + (k << 3)); // 低 64 位
    uint32_t hi = dec16le(buf.b + 32 + (k << 1)); // 高 16 位

    // 提取符号位（最高位）
    uint32_t neg = -(uint32_t)(lo >> 63);
    lo &= 0x7FFFFFFFFFFFFFFF; // 清除符号位
    hi &= 0x7FFF;

    // 根据奇偶位选择列
    uint32_t pbit = (t[v >> 3] >> (v & 7)) & 1;
    uint64_t p_odd = -(uint64_t)pbit; // 全 0 或全 1

    // 查表计算绝对值
    uint32_t r = 0;
    // 处理高位部分（hi_len 前的条目）
    for (size_t i = 0; i < hi_len; i += 2) {
     // 根据 p_odd 选择偶/奇列
     uint64_t tlo = tab_lo[i] ^ (p_odd & (tab_lo[i] ^ tab_lo[i+1]));
     uint32_t thi = tab_hi[i] ^ (p_odd & (tab_hi[i] ^ tab_hi[i+1]));
     // 比较 lo 和 tlo，hi 和 thi
     uint32_t cc = (lo - tlo) >> 63; // 0 或 1
     r += (hi - thi - cc) >> 31; // 若 hi < thi + cc，则累加 1
    }
    // 处理低位部分（hi 已为 0）
    uint32_t hinz = (hi - 1) >> 31; // hi != 0 时为 0xFFFFFFFF
    for (size_t i = hi_len; i < lo_len; i += 2) {
     uint64_t tlo = ...; // 同上
     uint32_t cc = (lo - tlo) >> 63;
     r += hinz & cc; // 仅当 hi != 0 时累加
    }

    // 调整奇偶性和符号
    r = (r << 1) - pbit; // 乘以 2 并减去 pbit
    r = (r ^ neg) - neg; // 应用符号
    x[v] = (int8_t)r;    // 存储到 x
    sn += r * r;         // 累加平方
   }
  }
 }
 return sn;
}
```

**2. `sig_gauss_alt` 函数**

与 `sig_gauss` 类似，但直接调用 RNG 生成 160 字节数据块，而非使用 SHAKE：

```c
static uint32_t
sig_gauss_alt(...)
{
 // 相同表选择逻辑...

 union { uint8_t b[160]; uint64_t q[20]; } buf;
 rng(rng_context, buf.b, sizeof buf.b); // 直接生成数据

 for (size_t u = 0; u < (n << 1); u += 16) {
  for (size_t j = 0; j < 4; j ++) {
   for (size_t k = 0; k < 4; k ++) {
    // 从 buf 中解析 lo 和 hi（类似原函数）
    uint64_t lo = dec64le(buf.b + (j << 3) + (k << 5));
    uint32_t hi = dec16le(buf.b + (j << 3) + 128 + (k << 1));
    // ...后续处理相同...
   }
  }
 }
 return sn;
}

```

### **关键点总结**

1. **表驱动采样**：
   - 使用预计算的 `tab_hi` 和 `tab_lo` 加速高斯采样，通过查表减少实时计算量。
2. **奇偶校验位处理**：
   - 根据 `t` 中的位选择不同的列，调整采样结果以满足签名中的线性约束。
3. **符号处理**：
   - 符号位单独处理，通过位操作高效应用符号到绝对值结果。
4. **随机数生成差异**：
   - `sig_gauss` 使用基于 SHAKE 的确定性随机数生成，适合需要确定性的场景。
   - `sig_gauss_alt` 直接使用外部 RNG，减少计算开销，适合资源受限环境。
5. **性能优化**：
   - 通过循环展开（处理 4 个样本/块）、位操作和查表优化性能。

| **代码行** | **解析** |
| --- | --- |
| `static uint32_t sig_gauss(...)` | 定义静态函数，返回 `uint32_t` 类型，用于计算签名的高斯采样结果。 |
| `const uint16_t *tab_hi;` | 声明指向高斯分布高位概率表的指针。 |
| `const uint64_t *tab_lo;` | 声明指向高斯分布低位概率表的指针。 |
| `size_t hi_len, lo_len;` | 声明表长度变量，分别表示高位和低位表的长度。 |
| `switch (logn) { ... }` | 根据 `logn` 选择不同参数（256/512/1024），设置对应的表和长度。 |
| `size_t n = (size_t)1 << logn;` | 计算多项式环的维度 `n = 2^logn`。 |
| `uint8_t seed[41];` | 声明41字节的种子数组，用于初始化随机数生成器。 |
| `rng(rng_context, seed, 40);` | 调用外部随机数生成函数填充种子（前40字节）。 |
| `uint32_t sn = 0;` | 初始化 `sn` 为0，用于累加所有采样值的平方和。 |
| `for (size_t j = 0; j < 4; j ++)` | 循环4次，处理4个并行的SHAKE实例。 |
| `shake_context sc;` | 声明SHAKE上下文结构体，用于生成随机数流。 |
| `seed[40] = (uint8_t)j;` | 设置种子第41字节为循环索引 `j`，区分不同实例。 |
| `shake_inject(&sc, seed, 41);` | 将种子注入SHAKE上下文，初始化哈希状态。 |
| `shake_flip(&sc);` | 切换SHAKE到输出模式（”flipping” 阶段）。 |
| `for (size_t u = 0; u < (n << 1); u += 16)` | 循环生成 `2n` 个样本，每次处理16个样本的块。 |
| `union { ... } buf;` | 声明联合体 `buf`，用于存储SHAKE输出的40字节数据。 |
| `shake_extract(&sc, buf.b, 40);` | 从SHAKE中提取40字节到 `buf`。 |
| `for (size_t k = 0; k < 4; k ++)` | 处理每个块内的4个样本（共16个样本/块）。 |
| `size_t v = u + (j << 2) + k;` | 计算当前样本的全局索引 `v`。 |
| `uint64_t lo = dec64le(buf.b + (k << 3));` | 从 `buf` 中提取小端序的64位低位随机数。 |
| `uint32_t hi = dec16le(buf.b + 32 + (k << 1));` | 从 `buf` 中提取小端序的16位高位随机数。 |
| `uint32_t neg = -(uint32_t)(lo >> 63);` | 提取符号位，`neg` 为全0或全1的掩码。 |
| `lo &= 0x7FFFFFFFFFFFFFFF;` | 清除 `lo` 的最高位（符号位）。 |
| `hi &= 0x7FFF;` | 清除 `hi` 的最高位（符号位）。 |
| `uint32_t pbit = (t[v >> 3] >> (v & 7)) & 1;` | 从 `t` 数组中提取对应位，决定奇偶列。 |
| `uint64_t p_odd = -(uint64_t)pbit;` | 将 `pbit` 转换为全0或全1的64位掩码。 |
| `uint32_t p_oddw = (uint32_t)p_odd;` | 同上，但为32位掩码。 |
| `uint32_t r = 0;` | 初始化采样值 `r` 为0。 |
| `for (size_t i = 0; i < hi_len; i += 2)` | 遍历高位表项，比较随机数与表值，计算 `r`。 |
| `uint64_t tlo = tlo0 ^ (p_odd & (tlo0 ^ tlo1));` | 根据奇偶列选择表项（异或操作）。 |
| `uint32_t cc = (uint32_t)((lo - tlo) >> 63);` | 若 `lo < tlo`，则 `cc=1`，否则 `cc=0`。 |
| `r += (hi - thi - cc) >> 31;` | 若 `hi < thi + cc`，则 `r += 1`。 |
| `uint32_t hinz = (hi - 1) >> 31;` | 若 `hi == 0`，则 `hinz=0xFFFFFFFF`，否则 `0`。 |
| `for (size_t i = hi_len; i < lo_len; i += 2)` | 遍历剩余低位表项，补充计算 `r`。 |
| `r = (r << 1) - p_oddw;` | 将 `r` 乘以2并应用奇偶性。 |
| `r = (r ^ neg) - neg;` | 应用符号位，若 `neg` 非零则取反。 |
| `x[v] = (int8_t)*(int32_t *)&r;` | 将 `r` 转换为 `int8_t` 存入 `x` 数组。 |
| `sn += r * r;` | 累加 `r^2` 到 `sn`，用于后续范数计算。 |

---

### **变量含义表**

| **变量名** | **类型** | **含义** |
| --- | --- | --- |
| `logn` | `unsigned` | 多项式环维度的对数（`n = 2^logn`）。 |
| `rng` | 函数指针 | 外部随机数生成函数。 |
| `rng_context` | `void *` | 随机数生成器的上下文指针。 |
| `sc_extra` | `shake_context *` | 预先生成的SHAKE上下文（可选）。 |
| `x` | `int8_t *` | 存储高斯采样结果的数组。 |
| `t` | `const uint8_t *` | 输入数据，决定奇偶列的位数组。 |
| `tab_hi` | `const uint16_t *` | 高斯分布高位概率表。 |
| `tab_lo` | `const uint64_t *` | 高斯分布低位概率表。 |
| `hi_len` | `size_t` | 高位概率表的长度。 |
| `lo_len` | `size_t` | 低位概率表的长度。 |
| `n` | `size_t` | 多项式环维度 `n = 2^logn`。 |
| `seed` | `uint8_t[41]` | 随机种子（40字节 + 1字节索引）。 |
| `sn` | `uint32_t` | 所有采样值的平方和。 |
| `j` | `size_t` | 循环索引（0-3），对应4个SHAKE实例。 |
| `sc` | `shake_context` | SHAKE-256的哈希上下文。 |
| `u` | `size_t` | 外层循环索引，处理样本块（步长16）。 |
| `buf` | 联合体 | 存储SHAKE输出的40字节数据。 |
| `k` | `size_t` | 内层循环索引（0-3），处理每个块的4个样本。 |
| `v` | `size_t` | 当前样本的全局索引（范围：0 到 `2n-1`）。 |
| `lo` | `uint64_t` | 64位低位随机数（符号位已清除）。 |
| `hi` | `uint32_t` | 16位高位随机数（符号位已清除）。 |
| `neg` | `uint32_t` | 符号位掩码（0或0xFFFFFFFF）。 |
| `pbit` | `uint32_t` | 奇偶列选择位（0或1）。 |
| `p_odd` | `uint64_t` | 奇偶列的64位掩码。 |
| `p_oddw` | `uint32_t` | 奇偶列的32位掩码。 |
| `i` | `size_t` | 查表时的循环索引。 |
| `tlo0`, `tlo1` | `uint64_t` | 低位表中的相邻表项。 |
| `tlo` | `uint64_t` | 根据奇偶列选择的低位表项。 |
| `thi0`, `thi1` | `uint32_t` | 高位表中的相邻表项。 |
| `thi` | `uint32_t` | 根据奇偶列选择的高位表项。 |
| `cc` | `uint32_t` | 比较标志（`lo < tlo` 时为1）。 |
| `hinz` | `uint32_t` | 高位随机数是否为0的掩码。 |
| `r` | `uint32_t` | 最终的高斯采样值（转换为有符号数）。 |
