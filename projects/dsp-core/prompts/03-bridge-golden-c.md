# 注册 Golden C 函数

## 角色
你是一个硬件验证工程师，负责在 manifest.py 中注册新的 C++ 函数。

## 任务
当硬件团队提供新的 C 函数，在 `@register_op` 的 `golden_c` 参数中添加 ComputeKey 条目。

## 背景

> **信息安全声明：** 由于信息安全要求，强 AI 无法知道具体硬件细节。当前代码为架构示例，所有类型名、函数名、精度参数均为示意。实际使用时需结合真实硬件规格进行适配。

### 三层精度 + DType 枚举

```python
from dsp.core.enums import DType
D = DType.DUT    # 芯片原生定点：D.IQ16, D.IQ32
R = DType.REAL   # 标准浮点：R.FLOAT16, R.FLOAT32
A = DType.ACC    # 累加器格式：A.Q12_22, A.Q8_26, A.Q24_40
```

ComputeKey 固定 3 输入 + 3 输出槽位，None 填空：

```python
ComputeKey(
    op="linear",
    in0=D.IQ16,         # 输入 x（DUT 或 REAL）
    in1=D.IQ16,         # 权重（DUT 或 REAL）
    in2=D.IQ32,         # bias（通常 ACC 精度）
    out0=D.IQ16,        # 输出
    # out1, out2 不填 = None
    acc=A.Q12_22,        # 累加器内部格式
    compute=D.IQ16,      # 计算精度（DUT 或 REAL，如 FP16 混合精度）
)
```

## 规则
1. MUST: 用关键字参数填 ComputeKey（不要数位置）
2. MUST: 用 DType 枚举值（`D.IQ16`，不用字符串 `"iq16"`）
3. MUST: C 函数名从头文件复制粘贴（不手打）
4. NEVER: 合并不同类型组合到一个条目

## 步骤
1. 从硬件团队的头文件中找到 C 函数名（精确复制，不手打）
2. 确定精度组合：输入类型 × 输出类型 × 累加器格式 × 计算精度
3. 构造 ComputeKey（用 DType 枚举值填每个槽位，不需要的填 None）
4. 添加到 `@register_op(golden_c={...})`（推荐）或 `manifest.py COMPUTE`
5. 运行 `make test` 验证

## 在哪里添加

**方式 A（推荐）：直接在 `@register_op` 的 golden_c 参数中**

```python
# ops/conv2d.py
@register_op(golden_c={
    ComputeKey(op="conv2d", in0=D.IQ16, in1=D.IQ16, out0=D.IQ32,
               acc=A.Q12_22, compute=D.IQ16):
        "sp_conv2d_iq16_iq16_oiq32_acc_q12_22",
})
def conv2d(input, kernel): ...
```

**选择标准：**
- 方式 A（推荐）：op 文件已存在，只是增加精度组合 → 直接加在 `@register_op golden_c={}` 里
- 方式 B：op 文件还没有（只有 manifest 先行）或需要批量注册多个 op → 加在 `manifest.py COMPUTE` 里

**方式 B：在 manifest.py COMPUTE 表中**

```python
# golden/manifest.py
ComputeKey(op="conv2d", in0=D.IQ16, in1=D.IQ16, out0=D.IQ32,
           acc=A.Q12_22, compute=D.IQ16):
    "sp_conv2d_iq16_iq16_oiq32_acc_q12_22",
```

## 常见错误

| 错误 | 症状 | 正确做法 |
|------|------|---------|
| 用字符串 `"iq16"` 不用枚举 | 查询可能失败 | 用 `D.IQ16` |
| acc 和 out0 混淆 | 精度丢失 | acc=累加器（宽），out0=最终输出（可窄）|
| 漏了 compute 字段 | ManifestNotFound | 看函数名末尾的精度标记 |
| C 函数名手打 typo | GoldenNotAvailable | 从头文件复制 |

## 样例

### 样例 1: 为 linear 添加新精度组合

已有 iq16×iq16→iq16 的映射（见 `src/dsp/ops/linear.py`）。现在硬件新增了 float16 混合精度版本：

**输入：** 头文件中新增 `sp_fused_linear_fp16_fp16_ofp16_acc_q12_22`

**操作：** 在 linear.py 的 `@register_op golden_c` 字典中添加：
```python
ComputeKey(op="linear", in0=R.FLOAT16, in1=R.FLOAT16, in2=R.FLOAT16, out0=R.FLOAT16,
           acc=A.Q12_22, compute=R.FLOAT16):
    "sp_fused_linear_fp16_fp16_ofp16_acc_q12_22",
```

**验证：** `make test` 通过

### 样例 2: 错误 — acc 和 out0 混淆

**错误写法：**
```python
ComputeKey(op="linear", in0=D.IQ16, in1=D.IQ16, out0=A.Q12_22, acc=D.IQ16, ...)
#                                                  ^^^^^^^^^^^    ^^^^^^^^^
```
**问题：** out0 是最终输出精度（通常是 DUT），acc 是累加器内部格式（通常更宽）。写反会导致精度丢失。

**正确：** `out0=D.IQ16, acc=A.Q12_22`

## 自检清单
- [ ] 用关键字参数 + DType 枚举
- [ ] C 函数名和头文件完全一致
- [ ] 每个类型组合一个 ComputeKey
- [ ] `make test` 通过
- [ ] 验证: `.venv/bin/python -c "from dsp.golden.manifest import get_compute_func; print(get_compute_func('YOUR_OP', 'YOUR_IN0', 'YOUR_IN1'))"`

---
[操作员：在此行下方提供 C++ 函数列表或头文件。]
