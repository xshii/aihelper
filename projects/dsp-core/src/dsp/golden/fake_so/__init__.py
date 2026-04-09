"""Fake .so — 纯 Python 模拟 golden C 函数，供开发/测试用。

模拟 convert 和 compute 函数的行为：
- convert: 简单的整数截断（round + clamp）
- compute: 用 numpy 实现基本运算

真正的 .so 接入后，golden/call.py 的 _get_lib() 应优先加载真 .so。
"""

import numpy as np


# ============================================================
# Convert: 整数截断模拟
# ============================================================

def _int_clamp(data, bits):
    """模拟整数截断: round + clamp to [-2^(bits-1), 2^(bits-1)-1]。"""
    qmin = -(1 << (bits - 1))
    qmax = (1 << (bits - 1)) - 1
    return np.clip(np.round(data), qmin, qmax).astype(np.float32)


def convert_float32_to_int8(src, dst, count):
    dst[:count] = _int_clamp(src[:count], 8)

def convert_int8_to_float32(src, dst, count):
    dst[:count] = src[:count]

def convert_float32_to_int16(src, dst, count):
    dst[:count] = _int_clamp(src[:count], 16)

def convert_int16_to_float32(src, dst, count):
    dst[:count] = src[:count]

def convert_float32_to_int32(src, dst, count):
    dst[:count] = _int_clamp(src[:count], 32)

def convert_int32_to_float32(src, dst, count):
    dst[:count] = src[:count]

def convert_int8_to_int16(src, dst, count):
    dst[:count] = src[:count]

def convert_int16_to_int32(src, dst, count):
    dst[:count] = src[:count]

def convert_int32_to_int16(src, dst, count):
    dst[:count] = _int_clamp(src[:count], 16)

def convert_int16_to_int8(src, dst, count):
    dst[:count] = _int_clamp(src[:count], 8)


# ============================================================
# Compute: numpy 模拟
# ============================================================

def sp_gemm_int16_int16_oint32_acc_q12_22(a, b, out, M, K, N):
    A = a[:M*K].reshape(M, K)
    B = b[:K*N].reshape(K, N)
    C = A @ B
    out[:M*N] = _int_clamp(C.flatten(), 32)

def sp_gemm_int16_int16_oint16_acc_q12_22(a, b, out, M, K, N):
    A = a[:M*K].reshape(M, K)
    B = b[:K*N].reshape(K, N)
    C = A @ B
    out[:M*N] = _int_clamp(C.flatten(), 16)

def sp_gemm_int32_int32_oint32_acc_q24_40(a, b, out, M, K, N):
    A = a[:M*K].reshape(M, K)
    B = b[:K*N].reshape(K, N)
    C = A @ B
    out[:M*N] = _int_clamp(C.flatten(), 32)

def sp_vadd_int16(a, b, out, count):
    out[:count] = _int_clamp(a[:count] + b[:count], 16)

def sp_vadd_int32(a, b, out, count):
    out[:count] = _int_clamp(a[:count] + b[:count], 32)

def sp_vmul_int16_int16_oint32_acc_q12_22(a, b, out, count):
    out[:count] = _int_clamp(a[:count] * b[:count], 32)

def sp_abs_int16(x, out, count):
    out[:count] = np.abs(x[:count])

def sp_abs_int32(x, out, count):
    out[:count] = np.abs(x[:count])

def sp_fused_linear_int16_int16_bint32_oint16_acc_q12_22(a, b, bias, out, scale_exp, M, K, N):
    A = a[:M*K].reshape(M, K)
    B = b[:K*N].reshape(K, N)
    C = A @ B + bias[:N]
    out[:M*N] = _int_clamp(C.flatten(), 16)

def sp_fused_linear_int16_int16_bint32_oint32_acc_q12_22(a, b, bias, out, scale_exp, M, K, N):
    A = a[:M*K].reshape(M, K)
    B = b[:K*N].reshape(K, N)
    C = A @ B + bias[:N]
    out[:M*N] = _int_clamp(C.flatten(), 32)

def sp_fused_linear_int32_int32_bint32_oint32_acc_q24_40(a, b, bias, out, scale_exp, M, K, N):
    A = a[:M*K].reshape(M, K)
    B = b[:K*N].reshape(K, N)
    C = A @ B + bias[:N]
    out[:M*N] = _int_clamp(C.flatten(), 32)

def sp_xcorr_int16_int16_oint32_acc_q12_22(a, b, out, signal_len):  # noqa: ARG
    result = np.correlate(a[:signal_len], b, mode='full').astype(np.float32)
    out[:len(result)] = result

def sp_xcorr_int32_int32_oint32_acc_q24_40(a, b, out, signal_len):  # noqa: ARG
    result = np.correlate(a[:signal_len], b, mode='full').astype(np.float32)
    out[:len(result)] = result
