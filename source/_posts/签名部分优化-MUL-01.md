---
title: 签名部分优化-MUL-01
date: 2025-02-27 19:07:49
updated: 2025-03-03
tags:
  - AVX2
  - Hawk
---

## 函数介绍

在该部分代码中存在着两个乘法辅助函数，其计算也是可并行化的，分别是 `bp_mul_32` 和 `bp_muladd_64` 。

```c
static uint64_t
bp_mul_32(uint32_t x, uint32_t y)
{
 /*
  * Classic technique (rediscovered many times): integer
  * multiplications with "holes" to absorb unwanted carries.
  */
 uint32_t x0 = x & 0x11111111;
 uint32_t x1 = x & 0x22222222;
 uint32_t x2 = x & 0x44444444;
 uint32_t x3 = x & 0x88888888;

 uint32_t y0 = y & 0x11111111;
 uint32_t y1 = y & 0x22222222;
 uint32_t y2 = y & 0x44444444;
 uint32_t y3 = y & 0x88888888;

#define M(a, b)   ((uint64_t)(a) * (uint64_t)(b))

 uint64_t z0 = M(x0, y0) ^ M(x1, y3) ^ M(x2, y2) ^ M(x3, y1);
 uint64_t z1 = M(x0, y1) ^ M(x1, y0) ^ M(x2, y3) ^ M(x3, y2);
 uint64_t z2 = M(x0, y2) ^ M(x1, y1) ^ M(x2, y0) ^ M(x3, y3);
 uint64_t z3 = M(x0, y3) ^ M(x1, y2) ^ M(x2, y1) ^ M(x3, y0);

#undef M

 z0 &= (uint64_t)0x1111111111111111;
 z1 &= (uint64_t)0x2222222222222222;
 z2 &= (uint64_t)0x4444444444444444;
 z3 &= (uint64_t)0x8888888888888888;
 return z0 | z1 | z2 | z3;
}

static void
bp_muladd_64(uint8_t *restrict d, const uint8_t *restrict a,
 const uint8_t *restrict b, uint8_t *restrict tmp)
{
 (void)tmp;

 uint32_t a0 = dec32le(a);
 uint32_t a1 = dec32le(a + 4);
 uint32_t b0 = dec32le(b);
 uint32_t b1 = dec32le(b + 4);

 uint64_t c0 = bp_mul_32(a0, b0);
 uint64_t c1 = bp_mul_32(a1, b1);
 uint64_t c2 = bp_mul_32(a0 ^ a1, b0 ^ b1) ^ c0 ^ c1;

 enc64le(d, dec64le(d) ^ c0 ^ (c2 << 32));
 enc64le(d + 8, dec64le(d + 8) ^ c1 ^ (c2 >> 32));
}
```

`bp_mul_32` 相对比较好理解，本质是一个先与掩码做与运算，再计算部分积的异或结果，最后再应用一次掩码的过程，而 `bp_muladd_64` 写的就比较难以理解了。

通过查询官方文档和上网搜索后，我们了解到：`bp_muladd_64` 用于计算两个 **64位二进制多项式** 的乘积，并将结果累加到目标数组 `d` 中。二进制多项式的乘法在密码学中常用于基于环的运算（如NTRU算法），其核心是通过 **异或（XOR）** 和 **按位与（AND）** 操作实现多项式系数的组合。

### 原始代码解析

`bp_muladd_64`原始代码的实现步骤如下：

1. **输入分解**：
   - 将输入的 `a` 和 `b` 各分为两个32位块：`a0`（低32位）、`a1`（高32位），`b0`（低32位）、`b1`（高32位）。
   - 例如：`a = a0 | (a1 << 32)`，`b = b0 | (b1 << 32)`。
2. **部分乘积计算**：
   - 计算四个部分积：
     - `c0 = a0 * b0`（低32位乘积）
     - `c1 = a1 * b1`（高32位乘积）
     - `c2 = (a0 ^ a1) * (b0 ^ b1)`（交叉项的乘积）
3. **结果组合**：
   - 通过异或操作合并部分积：
     - `c0` 和 `c2` 的低32位组合到结果的低64位。
     - `c1` 和 `c2` 的高32位组合到结果的高64位。
4. **累加到目标数组**：
   - 将最终结果异或到目标数组 `d` 中。

显然原始代码在不使用AVX2指令集的情况下也使用了一些优化技巧，但在使用AVX2指令集优化的情况下将舍弃这些技巧，因此不再赘述。

### 性能影响

这里出现了两个函数 `dec32le` 和 `enc64le` ，在这里做一些介绍。

