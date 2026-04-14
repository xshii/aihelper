#pragma once
#include <cstddef>

// ============================================================
// C++ 侧 transpose 辅助函数 —— header-only，可被其它 kernel 复用
// ============================================================
//
// 这个文件不被 bindings.cpp 直接收集成 Python 符号，只作为内部工具 header。
// 当某个 op 的 kernel 需要在其内部做"先 transpose 一下再计算"的步骤时，
// 可以 #include "dsp_transpose.h" 调用下面的函数。
//
// 所有函数都只在 double 域做纯元素搬运，不做量化/格式转换。调用方负责
// 先把硬件原生格式 (bf16/bf8 ...) 转成 double 再传入。

// ------------------------------------------------------------
// 4D transpose (核心实现): 只交换最后两维，前两维作为 batch
// ------------------------------------------------------------
// 输入 shape (d0, d1, rows, cols) row-major → 输出 (d0, d1, cols, rows)。
// 内部对 d0*d1 个独立的 (rows, cols) 2D 切片各做元素搬运。
//
// 索引约定 (row-major):
//   src[((i0*d1 + i1)*rows + r)*cols + c]
//   dst[((i0*d1 + i1)*cols + c)*rows + r]
//
// 调用方保证 src/dst 底层 buffer 长度 >= d0*d1*rows*cols。
//
// 用例: kernel 内部把 (B, H, M, D) 的 M/D 维对调:
//   dsp_transpose_4d_double(tmp, src, B, H, M, D);
inline void dsp_transpose_4d_double(double* dst, const double* src,
                                     size_t d0, size_t d1,
                                     size_t rows, size_t cols) {
    size_t batch = d0 * d1;
    size_t plane = rows * cols;
    for (size_t b = 0; b < batch; b++) {
        const double* s = src + b * plane;
        double*       d = dst + b * plane;
        for (size_t r = 0; r < rows; r++)
            for (size_t c = 0; c < cols; c++)
                d[c * rows + r] = s[r * cols + c];
    }
}

// ------------------------------------------------------------
// 2D transpose: (rows, cols) → (cols, rows)
// ------------------------------------------------------------
// 薄 wrapper，转发到 4D 核心 (batch = 1*1 = 1)。唯一的元素搬运逻辑
// 住在 dsp_transpose_4d_double 里。
inline void dsp_transpose_double(double* dst, const double* src,
                                  size_t rows, size_t cols) {
    dsp_transpose_4d_double(dst, src, 1, 1, rows, cols);
}
