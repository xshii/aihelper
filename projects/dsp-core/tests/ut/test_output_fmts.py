"""register_op(output_fmts=...) + multi-output save 单元测试。

覆盖三件事:
1. output_fmts kwarg 注册到 _OP_OUTPUT_FMTS
2. get_output_fmts 查询行为（声明 vs 缺省）
3. NN format DUT 文件 round trip (save 写出 → load 读回 → 数值一致)
"""

import torch
import pytest

import dsp
from dsp.core.enums import Format, Mode
from dsp.core.tensor import DSPTensor
from dsp.ops import register_op, get_output_fmts, _OP_OUTPUT_FMTS


@pytest.fixture(autouse=True)
def cleanup_ops():
    """每个 test 前后清掉测试用 op，避免污染全局 registry。"""
    from dsp.ops import _OP_REGISTRY
    snapshot_reg = dict(_OP_REGISTRY)
    snapshot_fmts = dict(_OP_OUTPUT_FMTS)
    yield
    # 还原
    _OP_REGISTRY.clear()
    _OP_REGISTRY.update(snapshot_reg)
    _OP_OUTPUT_FMTS.clear()
    _OP_OUTPUT_FMTS.update(snapshot_fmts)


class TestOutputFmtsRegistration:
    """register_op(output_fmts=...) 把声明写入全局表。"""

    def test_single_output_nn(self):
        @register_op(output_fmts=(Format.NN,))
        def fake_matmul_nn(x, w):
            return torch.matmul(x, w)

        assert _OP_OUTPUT_FMTS["fake_matmul_nn"] == (Format.NN,)
        assert get_output_fmts("fake_matmul_nn") == (Format.NN,)

    def test_multi_output_mixed(self):
        @register_op(output_fmts=(Format.ZZ, Format.NN, Format.ZZ))
        def fake_qkv(x, w):
            return x, x, x   # 仅占位

        assert _OP_OUTPUT_FMTS["fake_qkv"] == (Format.ZZ, Format.NN, Format.ZZ)
        assert get_output_fmts("fake_qkv", 3) == (Format.ZZ, Format.NN, Format.ZZ)

    def test_undeclared_defaults_zz(self):
        @register_op
        def fake_no_fmt(x):
            return x

        assert "fake_no_fmt" not in _OP_OUTPUT_FMTS
        # 默认 fallback：长度 1 → (ZZ,)
        assert get_output_fmts("fake_no_fmt") == (Format.ZZ,)
        # 多 output 默认也都 ZZ
        assert get_output_fmts("fake_no_fmt", 3) == (Format.ZZ, Format.ZZ, Format.ZZ)

    def test_string_fmt_coerced(self):
        """传字符串也接受，自动转 Format。"""
        @register_op(output_fmts=("nn",))
        def fake_str_fmt(x):
            return x

        assert _OP_OUTPUT_FMTS["fake_str_fmt"] == (Format.NN,)


class TestNNDUTRoundtrip:
    """save 一个 bf16 tensor with fmt=NN → 文件名带 _nn → load 回来等价。"""

    def test_nn_save_load_roundtrip(self, tmp_path, monkeypatch):
        from dsp.context.runloop import _save_tensor, _load_dut_file, _state
        from dsp.core.dtype import bf16

        # 准备原始 tensor
        torch.manual_seed(0)
        orig = torch.randn(16, 32, dtype=torch.double)
        # 量化到 bf16 精度（让 round trip 严格相等）
        orig = orig.to(torch.bfloat16).double()
        dsp_tensor = DSPTensor.create(orig, bf16)

        # mock 出当前 round dir + GOLDEN_C mode
        from dsp.context import runloop as rl
        round_dir = tmp_path / "round"
        round_dir.mkdir()
        monkeypatch.setattr(rl, "_current_round_dir", lambda: str(round_dir))
        _state.current_mode = Mode.GOLDEN_C

        try:
            _save_tensor(dsp_tensor, "testop", 0, "output0", fmt_hint=Format.NN)
        finally:
            _state.current_mode = Mode.TORCH

        # 找 DUT 文件
        dut_dir = round_dir / "dut"
        dut_files = list(dut_dir.glob("testop_0_output0_*.txt")) if dut_dir.exists() else []
        all_files = sorted(round_dir.rglob("*.txt"))
        assert len(dut_files) == 1, f"expected 1 file, got {len(dut_files)}; all files: {all_files}"
        dut_path = dut_files[0]
        assert "_nn.txt" in dut_path.name, f"expected _nn suffix, got {dut_path.name}"

        # 读回来
        loaded = _load_dut_file(dut_path)
        assert loaded.shape == orig.shape
        assert torch.allclose(loaded.double(), orig, atol=0)

    def test_zz_save_load_roundtrip_unchanged(self, tmp_path, monkeypatch):
        """对照组：fmt=ZZ 的同一个 tensor 也能 round trip（保证我没破坏 ZZ 路径）。"""
        from dsp.context.runloop import _save_tensor, _load_dut_file, _state
        from dsp.core.dtype import bf16

        torch.manual_seed(1)
        orig = torch.randn(16, 32, dtype=torch.double).to(torch.bfloat16).double()
        dsp_tensor = DSPTensor.create(orig, bf16)

        from dsp.context import runloop as rl
        round_dir = tmp_path / "round_zz"
        round_dir.mkdir()
        monkeypatch.setattr(rl, "_current_round_dir", lambda: str(round_dir))
        _state.current_mode = Mode.GOLDEN_C

        try:
            _save_tensor(dsp_tensor, "testop", 0, "output0", fmt_hint=Format.ZZ)
        finally:
            _state.current_mode = Mode.TORCH

        dut_files = list((round_dir / "dut").glob("testop_0_output0_*.txt"))
        assert len(dut_files) == 1
        assert "_zz.txt" in dut_files[0].name

        loaded = _load_dut_file(dut_files[0])
        assert torch.allclose(loaded.double(), orig, atol=0)


class TestMultiOutputSave:
    """save_op_output 支持 tuple result，写多个 outputN 文件。"""

    def test_tuple_result_writes_multiple_files(self, tmp_path, monkeypatch):
        from dsp.context.runloop import save_op_output, _state
        from dsp.core.dtype import bf16

        # 注册一个 fake 多 output op，声明 (ZZ, NN, ZZ)
        @register_op(output_fmts=(Format.ZZ, Format.NN, Format.ZZ))
        def fake_qkv_save(x):
            return x, x, x

        from dsp.context import runloop as rl
        round_dir = tmp_path / "round_multi"
        round_dir.mkdir()
        monkeypatch.setattr(rl, "_current_round_dir", lambda: str(round_dir))
        _state.current_mode = Mode.GOLDEN_C
        _state.op_id_counter = 0

        torch.manual_seed(2)
        t = torch.randn(16, 32, dtype=torch.double).to(torch.bfloat16).double()
        dsp_t = DSPTensor.create(t, bf16)

        try:
            save_op_output("fake_qkv_save", (dsp_t, dsp_t, dsp_t))
        finally:
            _state.current_mode = Mode.TORCH

        dut_dir = round_dir / "dut"
        files = sorted(dut_dir.glob("fake_qkv_save_*"))
        # 期望 3 个文件: output0 (zz), output1 (nn), output2 (zz)
        assert len(files) == 3, f"expected 3 files, got {[f.name for f in files]}"
        assert "output0" in files[0].name and "_zz.txt" in files[0].name
        assert "output1" in files[1].name and "_nn.txt" in files[1].name
        assert "output2" in files[2].name and "_zz.txt" in files[2].name
