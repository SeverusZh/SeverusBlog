---
title: 验签部分优化-VERIFY-01
date: 2025-04-08 02:34:53
tags:
  - AVX2
  - Hawk
---

字数：784，阅读时间：4分钟

# 验签部分优化-VERIFY-01

## verify\_inner函数可优化部分解析

由于这段函数太长而且只有一段可优化部分，因此只对这部分做解析。

### **代码逐段解析**

### **循环结构与模数选择**

```c
c
复制
for (int i = 0; i < 2; i++) {
    uint32_t p = (i == 0) ? P1 : P2;// 选择模数P1或P2
    uint32_t p0i = (i == 0) ? P1_0i : P2_0i;// 蒙哥马利模逆参数
    uint32_t R3 = (i == 0) ? P1_R3 : P2_R3;// 蒙哥马利常数R^3 mod p
    uint32_t m16 = (i == 0) ? P1_m16 : P2_m16;// 用于快速模运算的预计算值
    const uint32_t *gm = (i == 0) ? GM_p1 : GM_p2;// NTT生成元数组
```

- **作用**：循环两次，分别使用模数 `P1` 和 `P2`，目的是通过双模数验证范数的有效性。相关参数（如 `p0i`、`R3`、`m16`、`gm`）与模数相关，用于蒙哥马利乘法和NTT转换。

---

### **加载并处理 `t1` 多项式**

```c
/* c2 <- t1 */
if (sig_len == (size_t)-1) {
    memcpy(c2hi, s1, n * sizeof(int16_t));// 直接复制已解码的s1
} else {
    (void)decode_s1(logn, c2hi, s1buf, s1buf_len);// 解码s1到c2hi
}
make_t1(logn, c2hi, h + (n >> 3));// 计算t1 = h1 - 2*s1
mp_poly_to_NTT(logn, c2, c2hi, p, p0i, gm);// 转换为NTT形式
```

- **步骤**：
  1. \*\*解码 `s1`\*\*：若签名未预处理（`sig_len != -1`），需调用 `decode_s1` 解码 `s1` 到 `c2hi`。
  2. \*\*生成 `t1`\*\*：`make_t1` 计算 `t1 = h1 - 2*s1`，其中 `h1` 来自哈希值 `h` 的后半部分。
  3. **NTT转换**：将 `t1` 转换到NTT域，以便后续快速多项式乘法。

---

### **处理公钥多项式 `q00`**

```c
/* c1 <- q00 (auto-adjoint) */
if (pub_len != (size_t)-1) {
    q00 = c1hi;
    (void)decode_q00(logn, q00, q00buf, q00buf_len);// 解码q00
}
mp_poly_to_NTT_autoadj(logn, c1, q00, p, p0i, gm);// 自伴随NTT转换
```

- **关键点**：
  - **自伴随性**：`q00` 是自伴随多项式（`q00 = adj(q00)`），其NTT系数满足对称性。
  - **解码与转换**：若公钥未预处理，需解码 `q00` 并转换到NTT域，利用对称性优化计算。

---

### **蒙哥马利技巧批量求逆**

```c
/* 批量求逆：c1 <- 1/c1 */
uint32_t bx = c1[0];
c1[hn] = bx;
for (size_t u = 1; u < hn; u++) {
    bx = mp_montymul(bx, c1[u], p, p0i);// 累积乘积
    c1[u + hn] = bx;
}
bx = mp_div(1, bx, p, p0i, m16);// 求总乘积的逆元
for (size_t u = hn - 1; u > 0; u--) {
    uint32_t ix = mp_montymul(bx, c1[u + hn - 1], p, p0i);
    bx = mp_montymul(bx, c1[u], p, p0i);
    c1[u] = ix;// 计算单个逆元
}
c1[0] = bx;
```

- **数学原理**：利用关系式 `1/(x*y) = (1/x)*(1/y)`，通过一次全乘积求逆和反向乘法，批量计算多项式中每个元素的逆元。
- **步骤**：
  1. **累积乘积**：将 `c1` 的前 `hn` 个元素依次相乘，结果存储在 `c1` 的后半部分。
  2. **求总逆元**：调用 `mp_div` 计算总乘积的逆元 `bx`。
  3. **反向计算**：从后向前逐个计算每个元素的逆元，利用 `bx` 和已存储的累积乘积。

---

### **计算 `t1/q00` 并累加轨迹**

