#pragma once
#include <cstddef>

// ============================================================
// C++ 侧 transpose 辅助函数 —— header-only，可被其它 kernel 复用
// ============================================================
//
// 这个文件不被 bindings.cpp 收集成 Python 符号，只作为内部工具 header。
// 当某个 op 的 kernel 需要在其内部做"先 transpose 一下再计算"的步骤时，
// 可以 #include "dsp_transpose.h" 然后调 dsp_transpose_double。
//
// 索引约定:
//   src[r*cols + c]   — 输入，row-major (rows, cols)
//   dst[c*rows + r]   — 输出，row-major (cols, rows)
//
// 调用方保证 src/dst 的底层 buffer 长度 >= rows*cols。
inline void dsp_transpose_double(double* dst, double* src,
                                  size_t rows, size_t cols) {
    for (size_t r = 0; r < rows; r++)
        for (size_t c = 0; c < cols; c++)
            dst[c * rows + r] = src[r * cols + c];
}