- `dec32le` 函数通常用于将一个 32 位的整数从小端字节序（Little-Endian）转换为大端字节序（Big-Endian），或者反过来。在许多计算机系统中，数据是以小端字节序存储的，但在网络传输或其他特定协议中，可能需要使用大端字节序。因此，这种函数在处理不同系统之间的数据传输时非常有用。需要注意的是，`dec32le` 并不是标准C库中的函数，它可能是某个特定库或代码中的自定义函数，作用是进行32位整数的字节序转换。
- `enc64le` 函数的作用是将一个 64 位的整数以小端字节序（Little-Endian）的形式编码到指定的内存地址中。小端字节序是指在内存中，最低有效字节（Least Significant Byte, LSB）存储在最低的地址，而最高有效字节（Most Significant Byte, MSB）存储在最高的地址。具体来说，`enc64le` 函数的参数通常包括一个指向目标内存地址的指针和一个 64 位的整数。函数会将这个 64 位整数按照小端字节序写入到指定的内存地址。

容易发现，`dec32le`和 `enc64le` 都是对内存的访问操作，而频繁的 `dec32le` 和 `enc64le` 操作可能引入内存访问延迟。

## 优化代码

在第一份优化代码编写完后，我认为从逻辑上第一份代码并没有使用到AVX2可处理256位向量的优势，所以只能推迟 `bp_muladd_64` 的优化，今天只能完成 `bp_mul_32` 的优化工作。

```c
/*第一份代码*/
static uint64_t bp_mul_32(uint32_t x, uint32_t y) {
    __m256i x_vec = _mm256_set1_epi32(x);  // 将x广播到256位向量
    __m256i y_vec = _mm256_set1_epi32(y);  // 将y广播到256位向量

    // 掩码
    __m256i mask0 = _mm256_set1_epi32(0x11111111);
    __m256i mask1 = _mm256_set1_epi32(0x22222222);
    __m256i mask2 = _mm256_set1_epi32(0x44444444);
    __m256i mask3 = _mm256_set1_epi32(0x88888888);

    // 提取x和y的位
    __m256i x0 = _mm256_and_si256(x_vec, mask0);
    __m256i x1 = _mm256_and_si256(x_vec, mask1);
    __m256i x2 = _mm256_and_si256(x_vec, mask2);
    __m256i x3 = _mm256_and_si256(x_vec, mask3);

    __m256i y0 = _mm256_and_si256(y_vec, mask0);
    __m256i y1 = _mm256_and_si256(y_vec, mask1);
    __m256i y2 = _mm256_and_si256(y_vec, mask2);
    __m256i y3 = _mm256_and_si256(y_vec, mask3);

    // 计算部分积
    __m256i z0 = _mm256_xor_si256(
        _mm256_mullo_epi32(x0, y0),
        _mm256_xor_si256(
            _mm256_mullo_epi32(x1, y3),
            _mm256_xor_si256(
                _mm256_mullo_epi32(x2, y2),
                _mm256_mullo_epi32(x3, y1)
            )
        )
    );

    __m256i z1 = _mm256_xor_si256(
        _mm256_mullo_epi32(x0, y1),
        _mm256_xor_si256(
            _mm256_mullo_epi32(x1, y0),
            _mm256_xor_si256(
                _mm256_mullo_epi32(x2, y3),
                _mm256_mullo_epi32(x3, y2)
            )
        )
    );

    __m256i z2 = _mm256_xor_si256(
        _mm256_mullo_epi32(x0, y2),
        _mm256_xor_si256(
            _mm256_mullo_epi32(x1, y1),
            _mm256_xor_si256(
                _mm256_mullo_epi32(x2, y0),
                _mm256_mullo_epi32(x3, y3)
            )
        )
    );

    __m256i z3 = _mm256_xor_si256(
        _mm256_mullo_epi32(x0, y3),
        _mm256_xor_si256(
            _mm256_mullo_epi32(x1, y2),
            _mm256_xor_si256(
                _mm256_mullo_epi32(x2, y1),
                _mm256_mullo_epi32(x3, y0)
            )
        )
    );

    // 应用掩码
    z0 = _mm256_and_si256(z0, _mm256_set1_epi64x(0x1111111111111111));
    z1 = _mm256_and_si256(z1, _mm256_set1_epi64x(0x2222222222222222));
    z2 = _mm256_and_si256(z2, _mm256_set1_epi64x(0x4444444444444444));
    z3 = _mm256_and_si256(z3, _mm256_set1_epi64x(0x8888888888888888));

    // 合并结果
    __m256i result = _mm256_or_si256(
        _mm256_or_si256(z0, z1),
        _mm256_or_si256(z2, z3)
    );

    // 提取低64位
    return _mm256_extract_epi64(result, 0);
}
```

