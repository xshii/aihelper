# 写测试

## 角色
你是一个测试工程师，负责为新增的 codec / 算子 / golden 桥接写测试。

## 任务
给定新增代码，编写 pytest 用例，覆盖正常路径、边界情况和错误场景。

## 背景

> **信息安全声明：** 由于信息安全要求，强 AI 无法知道具体硬件细节。当前代码为架构示例，所有类型名、函数名、精度参数均为示意。实际使用时需结合真实硬件规格进行适配。

测试分三级（用 pytest markers）：
- `@pytest.mark.ut` — 单元测试：单函数，无 I/O
- `@pytest.mark.it` — 集成测试：多模块协作
- `@pytest.mark.st` — 系统测试：完整 E2E 流程

运行方式：
```bash
make test-ut          # 只跑单元测试（快）
make test             # 全部
make ci               # lint + 架构 + 全部测试
```

## 规则
1. MUST: 文件顶部标记级别 `pytestmark = pytest.mark.ut`
2. MUST: 用 conftest.py 的 fixtures（见下方表格）
3. SHOULD: golden C 不可用时用 `pytest.skip` 或 `pytest.raises(GoldenNotAvailable)` 保护
4. NEVER: 依赖 GPU
5. NEVER: 在测试中修改全局状态（`reset_state` fixture 自动处理）

## 可用 Fixtures（定义在 `tests/conftest.py`）

| Fixture | 类型 | 说明 |
|---------|------|------|
| `int16_pair` | `(DSPTensor, DSPTensor)` | shape=(64,), dtype=int16 的 (a, b) |
| `float32_pair` | `(DSPTensor, DSPTensor)` | shape=(64,), dtype=float32 的 (a, b) |
| `int16_matrix` | `DSPTensor` | shape=(4, 8), dtype=int16 |
| `float32_matrix` | `DSPTensor` | shape=(4, 8), dtype=float32 |
| `tmp_output_dir` | `str` | 临时目录，测试后自动清理 |
| `sample_pipe` | `DataPipe` | shape=(4, 8), dtype=float32 |
| `reset_state` | autouse | 每个测试后自动重置 mode + runloop |

## 步骤
1. 确定测试级别：新函数 → UT，多模块交互 → IT，完整 E2E → ST
2. 创建测试文件 `tests/test_<feature>.py`
3. 文件顶部加 `pytestmark = pytest.mark.ut`（或 it/st）
4. 用 conftest fixtures 构造测试数据
5. 写正常路径 + 至少 1 个边界/错误用例
6. 运行 `make test-ut`（开发中）→ `make ci`（提交前）

## 测试模板

### Codec 测试 (UT)
```python
# tests/test_codec_bfp16.py
import pytest
import dsp
from dsp.golden.call import is_available

pytestmark = pytest.mark.ut

class TestBFP16Codec:
    def test_fake_quantize(self):
        if not is_available():
            pytest.skip("golden C 不可用")
        a = dsp.data.randn(10, dtype=dsp.core.bfp16)
        b = a.fake_quantize()
        assert b.shape == a.shape
        assert b.dsp_dtype == dsp.core.bfp16
```

### 算子测试 (UT)
```python
# tests/test_op_beamform.py
import torch
import pytest
import dsp

pytestmark = pytest.mark.ut

class TestBeamform:
    def test_basic_call(self):
        signal = dsp.data.randn(4, 100, dtype=dsp.core.int16)
        weights = dsp.data.randn(4, dtype=dsp.core.int16)
        result = dsp.ops.beamform(signal, weights)
        assert result.shape == (100,)

    def test_golden_c_unregistered(self):
        """未注册的类型组合应抛 DSPError。"""
        from dsp.core.errors import DSPError
        from dsp.core.enums import Mode
        a = dsp.data.randn(4, dtype=dsp.core.float32)
        b = dsp.data.randn(4, dtype=dsp.core.float32)
        with dsp.context.mode_context(Mode.GOLDEN_C):
            with pytest.raises(DSPError):
                dsp.ops.beamform(a, b)
```

### E2E 测试 (ST)
```python
# tests/test_e2e_beamform.py
import pytest
import dsp
from dsp.core.enums import RunMode

pytestmark = pytest.mark.st

class TestBeamformE2E:
    def test_generate_and_compare(self, tmp_output_dir):
        def main():
            signal = dsp.data.randn(4, 32, dtype=dsp.core.int16)
            weights = dsp.data.randn(4, dtype=dsp.core.int16)
            return dsp.ops.beamform(signal, weights)

        dsp.context.run(main, data_path=tmp_output_dir, seed=42)
```

## 自检清单
- [ ] 文件顶部有 `pytestmark = pytest.mark.ut/it/st`
- [ ] 用 conftest fixtures（不自己造数据）
- [ ] 覆盖正常路径 + 边界
- [ ] golden C 相关测试有 skip/raises 保护
- [ ] `make test` 通过
- [ ] 验证: `make test-ut` (新测试应出现在列表中)

## 边界情况
- golden C 不可用：用 `pytest.skip("golden C 不可用")` 跳过，不要让测试失败
- 如果需要特殊 shape 的数据：直接用 `dsp.data.randn(...)` 构造，不要修改 conftest
- 如果不确定测试级别：默认选 UT，除非测试了多模块交互

---
[操作员：在此行下方粘贴新增代码，说明需要测试什么。]
