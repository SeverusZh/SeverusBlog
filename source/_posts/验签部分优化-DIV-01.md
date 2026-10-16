---
title: 验签部分优化-DIV-01
date: 2025-03-12 18:26:04
tags:
  - AVX2
  - Hawk
---

## **函数 `mp_div` 逐行分析**

```c
/*
 * Division: return x/y mod p.
 * Parameter m16 is the Montgomery representation of 16 (i.e. 16*R mod p).
 */
static uint32_t
mp_div(uint32_t x, uint32_t y, uint32_t p, uint32_t p0i, uint32_t m16)
{
 /*
  * Binary GCD between y and p:
  * Init:
  *    a <- y
  *    b <- p
  *    u <- x
  *    v <- 0
  * Invariants:
  *    a*x = u*y mod p
  *    b*x = v*y mod p
  *    b is odd
  * Operations:
  *    if a is odd:
  *        if a > b:
  *            (a, b, u, v) <- (b, a, v, u)
  *        (a, u) <- (a - b, u - v mod p)
  *    (a, u) <- (a/2, u/2 mod p)
  * Since p < 2^31, we always reach b = 1 in at most 60 iterations
  * (unless y = 0, in which case b remains equal to p). Then, we
  * have v = x/y mod p.
  * Updates to u and v are delayed: they are accumulated in "update
  * factors" (f0, g0, f1 and g1) and applied every 30 iterations.
  * Moreover, the update factors are themselves held by pairs: we
  * can do 15 iterations with f0 and g0 in the same 32-bit variable
  * (and the same for f1 and g1).
  */
 uint32_t a = y;
 uint32_t b = p;
 uint32_t u = x;
 uint32_t v = 0;
 uint32_t af0 = 0;
 uint32_t ag0 = 0;
 uint32_t af1 = 0;
 uint32_t ag1 = 0;
 for (int i = 0; i < 4; i ++) { //可优化？
  uint32_t fg0 = (uint32_t)1;
  uint32_t fg1 = (uint32_t)1 << 16;
  for (int j = 0; j < 15; j ++) {
   uint32_t a_odd = -(a & 1);
   uint32_t swap = tbmask(a - b) & a_odd;
   uint32_t t1 = swap & (a ^ b);
   a ^= t1;
   b ^= t1;
   uint32_t t2 = swap & (fg0 ^ fg1);
   fg0 ^= t2;
   fg1 ^= t2;
   a -= a_odd & b;
   fg0 -= a_odd & fg1;
   a >>= 1;
   fg1 <<= 1;
  }
  fg0 += 0x7FFF7FFF;
  fg1 += 0x7FFF7FFF;
  uint32_t f0 = (fg0 & 0xFFFF) - (uint32_t)0x7FFF;
  uint32_t g0 = (uint32_t)0x7FFF - (fg0 >> 16);
  uint32_t f1 = (fg1 & 0xFFFF) - (uint32_t)0x7FFF;
  uint32_t g1 = (uint32_t)0x7FFF - (fg1 >> 16);

  /*
   * We apply update factors only once every two outer
   * iterations. af0, ag0... are the factors from the
   * previous round. The aggregate factors (for two rounds)
   * are thus:
   *   bf0 = af0*f0 - af1*g0
   *   bg0 = ag0*f0 - ag1*g0
   *   bf1 = af0*f1 - af1*g1
   *   bg1 = ag0*f1 - ag1*g1
   * The aggregate update factors are, in fact, exactly the
   * value we would obtain from running 30 inner iterations,
   * so they follow the rules explained in:
   *    https://eprint.iacr.org/2020/972
   * In particular, these factors are at most 2^30 in
   * absolute value. Thus, they do not overflow and we can
   * use them with mp_lin().
   */

  if ((i & 1) == 0) {
   af0 = f0;
   ag0 = g0;
   af1 = f1;
   ag1 = g1;
  } else {
   uint32_t bf0 = af0*f0 - af1*g0;
   uint32_t bg0 = ag0*f0 - ag1*g0;
   uint32_t bf1 = af0*f1 - af1*g1;
   uint32_t bg1 = ag0*f1 - ag1*g1;
   uint32_t nu = mp_lin(u, v, bf0, bg0, p, p0i);
   uint32_t nv = mp_lin(u, v, bf1, bg1, p, p0i);
   u = nu;
   v = nv;
  }
 }

 /*
  * Each inner loop computed the update factors with an implicit
  * 2^15 factor; two inner iteration lead to a 2^30 factor, but
  * mp_lin() divided by R = 2^32. In total, we divided by (2^2)^2,
  * which we must compensate here by multiplying by 16.
  */
 v = mp_montymul(v, m16, p, p0i);

 /* GCD is in b; it is 1 if and only if y was invertible.
    Otherwise, the GCD is greater than 1. */
 return v & tbmask(b - 2);
}
```

## **函数声明**

```c
c
static uint32_t
mp_div(uint32_t x, uint32_t y, uint32_t p, uint32_t p0i, uint32_t m16)
```

