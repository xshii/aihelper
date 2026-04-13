# 写测试

## 角色
你是一个测试工程师，负责为新增的 codec / 算子 / golden 桥接写 pytest 用例。

## 任务
给定新增代码，编写单元/集成/系统测试，覆盖正常路径 + 边界 + 错误场景。

## 背景

> **信息安全声明：** 强 AI 无法看到具体硬件细节，所有类型名/函数名/精度参数均为示意。

测试按 pytest marker 分三级，按子目录放置：

| Marker | 位置 | 说明 |
|---|---|---|
| `@pytest.mark.ut` | tests/ut/ 下的 core/golden/ops 子目录 | 单函数/单类，无 I/O，最快 |
| `@pytest.mark.it` | tests/it/（需要时创建） | 多模块协作，允许临时文件 |
| `@pytest.mark.st` | tests/st/（需要时创建） | 完整端到端（`dsp.context.run`） |

文件顶部 `pytestmark = pytest.mark.ut` 统一标注整个文件的级别。

**运行方式：**
```bash
python -m pytest tests/ut -q              # 开发循环（最快，当前 38 个 UT）
python -m pytest tests/ -q                # 全跑
python -m pytest -m ut tests/             # 按 marker 过滤
ruff check src/ && lint-imports           # 提交前 lint + 分层
```

## 可用 Fixtures（定义在 `tests/conftest.py`）

| Fixture | 类型 | 说明 |
|---|---|---|
| `bf16_pair` | `(DSPTensor, DSPTensor)` | 一对 `bf16` shape=(64,) |
| `double_pair` | `(DSPTensor, DSPTensor)` | 一对 `double` shape=(64,) |
| `bf16_matrix` | `DSPTensor` | `bf16` shape=(4, 8) |
| `double_matrix` | `DSPTensor` | `double` shape=(4, 8) |
| `tmp_output_dir` | `str` | 临时目录，测试后自动清理 |
| `sample_pipe` | `DataPipe` | 预建的 `double` DataPipe (4, 8) |
| `reset_state` | autouse | 每个测试后自动还原 mode + runloop |

## 规则

1. MUST: 文件顶部 `pytestmark = pytest.mark.ut`（或 it/st）
2. MUST: 优先复用 conftest fixtures，不要自己 `torch.randn(...)`
3. MUST: `from dsp.core.enums import Mode, RunMode` 使用枚举，不写 `"torch"` 字符串
4. SHOULD: 和 golden C 相关的测试用 `if not is_available(): pytest.skip(...)` 保护
5. SHOULD: 至少 1 个正常 + 1 个边界/错误
6. NEVER: 依赖 GPU
7. NEVER: 手动改全局 state（`reset_state` autouse fixture 已处理）
8. NEVER: 用老 dtype 名字（`bint8/bint16/iq16`）—— 当前只有 `bf8/bf16/double`

## 步骤

1. 确定测试级别：新函数 / 单类 → UT；多模块交互 → IT；`dsp.context.run(...)` → ST
2. 在对应目录下建文件（例如算子测试 → tests/ut/ops/test_gelu.py）
3. 文件顶部加 `pytestmark = pytest.mark.ut`
4. 复用 fixtures 构造测试数据
5. 覆盖正常路径 + 至少 1 个边界/错误
6. `python -m pytest tests/ut/<sub>/test_<feature>.py -v` 本地跑
7. `ruff check tests/` + `lint-imports` 提交前检查

## 测试模板

### Codec 测试 (UT, 文件位置: tests/ut/core/test_codec_bf4.py)

```python
import pytest
import torch
import dsp
from dsp.golden.call import is_available

pytestmark = pytest.mark.ut


class TestBF4Codec:
    def test_registered(self):
        """Codec 已注册可查。"""
        from dsp.core.dtype import get_codec
        codec = get_codec(dsp.core.bf4)
        assert codec is not None

    def test_fake_quantize(self):
        """fake_quantize 保 shape，返回 double 存储。"""
        if not is_available():
            pytest.skip("golden C 不可用")
        a = dsp.data.randn(32, dtype=dsp.core.bf4)
        b = a.fake_quantize()
        assert b.shape == a.shape
        assert b.dsp_dtype == dsp.core.bf4
        assert b.dtype == torch.double     # 内存全程 double 存储

    def test_fake_quantize_unaligned(self):
        """非 subblock 倍数 shape，fake_quantize 内部补零对齐后 trim。"""
        if not is_available():
            pytest.skip("golden C 不可用")
        a = dsp.data.randn(20, dtype=dsp.core.bf4)  # 20 % 32 ≠ 0
        b = a.fake_quantize()
        assert b.shape == (20,)
```

### 算子测试 (UT, 文件位置: tests/ut/ops/test_gelu.py)

```python
import pytest
import torch
import dsp

pytestmark = pytest.mark.ut


class TestGelu:
    def test_registered(self):
        assert "gelu" in dsp.ops.list_ops()

    def test_basic_shape(self, bf16_matrix):
        out = dsp.ops.gelu(bf16_matrix)
        assert out.shape == bf16_matrix.shape
        assert out.dsp_dtype == bf16_matrix.dsp_dtype

    def test_torch_fallback_when_no_c_binding(self):
        """golden_c 模式没注册就 fallback 到 torch，不抛错。"""
        a = dsp.data.randn(8, dtype=dsp.core.bf16)
        with dsp.context.mode_context(dsp.core.Mode.GOLDEN_C):
            out = dsp.ops.gelu(a)
        assert out.shape == a.shape
```

### E2E 测试 (ST, 文件位置: tests/st/test_e2e_gelu.py)

```python
import pytest
import dsp
from dsp.core.enums import RunMode
from dsp.data.datagen import DataStrategy

pytestmark = pytest.mark.st


def test_gelu_generate_then_use(tmp_output_dir):
    def main():
        x = dsp.data.randn(2, 32, dtype=dsp.core.bf16)
        return dsp.ops.gelu(x)

    strategies = [DataStrategy("random")]
    dsp.context.run(main, runmode=RunMode.GENERATE_INPUT,
                    data_path=tmp_output_dir, seed=42, strategies=strategies)
    dsp.context.run(main, runmode=RunMode.USE_INPUT,
                    data_path=tmp_output_dir, seed=42, strategies=strategies)
```

## 自检清单

- [ ] 文件顶部有 `pytestmark = pytest.mark.ut/it/st`
- [ ] 用当前存在的 dtype：`bf8 / bf16 / double`（不是 `bint16 / iq16`）
- [ ] 用 conftest fixtures（不重造随机数据）
- [ ] golden C 相关测试有 `if not is_available()` 保护
- [ ] 至少覆盖"注册" + "shape 正确" + 一个边界
- [ ] `python -m pytest tests/ut -q` 通过
- [ ] `ruff check tests/<your_file>` 通过

## 边界情况

- golden C 不可用时：`pytest.skip(...)`，不要让测试失败
- `fake_quantize` 的非对齐 shape：算例内部 `core.block.pad_dim` 会补齐再 trim，不会抛错 —— 可以直接测
- `DSPTensor` 的内存 dtype 始终是 `torch.double`（`dsp_dtype` 只是标签），写断言时注意
- 不确定测试级别时：默认 UT；涉及 `dsp.context.run` 一定是 ST

---
[操作员：在此行下方粘贴要测试的新代码，说明验收点。]
