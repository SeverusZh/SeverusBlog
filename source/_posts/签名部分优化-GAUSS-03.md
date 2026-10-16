---
title: 签名部分优化-GAUSS-03
date: 2025-02-27 19:08:15
updated: 2025-03-03
tags:
  - AVX2
  - Hawk
---

## SHAKE类型

经过之前的工作，我们了解到，GAUSS函数实际上的操作对象是一个 `shake_context`类型的变量。如果要对这个函数进行优化，那么势必就要了解一下这个 `shake_context`到底是什么，该变量定义在 `sha3.h`中：

```c
typedef struct {
 uint64_t A[25];
 unsigned dptr, rate;
} shake_context;
```

这个结构体包含以下成员：

1. **`uint64_t A[25];`**

   这是一个包含 25 个 `uint64_t` 类型元素的数组。`uint64_t` 是一个无符号 64 位整数类型，通常用于存储较大的整数值。

2. **`unsigned dptr;`**

   这是一个无符号整数类型的变量，通常用于表示某种指针或索引。

3. **`unsigned rate;`**

   这也是一个无符号整数类型的变量，通常用于表示某种速率或比率。

### SHAKE初始化

接下来我们要跟踪GAUSS函数中对shake_context变量的操作来确定我们到底该在哪一步开始优化工作。我们关注到在四次循环中，第一步都是：

```c
  shake_context sc;
if (sc_extra != NULL) {
 sc = *sc_extra;
} else {
 shake_init(&sc, 256);
}
```

这一步的目的显然是初始化 `shake_context`，观察循环结构可以知道，该过程需要重复四次，那么我们有没有可能把这个四次的过程利用AVX2变为一次呢？这需要查看具体的 `shake_init`函数。

```c
void
shake_init(shake_context *sc, unsigned size)
{
 sc->rate = 200 - (size_t)(size >> 2);
 sc->dptr = 0;
 memset(sc->A, 0, sizeof sc->A);
}
```

我认为完全是可以的，这里的初始化实质上是一个重复的过程，在传入参数确定只可能为256/512/1024的情况下，`rate`和 `dptr`的初值实际上是确定的，而A数组的所有值都为0，这只需要使用AVX2的 `setzero`指令也可以完成。同时，从 `rate`和 `dptr`的初值来看，两者分别是当前状态缓冲区的写入位置和SHAKE 算法的“速率”（每个块的大小，单位：字节）。

### Inject&flip步骤

接下来的一步是这样的：

```c
  seed[40] = (uint8_t)j;
shake_inject(&sc, seed, 41);
shake_flip(&sc);
```

我们观察到，之前的代码生成随机种子时只生成了40位，但预备位却有41位，而在此处才加入了第41位，也就是循环变量，可能是用于禀明shake实例的顺序?但这个并不重要，我们要关注的是接下来的 `inject`和 `flip`函数：

```c
void
shake_inject(shake_context *sc, const void *in, size_t len)
{
 size_t dptr, rate;
 const uint8_t *buf;

 dptr = sc->dptr;
 rate = sc->rate;
 buf = in;
 while (len > 0) {
  size_t clen, u;

  clen = rate - dptr;//计算当前块剩余可写入的字节数
  if (clen > len) {
   clen = len;//如果剩余数据不足一个块，则处理剩余数据
  }
  for (u = 0; u < clen; u ++) {
   size_t v;

   v = u + dptr;//计算全局位置
   sc->A[v >> 3] ^= (uint64_t)buf[u] << ((v & 7) << 3);//这一步比较复杂，下文解析
  }
  dptr += clen;
  buf += clen;//代表已经处理完的部分
  len -= clen;
  if (dptr == rate) {
   process_block(sc->A);//当缓冲区填满时，调用 process_block（可能是 Keccak-f 置换函数）处理数据，并重置 dptr
   dptr = 0;
  }
 }
 sc->dptr = (unsigned)dptr;
}

/* see sha3.h */
void
shake_flip(shake_context *sc)
{
 /*
  * We apply padding and pre-XOR the value into the state. We
  * set dptr to the end of the buffer, so that first call to
  * shake_extract() will process the block.
  */
 unsigned v;

 v = (unsigned)sc->dptr;
 sc->A[v >> 3] ^= (uint64_t)0x1F << ((v & 7) << 3);//在当前位置 v 处异或 0x1F，这是 SHAKE 算法的填充规则（区别于 SHA-3 的 0x06）
 v = (unsigned)sc->rate - 1;
 sc->A[v >> 3] ^= (uint64_t)0x80 << ((v & 7) << 3);//在块的最后一个字节（rate - 1）处异或 0x80，表示多比特填充结束。
 sc->dptr = sc->rate;//当 dptr 被设为 rate 后，下一次调用 shake_extract 会强制处理填充后的块。
}
```

- **位操作** `sc->A[v >> 3] ^= (uint64_t)buf[u] << ((v & 7) << 3);` **解析**：
  - `v >> 3`：将字节位置 `v` 转换为 `uint64_t` 数组的索引（每个 `uint64_t` 占 8 字节，右移 3 位等价于除以 8）。
  - `(v & 7) << 3`：计算在 `uint64_t` 中的位偏移（每字节 8 位，7是0b0111，&7相当于取模8的余数，左移 3 位等价于乘以 8）。
  - 将输入字节 `buf[u]` 左移到正确位置，并与 `A` 数组的对应位置进行异或。

flip函数则比较简单，其作用是应用 SHAKE 算法的填充规则（Padding），标记输入结束。

这一步的内部函数不太适合并行化，好在4个Shake示例彼此无关，所以在调用的时候可以并行操作。
