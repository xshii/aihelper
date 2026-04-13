"""core/block.py 单元测试 — padding + 存储顺序 + format 转换。不绑定具体 dtype 值。"""

import numpy as np
import torch
import pytest

from dsp.core.block import (
    BLOCK_TYPES, get_block_shape, pad_dim, pad_to_block,
    to_block, from_block, format_to_dut, format_from_dut,
)
from dsp.core.enums import Format

# 取第一个可用 dtype，不硬编码
_DTYPE = str(list(BLOCK_TYPES.keys())[0])


class TestPadDim:
    def test_aligned(self):
        assert pad_dim(16, 16) == 16

    def test_unaligned(self):
        assert pad_dim(12, 16) == 16
        assert pad_dim(17, 16) == 32


class TestStorageOrder:
    """行优先/列优先 flatten 的定义验证。"""

    def test_row_major(self):
        mat = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.double)
        assert list(mat.flatten()) == [1, 2, 3, 4, 5, 6]

    def test_col_major(self):
        mat = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.double)
        assert list(mat.flatten(order='F')) == [1, 4, 2, 5, 3, 6]

    def test_row_major_indexing(self):
        mat = np.array([[10, 20], [30, 40]], dtype=np.double)
        flat = mat.flatten()
        assert flat[0 * 2 + 0] == 10
        assert flat[0 * 2 + 1] == 20
        assert flat[1 * 2 + 0] == 30
        assert flat[1 * 2 + 1] == 40

    def test_col_major_indexing(self):
        mat = np.array([[10, 20], [30, 40]], dtype=np.double)
        flat = mat.flatten(order='F')
        assert flat[0 * 2 + 0] == 10
        assert flat[0 * 2 + 1] == 30
        assert flat[1 * 2 + 0] == 20
        assert flat[1 * 2 + 1] == 40


class TestBlockReorder:
    def test_roundtrip(self):
        """to_block → from_block 往返一致。"""
        t = torch.randn(20, 30)
        for fmt in [Format.ZZ, Format.NN]:
            blocked = to_block(t, _DTYPE, fmt)
            recovered = from_block(blocked, _DTYPE, fmt, t.shape)
            torch.testing.assert_close(recovered, t)


class TestFormatToDut:
    def test_roundtrip_zz(self):
        data = np.random.randn(5, 7).astype(np.double)
        flat, orig = format_to_dut(data, _DTYPE, str(Format.ZZ))
        recovered = format_from_dut(flat, _DTYPE, str(Format.ZZ), orig)
        np.testing.assert_array_almost_equal(recovered, data)

    def test_1d_passthrough(self):
        data = np.array([1.0, 2.0, 3.0])
        flat, shape = format_to_dut(data, _DTYPE, str(Format.ZZ))
        assert list(flat) == [1.0, 2.0, 3.0]
