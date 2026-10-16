---
title: 签名部分优化-ENCODE-02
date: 2025-03-09 17:11:17
tags:
  - AVX2
  - Hawk
---

## 提取符号位

首先我们在源代码中很容易找到下面这一段循环。

```c
for (size_t u = 0; u < n; u += 8) {
 unsigned x = 0;
 for (size_t v = 0; v < 8; v ++) {
  x |= (*(const uint16_t *)(s1 + u + v) >> 15) << v;
 }
 buf[u >> 3] = x;
}
```

**含义**：提取 `s1`数组中每个元素的符号位（最高位），每8个符号位组合成一个字节，存入缓冲区。

而我们的优化思路是这样的：AVX2指令集的右移指令最小操作单元是32位整数，但我们的操作对象是16位有符号整数，因此我们要把16位有符号整数零扩展为32位无符号整数来提取其符号位。又因为我们后面的处理中要将8个符号位拼接成为一个字节，所以我们在右移时可以采用可变右移指令，使每个32位的右移位数递减，然后与预设好的掩码相与，最后通过32位无符号整型指针读取内存得到一个大小为8的32位无符号整型数组并彼此相或得到最终结果。

零扩展代码如下：

```c
__m256i load_8x16bits_zero_extend(int16_t* data) {
 __m128i vec128 = _mm_loadu_si128((const __m128i*)data); // 加载8个16位整数
 return _mm256_cvtepu16_epi32(vec128);                   // 零扩展为32位
}
```

优化后代码如下：

```c
uint32_t shifts[8] = {15, 14, 13, 12, 11, 10, 9, 8}; //右移位数
 uint32_t shifts_mask[8] = {0x1, 0x2, 0x4, 0x8, 0x10, 0x20, 0x40, 0x80}; //取位掩码
 __m256i count = _mm256_loadu_si256((__m256i*)shifts);
 __m256i calc_mask = _mm256_loadu_si256((__m256i*)shifts_mask);
 for (size_t u = 0; u < n; u += 8) {
  __m256i avx2_256_temp = load_8x16bits_zero_extend((__m256i *)(s1+u));
  avx2_256_temp = _mm256_and_si256(_mm256_srlv_epi32(avx2_256_temp,count), calc_mask);
  uint32_t *calc =  (uint32_t*)& avx2_256_temp; // 此处转换并不安全，如果运行出错可以使用union结构体尝试修改
  unsigned x = calc[0] | calc[1] | calc[2] | calc[3] | calc[4] | calc[5] | calc[6] | calc[7];
  buf[u >> 3] = x;
 }
```

这里需要注意的是。通过32位指针访问256位内存从原理上来说是**不安全的**，可能违反严格别名规则，不过 `__m256i`其实可以看作是`char`的一种别名，被编译器许可，因此这种技巧又是很常用的，更安全的方式是使用 `union`结构体或者 `memcpy`指令，但都会造成一定程度上的性能损失和空间浪费。

## 固定低位提取

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

这里我们又重新走了一遍循环，可以看到整体的逻辑其实和提取符号位时的逻辑差不多，区别只在于提取的是低5位，每次循环提取8个16位有符号整数的低5位，并合成40位存储到一个64位无符号整型变量中。优化后代码如下：

```c
__m256i load_8x16bits_sign_extend(int16_t* data) {
 __m128i vec128 = _mm_loadu_si128((const __m128i*)data); // 加载8个16位整数
 return _mm256_cvtepi16_epi32(vec128);                   // 符号扩展为32位
}1
...
uint32_t low_mask = ((uint32_t)1 << low) - 1;//low=5
 __m256i avx2_256_low_mask = _mm256_set1_epi32(low_mask);
 for (size_t u = 0; u < n; u += 8) {
  uint64_t x = 0;
  __m256i avx2_256_temp = load_8x16bits_zero_extend((__m256i *)(s1+u));
  //补充一个tbmask,还没写
  __m256i avx2_256_temp_low = _mm256_and_si256(avx2_256_temp,avx2_256_low_mask);
  uint32_t *calc =  (uint32_t*)& avx2_256_temp_low; // 此处转换并不安全，如果运行出错可以使用union结构体尝试修改
  x = calc[0] | (calc[1] << 5) | (calc[2] << 10) | (calc[3] << 15) | (calc[4] << 20) | (calc[5] << 25) | (calc[6] << 30) | (calc[7] << 35);
  for (int i = 0; i < (low << 3); i += 8) {
   *buf ++ = (uint8_t)(x >> i);
  }
 }
```

