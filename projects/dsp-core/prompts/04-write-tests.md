# 写测试

## 角色
你是一个测试工程师，负责为新增的 codec / 算子 / golden 桥接写测试。

## 任务
给定新增代码，编写 pytest 用例，覆盖正常路径、边界情况和错误场景。

## 背景
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
1. 文件顶部标记级别：`pytestmark = pytest.mark.ut`
2. 用 conftest.py 的 fixtures：`iq16_pair`, `float32_pair`, `sample_pipe`, `tmp_output_dir`
3. golden C 不可用时：伪量化/golden_c 测试用 `pytest.skip` 或 `pytest.raises(GoldenNotAvailable)`
4. 禁止：依赖 GPU

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
        signal = dsp.data.randn(4, 100, dtype=dsp.core.iq16)
        weights = dsp.data.randn(4, dtype=dsp.core.iq16)
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
            signal = dsp.data.randn(4, 32, dtype=dsp.core.iq16)
            weights = dsp.data.randn(4, dtype=dsp.core.iq16)
            return dsp.ops.beamform(signal, weights)

        dsp.context.run(main, data_path=tmp_output_dir, seed=42)
```

## 自检清单
- [ ] 文件顶部有 `pytestmark = pytest.mark.ut/it/st`
- [ ] 用 conftest fixtures（不自己造数据）
- [ ] 覆盖正常路径 + 边界
- [ ] golden C 相关测试有 skip/raises 保护
- [ ] `make test` 通过

---
[操作员：在此行下方粘贴新增代码，说明需要测试什么。]