- **参数**：
  - `x`: 被除数（分子）
  - `y`: 除数（分母）
  - `p`: 模数（质数）
  - `p0i`: 用于快速模约减的预计算值（`1/p mod 2^32`）
  - `m16`: 用于Montgomery乘法后的校正因子（`16 mod p`）
- **返回值**：`x/y mod p`（若 `y` 可逆），否则返回 `0`。

---

## **初始化变量**

```c
c
uint32_t a = y;
uint32_t b = p;
uint32_t u = x;
uint32_t v = 0;
uint32_t af0 = 0;
uint32_t ag0 = 0;
uint32_t af1 = 0;
uint32_t ag1 = 0;
```

- **变量含义**：
  - `a`, `b`: 扩展二进制GCD的初始值（`a = y`, `b = p`）
  - `u`, `v`: 跟踪线性组合系数，初始化为 `u = x`, `v = 0`
  - `af0`, `ag0`, `af1`, `ag1`: 延迟更新因子（用于合并多次操作）

---

## **外层循环（4次）**

```c
c
for (int i = 0; i < 4; i ++) {
// 内部处理
}
```

- **目的**：总共有60次内层迭代（4次外层循环 × 15次内层循环），确保在 `p < 2^31` 时终止。

---

## **内层循环（15次）**

```c
c
uint32_t fg0 = (uint32_t)1;
uint32_t fg1 = (uint32_t)1 << 16;
for (int j = 0; j < 15; j ++) {
// 条件交换和更新操作
}
```

- **变量含义**：
  - `fg0`, `fg1`: 合并的更新因子（低16位和高16位分别存储 `f` 和 `g`）

---

## **条件交换逻辑**

```c
c
uint32_t a_odd = -(a & 1);// 若a为奇数则全1，否则全0
uint32_t swap = tbmask(a - b) & a_odd;// 若a > b且a为奇数则交换
uint32_t t1 = swap & (a ^ b);// 交换a和b
a ^= t1;
b ^= t1;
uint32_t t2 = swap & (fg0 ^ fg1);// 交换fg0和fg1
fg0 ^= t2;
fg1 ^= t2;
```

- **目的**：若 `a` 为奇数且 `a > b`，则交换 `a` 与 `b`，并同步交换 `fg0` 和 `fg1`。
- \*\*函数 `tbmask`\*\*：返回 `a >= b ? 0xFFFFFFFF : 0`。

---

## **更新 `a` 和 `fg0`**

```c
c
a -= a_odd & b;// 若a为奇数，则a = a - b
fg0 -= a_odd & fg1;// 对应更新fg0
a >>= 1;// a除以2
fg1 <<= 1;// 左移1位（对应除以2的延迟补偿）
```

- **操作逻辑**：若 `a` 为奇数，则执行减法并右移，同时调整因子。

---

## **分解合并因子**

```c
c
fg0 += 0x7FFF7FFF;
fg1 += 0x7FFF7FFF;
uint32_t f0 = (fg0 & 0xFFFF) - 0x7FFF;
uint32_t g0 = 0x7FFF - (fg0 >> 16);
uint32_t f1 = (fg1 & 0xFFFF) - 0x7FFF;
uint32_t g1 = 0x7FFF - (fg1 >> 16);
```

- **目的**：将合并的因子 `fg0` 和 `fg1` 拆分为独立的 `f0, g0` 和 `f1, g1`，用于后续线性组合。

---

## **应用延迟更新**

```c
c
if ((i & 1) == 0) {
    af0 = f0; ag0 = g0; af1 = f1; ag1 = g1;
} else {
// 合并两次的因子并更新u和v
    uint32_t bf0 = af0*f0 - af1*g0;
    uint32_t bg0 = ag0*f0 - ag1*g0;
    uint32_t bf1 = af0*f1 - af1*g1;
    uint32_t bg1 = ag0*f1 - ag1*g1;
    u = mp_lin(u, v, bf0, bg0, p, p0i);// u = (u*bf0 + v*bg0) mod p
    v = mp_lin(u, v, bf1, bg1, p, p0i);// v = (u*bf1 + v*bg1) mod p
}
```

- \*\*函数 `mp_lin`\*\*：计算 `(a*f + b*g) mod p`，使用快速模约减（依赖 `p0i`）。

---

## **最终校正**

```c
c
v = mp_montymul(v, m16, p, p0i);// 应用Montgomery校正
return v & tbmask(b - 2);// 若b != 1则返回0
```

- **目的**：
  - `mp_montymul(v, m16, p, p0i)`：将结果从Montgomery形式转换回标准模数。
  - `tbmask(b - 2)`：若 `b != 1`（即 `y` 不可逆），则返回 `0`。

---

## **关键变量总结**

| **变量** | **含义** |
| --- | --- |
| `a`, `b` | 扩展GCD的当前值，初始为 `y` 和 `p` |
| `u`, `v` | 跟踪线性组合系数，最终 `v = x/y mod p` |
| `fg0`, `fg1` | 合并的更新因子（低16位和高16位） |
| `af0`, `ag0` | 前一次的更新因子（用于合并两次操作） |
| `m16` | Montgomery乘法校正因子（`16 mod p`） |
| `p0i` | 快速模约减的预计算值（`-1/p mod 2^32`） |