与提取符号位不同的是，这里我们需要进行符号扩展，这是和后面的计算有关的，源代码中 `int16`扩展到 `uint32`时也是进行了符号扩展，不然后面的 `tbmask`将失去作用。

大家可能注意到，中间我特意留出一部分来做 `tbmask`处理，这也是和提取符号位时有些区别的地方我们先来看 `tbmask`是什么：

```c
static inline uint32_t
tbmask(uint32_t x)
{
 return (uint32_t)(*(int32_t *)&x >> 31);
}
```

这段代码的作用是根据输入的无符号整数 `x` 的最高位（符号位）生成一个掩码。具体来说：

1. **类型转换**：`(int32_t *)&x` 将 `x` 的地址强制转换为 `int32_t` 指针，并解引用它，将 `x` 的二进制位解释为有符号整数。这一步利用类型双关（type punning）直接操作内存中的位模式。
2. **算术右移**：`>> 31` 对有符号整数进行算术右移。如果最高位是 `1`（负数），右移 31 位后结果为 `1`（二进制全 `1`）；如果最高位是 `0`（正数），结果为 `0`。
3. **转换为无符号**：最终将结果转换为 `uint32_t`。若原最高位是 `1`，返回 `0xFFFFFFFF`（全 `1` 掩码）；若是 `0`，返回 `0x00000000`。

**功能总结**：函数生成一个掩码，当输入 `x` 的最高位为 `1` 时返回全 `1`，否则返回全 `0`。这种掩码常用于位操作中，例如条件选择或无分支代码优化。

为什么我暂时没有在优化后的代码中完成这一部分呢，首先我们知道，我们将这些整数想办法合成位256进行操作时，一般来说不好再分开提取作判别了，一般都要对4/8个项作统一的处理，二提取符号位的操作我们已经做过了，所以，无论是从对代码逻辑的整体优化还是从方便再利用的角度来看，将符号位提取和低位提取融合才是更好的选择。

以下是优化后的 `tbmask`处理：

```c
/*先比较处理后的sign是不是0，如果是则置32位全1，反之全0，随后通过与-1异或的方式按位取反，最后再与自身异或。*/
  avx2_256_temp_low = _mm256_xor_si256(_mm256_xor_si256(_mm256_cmpeq_epi32(avx2_256_temp_sign,_mm256_setzero_si256()),_mm256_set1_epi32(-1)),avx2_256_temp_low);
```

这里的处理相对比较复杂，但其实比较好理解，首先通过之前在GAUSS函数就使用过的 `cmpeq`函数来判断 `avx2_256_temp_sign` 的每个32位是不是全0，此时已经是与取位掩码异或过的状态，因此只要符号位是1就会被置全0，反之置全1。但是我们的要求与此恰好相反，只能按位取反，由于无法直接对256位变量按位取反，我们采用与全1的的256位变量（即每个32位取值是-1）进行异或来按位取反，这一过程非常快，与按位取反相比性能几乎没有差异，最后再与 `avx2_256_temp_low`自身异或即可。

以下是融合后的循环结构，注意buf要重新计算。