```c
/* c2 <- c2*c1 = t1/q00; nnacc = Tr_p(t1*adj(t1)/q00) */
uint32_t nnacc = 0;
for (size_t u = 0; u < hn; u++) {
    uint32_t x1 = c2[u], x2 = c2[(n - 1) - u];// 对称位置系数
    uint32_t qx = c1[u];// q00逆的系数
    x1 = mp_montymul(x1, qx, p, p0i);// x1 = t1[u]/q00[u]
    nnacc = mp_add(nnacc, mp_montymul(x1, x2, p, p0i), p);// 累加轨迹
    x2 = mp_montymul(x2, qx, p, p0i);// x2 = t1[n-1-u]/q00[u]
    c2[u] = x1;// 更新c2为t1/q00
    c2[(n - 1) - u] = x2;
}
```

- **操作**：
  - **对称性利用**：因 `q00` 和 `t1` 的对称性，只需计算前 `hn` 个系数。
  - **蒙哥马利乘法**：在模 `p` 下计算 `t1/q00`，并累加轨迹 `Tr(t1*adj(t1)/q00)`。

---

### **处理 `q01` 并构造多项式 `e`**

```c
/* c1 <- q01 */
if (pub_len != (size_t)-1) {
    q01 = c1hi;
    (void)decode_q01(logn, q01, q01buf, q01buf_len);// 解码q01
}
mp_poly_to_NTT(logn, c1, q01, p, p0i, gm);// 转换为NTT形式/* c1 <- c1*c2 = q01*t1/q00 */
for (size_t u = 0; u < n; u++) {
    c1[u] = mp_montymul(mp_montymul(c1[u], c2[u], p, p0i), R3, p, p0i);
}

/* c2 <- t0 */
mp_poly_to_NTT(logn, c2, t0, p, p0i, gm);// t0转换到NTT域/* c2 <- c2 + c1 = t0 + q01*t1/q00 = e */
for (size_t u = 0; u < n; u++) {
    c2[u] = mp_add(c2[u], c1[u], p);// 多项式加法
}
```

- **步骤**：
  1. **解码与转换**：解码 `q01` 并转换到NTT域。
  2. **多项式乘法**：计算 `q01*t1/q00`，结果存储在 `c1`。
  3. \*\*构造 `e`\*\*：将 `t0` 转换到NTT域后，与 `c1` 相加得到 `e = t0 + q01*t1/q00`。

---

### **计算最终范数并验证**

```c
/* c1 <- q00 (auto-adjoint) */
if (pub_len != (size_t)-1) {
    q00 = c1hi;
    (void)decode_q00(logn, q00, q00buf, q00buf_len);
}
mp_poly_to_NTT_autoadj(logn, c1, q00, p, p0i, gm);// 重新加载q00到NTT域/* nnacc += Tr_p(q00*e*adj(e)) */
for (size_t u = 0; u < hn; u++) {
    uint32_t x1 = c2[u], x2 = c2[(n - 1) - u];
    uint32_t qx = c1[u];
    nnacc = mp_add(nnacc, mp_montymul(qx, mp_montymul(x1, x2, p, p0i), p, p0i), p);
}

/* 转换nnacc到普通整数 */
nnacc = mp_montymul(nnacc, R3, p, p0i);

/* 存储结果并检查一致性 */
if (i == 0) {
    tnorm = nnacc;// 第一次结果
} else {
    if (tnorm != nnacc) return 0;// 两次结果必须一致
}
```

- **数学验证**：
  - **最终范数**：`nnacc` 表示 `n*sqnorm_Q(t)/2`，需满足 `(tnorm >> (logn-1)) <= max_tnorm`。
  - **双模数一致性**：两次循环结果必须一致，否则范数超过模数范围，签名无效。

---

### **关键变量与作用**

| **变量/函数** | **类型/操作** | **作用** |
| --- | --- | --- |
| `p`, `P1`, `P2` | `uint32_t` | 模数，用于双模数验证范数。 |
| `mp_montymul` | 蒙哥马利乘法 | 高效计算 `(a*b*R^{-1}) mod p`，避免除法。 |
| `mp_poly_to_NTT` | 多项式NTT转换 | 将多项式转换到NTT域，加速乘法。 |
| `decode_s1`/`decode_q00` | 解码函数 | 从字节流解码多项式 `s1`和 `q00`。 |
| `make_t1` | 计算 `t1 = h1 - 2*s1` | 构造中间多项式 `t1`。 |
| `mp_div` | 蒙哥马利求逆 | 计算模逆元，用于多项式除法。 |
| `nnacc` | `uint32_t` | 累加器，存储范数的模数部分结果。 |
| `R3` | `uint32_t` | 预计算的 `R^3 mod p`，用于调整蒙哥马利乘法结果。 |
