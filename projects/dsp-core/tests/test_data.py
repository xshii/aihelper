"""测试 data 模块：DataPipe 链式 API + 各 Mixin。"""

import os
import torch
import pytest
from dsp.core.enums import Format
from dsp.data.pipe import DataPipe
from dsp.data.datagen import DataStrategy, DEFAULT_STRATEGIES, generate_by_strategy
from dsp.data.layout import infer_format, _to_block, _from_block, _pad_to_block
from dsp.data.compare import compute_diff
from dsp.data.io import make_filename, parse_filename


# ============================================================
# UT: datagen
# ============================================================

class TestDatagen:
    pytestmark = pytest.mark.ut

    def test_strategy_frozen(self):
        """DataStrategy 是 frozen，不可修改。"""
        s = DataStrategy("test")
        with pytest.raises(AttributeError):
            s.name = "changed"

    def test_generate_random(self):
        t = generate_by_strategy(4, 8, dtype_torch=torch.float32,
                                 strategy=DataStrategy("random"))
        assert t.shape == (4, 8)
        assert t.dtype == torch.float32

    def test_generate_precision_exact(self):
        t = generate_by_strategy(10, dtype_torch=torch.float32,
                                 strategy=DataStrategy("exact", precision_exact=True,
                                                       value_range=(-10, 10)))
        assert t.dtype == torch.float32
        assert (t == t.round()).all()  # 整数值

    def test_generate_sparse(self):
        t = generate_by_strategy(1000, dtype_torch=torch.float32,
                                 strategy=DataStrategy("sparse", sparsity=0.9))
        zero_ratio = (t == 0).float().mean().item()
        assert zero_ratio > 0.8  # 大约 90% 零值

    def test_generate_all_zero(self):
        t = generate_by_strategy(10, dtype_torch=torch.float32,
                                 strategy=DataStrategy("zero", sparsity=1.0))
        assert (t == 0).all()

    def test_default_strategies_count(self):
        assert len(DEFAULT_STRATEGIES) == 7


# ============================================================
# UT: layout
# ============================================================

class TestLayout:
    pytestmark = pytest.mark.ut

    def test_infer_format_vector(self):
        assert infer_format(torch.randn(10)) == Format.ND
        assert infer_format(torch.randn(1, 10)) == Format.ND
        assert infer_format(torch.randn(10, 1)) == Format.ND

    def test_infer_format_matrix(self):
        assert infer_format(torch.randn(4, 8)) == Format.ZZ
        assert infer_format(torch.randn(16, 4, 8)) == Format.ZZ

    def test_pad_to_block(self):
        t = torch.randn(3, 5)
        padded = _pad_to_block(t, (4, 4))
        assert padded.shape == (4, 8)
        assert (padded[:3, :5] == t).all()

    def test_block_roundtrip(self):
        t = torch.randn(4, 8)
        block_shape = (4, 4)
        blocked = _to_block(t, "zz", block_shape)
        restored = _from_block(blocked, "zz", block_shape, (4, 8))
        assert torch.allclose(t, restored)


# ============================================================
# UT: io (文件名)
# ============================================================

class TestIO:
    pytestmark = pytest.mark.ut

    def test_make_parse_filename(self):
        fname = make_filename("linear", 0, "input0", "iq16", (4, 8), "zz")
        assert fname == "linear_0_input0_iq16_4x8_zz.txt"
        meta = parse_filename(fname)
        assert meta["op"] == "linear"
        assert meta["dtype"] == "iq16"
        assert meta["shape"] == (4, 8)
        assert meta["format"] == "zz"

    def test_parse_short_filename(self):
        meta = parse_filename("weird.txt")
        assert "raw" in meta


# ============================================================
# UT: compare
# ============================================================

class TestCompare:
    pytestmark = pytest.mark.ut

    def test_identical_tensors(self):
        t = torch.randn(10)
        diff = compute_diff(t, t)
        assert diff["max_diff"] == 0.0
        assert diff["cosine_sim"] == pytest.approx(1.0)

    def test_different_tensors(self):
        a = torch.ones(10)
        b = torch.zeros(10)
        diff = compute_diff(a, b)
        assert diff["max_diff"] == 1.0

    def test_complex_tensors(self):
        a = torch.randn(10, dtype=torch.complex64)
        diff = compute_diff(a, a)
        assert diff["max_diff"] == 0.0


# ============================================================
# IT: DataPipe 链式操作
# ============================================================

class TestDataPipeChain:
    pytestmark = pytest.mark.it

    def test_layout_roundtrip(self, sample_pipe):
        original = sample_pipe.tensor.clone()
        sample_pipe.layout(Format.ZZ).layout(Format.ND)
        assert torch.allclose(original, sample_pipe.tensor)

    def test_export_load_roundtrip(self, sample_pipe, tmp_output_dir):
        path = os.path.join(tmp_output_dir, "test_0_input0_float32_4x8_nd.txt")
        sample_pipe.export(path)
        loaded = DataPipe.load(path)
        assert torch.allclose(sample_pipe.tensor.float(), loaded.tensor.float(), atol=1e-6)

    def test_compare_via_pipe(self, tmp_output_dir):
        a = DataPipe(torch.randn(10), dtype="float32")
        b = a.clone()
        result = a.compare(b)
        assert result.max_diff == 0.0

    def test_history_tracking(self, sample_pipe, tmp_output_dir):
        path = os.path.join(tmp_output_dir, "test_0_input0_float32_4x8_nd.txt")
        sample_pipe.layout(Format.ZZ).layout(Format.ND).export(path)
        assert len(sample_pipe.history) == 3

    def test_clone_independent(self, sample_pipe):
        clone = sample_pipe.clone()
        clone.layout(Format.ZZ)
        assert sample_pipe.fmt == Format.ND
        assert clone.fmt == Format.ZZ