```c
uint32_t shifts[8] = {15, 14, 13, 12, 11, 10, 9, 8}; //右移位数
uint32_t shifts_mask[8] = {0x1, 0x2, 0x4, 0x8, 0x10, 0x20, 0x40, 0x80}; //取位掩码
__m256i count = _mm256_loadu_si256((__m256i*)shifts);
__m256i calc_mask = _mm256_loadu_si256((__m256i*)shifts_mask);
__m256i avx2_256_low_mask = _mm256_set1_epi32(((uint32_t)1 << low) - 1);
for (size_t u = 0; u < n; u += 8) {
 uint64_t low_combined_40 = 0;
 unsigned sign_combined_8 = 0;
 __m256i avx2_256_temp_zero_extend = load_8x16bits_zero_extend((__m256i *)(s1+u));
 __m256i avx2_256_temp_sign_extend = load_8x16bits_sign_extend((__m256i *)(s1+u));
 __m256i avx2_256_temp_sign = _mm256_and_si256(_mm256_srlv_epi32(avx2_256_temp_zero_extend,count), calc_mask);
 __m256i avx2_256_temp_low = _mm256_and_si256(avx2_256_temp_sign_extend,avx2_256_low_mask);//这里要进行符号扩展，否则后面的运算会出错
 /*先比较处理后的sign是不是0，如果是则置32位全1，反之全0，随后通过与-1异或的方式按位取反，最后再与自身异或。*/
 avx2_256_temp_low = _mm256_xor_si256(_mm256_xor_si256(_mm256_cmpeq_epi32(avx2_256_temp_sign,_mm256_setzero_si256()),_mm256_set1_epi32(-1)),avx2_256_temp_low);
 uint32_t *calc_sign =  (uint32_t*)& avx2_256_temp_sign; // 此处转换并不安全，如果运行出错可以使用union结构体尝试修改
 uint32_t *calc_low =  (uint32_t*)& avx2_256_temp_low;
 sign_combined_8 = calc_sign[0] | calc_sign[1] | calc_sign[2] | calc_sign[3] | calc_sign[4] | calc_sign[5] | calc_sign[6] | calc_sign[7];
 low_combined_40 = calc_low[0] | (calc_low[1] << 5) | (calc_low[2] << 10) | (calc_low[3] << 15) | (calc_low[4] << 20) | (calc_low[5] << 25) | (calc_low[6] << 30) | (calc_low[7] << 35);
 buf[u >> 3] = sign_combined_8;
 for (int i = 0, j = 0; i < (low << 3); i += 8, j++) {
  buf[u + j + 32] = (uint8_t)(low_combined_40 >> i);
 }
}
buf += (n >> 3) + (size_t)low << (logn - 3); //low << (logn - 3)其实就是 low * (n/8) 算循环次数也能算出来的
buf_len -= (n >> 3) + (size_t)low << (logn - 3);
```

## 处理高位部分

先看源代码

```c
uint32_t acc = 0;
int acc_len = 0;
size_t j = 0;//神人代码发力了，j的作用是什么？
for (size_t u = j; u < n; u ++) { //可并行化
 uint32_t w = (uint32_t)s1[u];
 int k = (int)((w ^ tbmask(w)) >> low);
 acc |= (uint32_t)1 << (acc_len + k);
 acc_len += 1 + k;
 while (acc_len >= 8) {
  if (buf_len == 0) {
   return 0;
  }
  *buf ++ = (uint8_t)acc;
  buf_len --;
  acc >>= 8;
  acc_len -= 8;
 }
}
if (acc_len > 0) {
 if (buf_len == 0) {
  return 0;
 }
 *buf ++ = (uint8_t)acc;
 buf_len --;
}
```

**含义**：将高位部分编码为一元码，累积到 `acc`中，每满8位写入一个字节。
 我一开始以为这里能够优化，但最后发现不行，原因如下：

**代码逻辑分析**

1. **核心操作**：逐字节处理输入数据，根据 `w ^ tbmask(w)`计算偏移量 `k`，将结果位动态写入 `acc`缓冲区，并在 `acc`填满8位时输出到 `buf`。
2. **关键依赖**：
   - `acc`和 `acc_len`是累积变量，每次循环更新都依赖前一次结果（数据依赖）。
   - `k`的值动态变化，导致 `acc_len`的增量不固定（控制流依赖）。

---

**AVX2并行化的难点**

1. **数据依赖限制**
   - `acc`和 `acc_len`的串行更新无法直接向量化。例如，第 `u+1`次迭代的 `acc`值完全依赖第 `u`次的结果。
   - `k`的动态性导致无法预知每个字符的位偏移量，难以批量处理多个字符的位填充操作。
2. **动态位操作的限制**
   - AVX2指令集对**非对齐位操作**支持有限，例如无法直接模拟 `acc |= (uint32_t)1 << (acc_len + k)`这类动态位移操作。
3. **分支与缓冲区管理**
   - 代码中的 `while (acc_len >= 8)`分支会破坏SIMD的流水线连续性，且 `buf`的写入需要处理动态缓冲区长度。

---

至此，签名部分已基本完成优化了。
