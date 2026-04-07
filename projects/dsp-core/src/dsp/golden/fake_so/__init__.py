"""Fake .so — 纯 Python 模拟 golden C 函数，供开发/测试用。

模拟 convert 和 compute 函数的行为：
- convert: 简单的定点截断（round + clamp）
- compute: 用 numpy 实现基本运算

真正的 .so 接入后，golden/call.py 的 _get_lib() 应优先加载真 .so。
"""

import numpy as np


# ============================================================
# Convert: 定点截断模拟
# ============================================================

def _iq_clamp(data, bits):
    """模拟定点截断: round + clamp to [-2^(bits-1), 2^(bits-1)-1]。"""
    qmin = -(1 << (bits - 1))
    qmax = (1 << (bits - 1)) - 1
    return np.clip(np.round(data), qmin, qmax).astype(np.float32)


def convert_float32_to_iq16(src, dst, count):
    dst[:count] = _iq_clamp(src[:count], 16)

def convert_iq16_to_float32(src, dst, count):
    dst[:count] = src[:count]

def convert_float32_to_iq32(src, dst, count):
    dst[:count] = _iq_clamp(src[:count], 32)

def convert_iq32_to_float32(src, dst, count):
    dst[:count] = src[:count]

def convert_iq16_to_iq32(src, dst, count):
    dst[:count] = src[:count]

def convert_iq32_to_iq16(src, dst, count):
    dst[:count] = _iq_clamp(src[:count], 16)


# ============================================================
# Compute: numpy 模拟
# ============================================================

def sp_gemm_iq16_iq16_oiq32_acc_q12_22(a, b, out, M, K, N):
    A = a[:M*K].reshape(M, K)
    B = b[:K*N].reshape(K, N)
    C = A @ B
    out[:M*N] = _iq_clamp(C.flatten(), 32)

def sp_gemm_iq16_iq16_oiq16_acc_q12_22(a, b, out, M, K, N):
    A = a[:M*K].reshape(M, K)
    B = b[:K*N].reshape(K, N)
    C = A @ B
    out[:M*N] = _iq_clamp(C.flatten(), 16)

def sp_gemm_iq32_iq32_oiq32_acc_q24_40(a, b, out, M, K, N):
    A = a[:M*K].reshape(M, K)
    B = b[:K*N].reshape(K, N)
    C = A @ B
    out[:M*N] = _iq_clamp(C.flatten(), 32)

def sp_vadd_iq16(a, b, out, count):
    out[:count] = _iq_clamp(a[:count] + b[:count], 16)

def sp_vadd_iq32(a, b, out, count):
    out[:count] = _iq_clamp(a[:count] + b[:count], 32)

def sp_vmul_iq16_iq16_oiq32_acc_q12_22(a, b, out, count):
    out[:count] = _iq_clamp(a[:count] * b[:count], 32)

def sp_abs_iq16(x, out, count):
    out[:count] = np.abs(x[:count])

def sp_abs_iq32(x, out, count):
    out[:count] = np.abs(x[:count])

def sp_fused_linear_iq16_iq16_biq32_oiq16_acc_q12_22(a, b, bias, out, scale_exp, M, K, N):
    A = a[:M*K].reshape(M, K)
    B = b[:K*N].reshape(K, N)
    C = A @ B + bias[:N]
    out[:M*N] = _iq_clamp(C.flatten(), 16)

def sp_fused_linear_iq16_iq16_biq32_oiq32_acc_q12_22(a, b, bias, out, scale_exp, M, K, N):
    A = a[:M*K].reshape(M, K)
    B = b[:K*N].reshape(K, N)
    C = A @ B + bias[:N]
    out[:M*N] = _iq_clamp(C.flatten(), 32)

def sp_fused_linear_iq32_iq32_biq32_oiq32_acc_q24_40(a, b, bias, out, scale_exp, M, K, N):
    A = a[:M*K].reshape(M, K)
    B = b[:K*N].reshape(K, N)
    C = A @ B + bias[:N]
    out[:M*N] = _iq_clamp(C.flatten(), 32)

def sp_xcorr_iq16_iq16_oiq32_acc_q12_22(a, b, out, signal_len):  # noqa: ARG
    result = np.correlate(a[:signal_len], b, mode='full').astype(np.float32)
    out[:len(result)] = result

def sp_xcorr_iq32_iq32_oiq32_acc_q24_40(a, b, out, signal_len):  # noqa: ARG
    result = np.correlate(a[:signal_len], b, mode='full').astype(np.float32)
    out[:len(result)] = result