关注一下原始代码的逻辑，在运算z0~z3时，其进行运算实质上可以概括为

```c
z_k = M(x0, y_{(0 + k) \mod 4}) ^ M(x1, y_{(3 + k) \mod 4}) ^ M(x2, y_{(2 + k) \mod 4}) ^ M(x3, y_{(1 + k) \mod 4})
```

因此我可以实现直接将扩展后的 `x_vec`和 `y_vec`先交换索引为1和3的两个64位整数相乘后再交换回来循环左移重复来完成这一部分的计算。这里我使用函数\*\*`_mm256_permute4x64_epi64`\*\* 来完成这一点。

- `_mm256_permute4x64_epi64` 的第二个参数是一个 8 位的控制掩码（control mask），用于指定如何重排 4 个 64 位整数。

- 控制掩码 `0b10010011` 的二进制表示如下：

  - 第 0 位和第 1 位：`11`，表示目标位置 0 使用源位置 3（即 `D`）。
  - 第 2 位和第 3 位：`00`，表示目标位置 1 使用源位置 0（即 `A`）。
  - 第 4 位和第 5 位：`01`，表示目标位置 2 使用源位置 1（即 `B`）。
  - 第 6 位和第 7 位：`10`，表示目标位置 3 使用源位置 2（即 `C`）。

  因此，`0b10010011` 将 `[A, B, C, D]` 重排为 `[B, C, D, A]`。

避免多余操作，我第一次使用控制掩码 `0b01101100`，以后每次使用控制掩码 `0b10010011` 即可。

接下来我直接将 `x_vec`和 `y_vec`相乘，然后内部进行异或，就能得到z0~z3。由于我们设计的\_\_m256i变量中索引为1、3、5、7的32位整数总为0，所以可以直接使用 `_mm256_mul_epu32` 指令，它会将高位进位保留到我们预留的位置。

此外，为了实现\_\_m256i变量的快速内部64位异或，我编写了一个辅助函数，实现内部的水平异或。

```c
uint64_t xor_all_64bit_elements_optimized(__m256i vec) {
    // 将高 128 位和低 128 位异或
    __m256i temp = _mm256_xor_si256(vec, _mm256_permute4x64_epi64(vec, 0b01001110));
    // 将结果的低 128 位中的两个 64 位整数异或
    __m128i low = _mm256_castsi256_si128(temp);
    uint64_t result = _mm_extract_epi64(low, 0) ^ _mm_extract_epi64(low, 1);
    return result;
}

```

```c
static uint64_t bp_mul_32(uint32_t x, uint32_t y) {
    __m256i x_vec = _mm256_set1_epi32(x);  // 将x广播到256位向量
    __m256i y_vec = _mm256_set1_epi32(y);  // 将y广播到256位向量

    // 掩码
    __m256i mask = _mm256_set_epi32(
        0x00000000,0x88888888,0x00000000,0x44444444,
        0x00000000,0x22222222,0x00000000,0x11111111
    );

    x_vec = _mm256_and_si256(x_vec, mask);  // 掩码x
    y_vec = _mm256_and_si256(y_vec, mask);  // 掩码y

 // 计算部分积
    y_vec = _mm256_permute4x64_epi64(y_vec, 0b01101100);  // 交换y的第二个64位和第四个64位
    uint64_t z0 = xor_all_64bit_elements_optimized(_mm256_mul_epu32(x_vec, y_vec));
 y_vec = _mm256_permute4x64_epi64(y_vec, 0b10010011);
    uint64_t z1 = xor_all_64bit_elements_optimized(_mm256_mul_epu32(x_vec, y_vec));
 y_vec = _mm256_permute4x64_epi64(y_vec, 0b10010011);
    uint64_t z2 = xor_all_64bit_elements_optimized(_mm256_mul_epu32(x_vec, y_vec));
 y_vec = _mm256_permute4x64_epi64(y_vec, 0b10010011);
    uint64_t z3 = xor_all_64bit_elements_optimized(_mm256_mul_epu32(x_vec, y_vec));
    __m256i z_mask = _mm256_set_epi32(
        0x88888888,0x88888888,0x44444444,0x44444444,
        0x22222222,0x22222222,0x11111111,0x11111111
    );

    __m256i z_vec = _mm256_set_epi64x(z3, z2, z1, z0);  // 合并结果
    z_vec = _mm256_and_si256(z_vec, z_mask);  // 掩码结果

    return xor_all_64bit_elements_optimized(z_vec);  // 计算结果
    }
```