该函数通过扩展二进制GCD算法和延迟更新策略高效计算模数除法，并确保结果在 `y` 不可逆时返回 `0`。

---

该函数实现了模数除法 *x*/*y*mod*p*，其核心原理基于优化的二进制GCD算法，结合延迟更新策略以提升效率。以下为详细原理分析：

---

## **1. 算法基础：扩展二进制GCD**

- **目标**：计算 *x*⋅*y*−1mod*p*，即找到 *v* 使得 *v*⋅*y*≡*x*mod*p*。
- **初始化**：
  - *a*=*y*, *b*=*p*
  - *u*=*x*, *v*=0
- **不变量**：
  - *a*⋅*x*≡*u*⋅*y*mod*p*
  - *b*⋅*x*≡*v*⋅*y*mod*p*
  - *b* 始终为奇数（通过操作保证）。

---

## **2. 关键操作步骤**

## **步骤1：交换与减法**

- **条件**：若 *a* 为奇数且 *a*>*b*，则交换 *a* 和 *b*，同时交换对应的系数 *u* 和 *v*。

- **操作**：保证 *a* 变为偶数。

  ```c
  c
  a = a - b;
  u = (u - v) \mod p;
  ```

## **步骤2：除以2**

- 若 *a* 为偶数，则：由于 *p* 为奇数，2 的逆元存在，但实际通过延迟因子处理。

  ```c
  c
  a = a / 2;
  u = u / 2 \mod p;
  ```

---

## **3. 延迟更新策略**

- **目的**：减少模运算次数，将多次迭代的系数调整累积后批量应用。
- **实现**：
  - **合并因子**：每15次迭代将系数 *f* 和 *g* 合并到 `fg0` 和 `fg1` 的高低16位中。
  - **批量应用**：每30次迭代（外层循环两次）通过 `mp_lin` 函数更新 *u* 和 *v*：
      ```c
      c
      u = (u \cdot bf0 + v \cdot bg0) \mod p;
      v = (u \cdot bf1 + v \cdot bg1) \mod p;
      ```

---

## **4. 最终校正与结果处理**

- **Montgomery校正**：

  ```c
  c
  v = mp_montymul(v, m16, p, p0i);
  ```

  将延迟更新引入的缩放因子 230 转换为标准模数，通过乘以 16mod*p* 校正。

- **结果验证**：

  - 若 *b*=1（即 *y* 可逆），返回 *v*。
  - 若 *b*=1（*y* 与 *p* 不互质），返回 0（通过掩码 `tbmask(b - 2)` 实现）。

---

## **5. 数学原理验证**

- **不变量保持**：每次操作确保 *a*⋅*x*≡*u*⋅*y*mod*p* 和 *b*⋅*x*≡*v*⋅*y*mod*p*。
- **终止条件**：当 *b*=1 时，*v*⋅*y*≡*x*mod*p*，故 *v*=*x*/*y*mod*p*。

---

## **6. 变量与函数作用总结**

| **变量/函数** | **作用** |
| --- | --- |
| `a`, `b` | 跟踪GCD进程，初始为*y* 和 *p*。 |
| `u`, `v` | 维护线性组合系数，最终*v* 为所求结果。 |
| `fg0`, `fg1` | 合并的延迟因子，高低16位分别存储*f* 和 *g*。 |
| `mp_lin` | 应用累积因子更新*u* 和 *v*。 |
| `mp_montymul` | Montgomery乘法校正，消除延迟因子引入的缩放。 |
| `tbmask` | 生成条件掩码，用于判断交换条件和结果有效性。 |

---

## **7. 性能优化点**

- **延迟更新**：减少模运算次数，每30次迭代批量应用因子。
- **位操作优化**：利用掩码和位运算避免分支预测失败，提升速度。
- **合并变量**：通过高低位存储因子，节省内存和计算步骤。

该算法在保证正确性的前提下，通过二进制GCD的高效性和延迟更新策略，显著提升了模数除法的计算效率。

## AVX2优化点

这是一个相当成熟的模运算算法而且因为a和b的值不可预测且与前一次循环有联系很难并行化。但在更上层可能要多次调用多个函数，彼时可能存在需要将该函数改为x8形式，将所有变量变为256位变量并将运算换为AVX2运算。比如在 `ng_ntru.c`的 `recover_G`函数中：

```c
/* see ng_inner.h */
int
recover_G(unsigned logn, int32_t q, uint32_t ulim,
 const int8_t *restrict f, const int8_t *restrict g,
 const int8_t *restrict F, uint32_t *restrict tmp)
{
 size_t n = (size_t)1 << logn;
 uint32_t *gm = tmp;
 uint32_t *t1 = gm + n;
 uint32_t *t2 = t1 + n;
 ...
 for (size_t u = 0; u < n; u ++) {
  b |= t1[u] - 1;
  t2[u] = mp_div(t2[u], t1[u], p);
 }
 ...
}
```

此处的循环若将步长设为8，就可以使用 `mp_div_x8`的形式来减少运算量了。
