"""ops/linear 单元测试 — _pad_and_flatten + torch/golden_c 比数。"""

import numpy as np
import torch
import pytest

import dsp
from dsp.core.enums import Mode, Format
from dsp.core.block import get_block_shape, pad_dim
from dsp.data.compare import compute_diff
from dsp.golden.call import is_available


class TestPadAndFlatten:
    """验证 _pad_and_flatten 的行/列优先。"""

    def test_zz_row_major_simple(self):
        from dsp.ops.linear import _pad_and_flatten
        data = np.array([[1, 2], [3, 4]], dtype=np.double)
        flat = _pad_and_flatten(data, "bf16", Format.ZZ)
        bh, bw = get_block_shape("bf16", Format.ZZ)
        ph, pw = pad_dim(2, bh), pad_dim(2, bw)
        assert flat.shape[0] == ph * pw
        # 行优先: flat[0]=1, flat[1]=2, flat[pw]=3, flat[pw+1]=4
        assert flat[0] == 1
        assert flat[1] == 2
        assert flat[pw] == 3
        assert flat[pw + 1] == 4

    def test_nn_col_major_simple(self):
        from dsp.ops.linear import _pad_and_flatten
        data = np.array([[1, 2], [3, 4]], dtype=np.double)
        flat = _pad_and_flatten(data, "bf16", Format.NN)
        bh, bw = get_block_shape("bf16", Format.NN)
        ph, pw = pad_dim(2, bh), pad_dim(2, bw)
        assert flat.shape[0] == ph * pw
        # 列优先: flat[0]=1, flat[1]=3, flat[ph]=2, flat[ph+1]=4
        assert flat[0] == 1, f"expected 1, got {flat[0]}"
        assert flat[1] == 3, f"expected 3, got {flat[1]}"
        assert flat[ph] == 2, f"expected 2, got {flat[ph]}"
        assert flat[ph + 1] == 4, f"expected 4, got {flat[ph+1]}"

    def test_nn_col_major_3x2(self):
        """列优先 flatten 验证: [[a,b],[c,d],[e,f]] → [a,c,e,b,d,f]。"""
        from dsp.ops.linear import _pad_and_flatten
        data = np.array([[10, 20], [30, 40], [50, 60]], dtype=np.double)
        flat = _pad_and_flatten(data, "bf16", Format.NN)
        bh, bw = get_block_shape("bf16", Format.NN)
        ph = pad_dim(3, bh)
        # 列优先: 先第 0 列 [10,30,50], 再第 1 列 [20,40,60]
        assert flat[0] == 10
        assert flat[1] == 30
        assert flat[2] == 50
        assert flat[ph] == 20
        assert flat[ph + 1] == 40
        assert flat[ph + 2] == 60


class TestLinearTorch:
    """torch 模式下的 linear。"""

    def test_2x2(self):
        x = dsp.data.tensor([[1, 2], [3, 4]], dtype=dsp.core.bf16)
        w = dsp.data.tensor([[5, 7], [6, 8]], dtype=dsp.core.bf16)
        b = dsp.data.tensor([[0, 0]], dtype=dsp.core.bf16)
        out = dsp.ops.linear(x, w, b)
        assert out.torch().tolist() == [[17, 23], [39, 53]]

    def test_with_bias(self):
        x = dsp.data.tensor([[1, 0], [0, 1]], dtype=dsp.core.bf16)
        w = dsp.data.tensor([[10, 20], [30, 40]], dtype=dsp.core.bf16)
        b = dsp.data.tensor([[1, 2]], dtype=dsp.core.bf16)
        out = dsp.ops.linear(x, w, b)
        assert out.torch().tolist() == [[11, 22], [31, 42]]

    def test_batch(self):
        x = dsp.data.randn(3, 4, 8, dtype=dsp.core.bf16)
        w = dsp.data.randn(8, 6, dtype=dsp.core.bf16)
        b = dsp.data.randn(1, 6, dtype=dsp.core.bf16)
        out = dsp.ops.linear(x, w, b)
        assert list(out.shape) == [3, 4, 6]


@pytest.mark.skipif(not is_available(), reason="golden C not available")
class TestLinearGoldenC:
    """golden_c 模式下的 linear。"""

    def setup_method(self):
        dsp.context.set_mode(Mode.GOLDEN_C)

    def teardown_method(self):
        dsp.context.set_mode(Mode.TORCH)

    def test_2x2_exact(self):
        x = dsp.data.tensor([[1, 2], [3, 4]], dtype=dsp.core.bf16)
        w = dsp.data.tensor([[5, 7], [6, 8]], dtype=dsp.core.bf16)
        b = dsp.data.tensor([[0, 0]], dtype=dsp.core.bf16)
        out = dsp.ops.linear(x, w, b)
        expected = [[17, 23], [39, 53]]
        assert out.torch().tolist() == expected, f"got {out.torch().tolist()}"

    def test_identity(self):
        """I @ w + 0 = w。"""
        x = dsp.data.tensor([[1, 0], [0, 1]], dtype=dsp.core.bf16)
        w = dsp.data.tensor([[3, 7], [5, 9]], dtype=dsp.core.bf16)
        b = dsp.data.tensor([[0, 0]], dtype=dsp.core.bf16)
        out = dsp.ops.linear(x, w, b)
        assert out.torch().tolist() == [[3, 7], [5, 9]]

    def test_non_aligned_shape(self):
        """非对齐 shape 不报错。"""
        x = dsp.data.randn(5, 7, dtype=dsp.core.bf16)
        w = dsp.data.randn(7, 3, dtype=dsp.core.bf16)
        b = dsp.data.randn(1, 3, dtype=dsp.core.bf16)
        out = dsp.ops.linear(x, w, b)
        assert list(out.shape) == [5, 3]

    def test_vs_torch_qsnr(self):
        """torch vs golden_c QSNR。"""
        x = dsp.data.randn(4, 8, dtype=dsp.core.bf16)
        w = dsp.data.randn(8, 4, dtype=dsp.core.bf16)
        b = dsp.data.randn(1, 4, dtype=dsp.core.bf16)

        dsp.context.set_mode(Mode.TORCH)
        out_torch = dsp.ops.linear(x, w, b)

        dsp.context.set_mode(Mode.GOLDEN_C)
        out_gc = dsp.ops.linear(x, w, b)

        diff = compute_diff(out_torch.torch(), out_gc.torch())
        print(f"\nlinear QSNR={diff['qsnr_db']:.1f}dB max_diff={diff['max_diff']:.1f}")
