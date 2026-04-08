# dsp-core 架构设计文档

> 渐进式阅读：先看 Layer 0（一张图），需要时再深入后续层。

---

## Layer 0: 一张图看全貌

```mermaid
graph TB
    subgraph "用户代码"
        USER["main.py<br/>x = dsp.data.randn(...)<br/>out = dsp.ops.linear(x, w, b)<br/>dsp.context.run(main)"]
    end

    subgraph "dsp 框架"
        CORE["core<br/>类型系统"]
        DATA["data<br/>数据管线"]
        OPS["ops<br/>算子注册"]
        GOLDEN["golden<br/>C++ 封装"]
        CTX["context<br/>运行循环"]
    end

    USER --> CTX
    CTX -->|hook 注入| OPS
    CTX -->|hook 注入| DATA
    OPS --> CORE
    OPS -->|golden_c 分发| GOLDEN
    DATA --> CORE
    DATA -->|block shape| GOLDEN
    GOLDEN --> CORE

    style CORE fill:#e1f5fe
    style CTX fill:#fff3e0
```

**依赖方向严格单向：** `core → golden → data → ops → context`

import-linter 自动检查，违反即 CI 失败。

---

## Layer 1: 模块职责

```mermaid
graph LR
    subgraph core ["core — 类型系统"]
        dtype["DSPDtype<br/>iq16, iq32, float32..."]
        tensor["DSPTensor<br/>torch.Tensor 子类"]
        codec["TypeCodec<br/>编解码器"]
        enums["Mode / Format / DType<br/>字符串枚举"]
    end

    subgraph golden ["golden — C++ 封装"]
        manifest["manifest.py<br/>ComputeKey → C 函数名"]
        call["call.py<br/>调用 C / fake_so"]
        convention["op_convention.py<br/>参数映射约定"]
        fakeso["fake_so/<br/>Python 模拟 C"]
    end

    subgraph data ["data — 数据管线"]
        factory["factory.py<br/>randn / zeros / ones"]
        datagen["datagen.py<br/>数据策略"]
        pipe["DataPipe<br/>链式 API"]
        io["io.py<br/>hex 文件读写"]
        layout["layout.py<br/>block 分块"]
        compare["compare.py<br/>比数"]
    end

    subgraph ops ["ops — 算子"]
        register["@register_op<br/>装饰器 + wrapper"]
        linear["linear.py<br/>+ math_strategy"]
        correlate["correlate.py"]
    end

    subgraph context ["context — 运行循环"]
        mode["mode.py<br/>torch / pseudo_quant / golden_c"]
        runloop["runloop.py<br/>状态机 + 数据拦截"]
        case["case.py<br/>目录 + seed 管理"]
    end
```

---

## Layer 2: 数据流 — generate_input

```mermaid
sequenceDiagram
    participant U as 用户 main()
    participant F as factory.randn
    participant RL as runloop
    participant W as register_op wrapper
    participant MS as math_strategy
    participant OP as linear (torch)
    participant IO as save_op_inputs/output

    U->>F: dsp.data.randn(4, 8, dtype=iq16)
    F->>RL: intercepted_randn()
    RL-->>F: DSPTensor (_source="randn")
    F-->>U: x

    Note over U: 同样生成 w, b

    U->>W: dsp.ops.linear(x, w, b)
    W->>W: 检查当前策略
    alt 策略 = "math" 且 op 有 math_strategy
        W->>MS: math_strategy(inputs, source_map)
        MS-->>W: {0: new_x, 1: new_w, 2: new_b}
        W->>W: 替换 randn 源的输入
    end
    W->>IO: save_op_inputs (替换后的)
    W->>OP: linear(x, w, b)
    OP-->>W: result
    W->>W: result._source = "op_output"
    W->>IO: save_op_output
    W-->>U: DSPTensor
```

---

## Layer 3: 数据流 — use_input

```mermaid
sequenceDiagram
    participant U as 用户 main()
    participant F as factory.randn
    participant RL as runloop
    participant W as register_op wrapper
    participant OP as linear
    participant M as mode (torch/pq/gc)

    Note over RL: 遍历: 8 策略目录 × 3 模式

    RL->>M: set_mode(当前模式)

    U->>F: dsp.data.randn(4, 8)
    F->>RL: intercepted_randn()
    RL->>RL: 从磁盘加载 input0
    RL-->>F: 已保存的 DSPTensor
    F-->>U: x (和 generate_input 时一样)

    U->>W: dsp.ops.linear(x, w, b)
    Note over W: math_strategy 不激活<br/>(只在 generate_input 生效)
    W->>IO: save_op_inputs
    alt mode = torch
        W->>OP: linear (纯 torch)
    else mode = pseudo_quant
        W->>OP: linear (fake_quantize 拦截)
    else mode = golden_c
        W->>OP: dispatch_golden_c
    end
    W->>IO: save_op_output
    W-->>U: result

    Note over RL: 所有轮次完成后<br/>比数报告: torch vs pq vs gc
```

---

## Layer 4: 类图

### 4.1 类型系统 (core)

```mermaid
classDiagram
    class DSPDtype {
        +name: str
        +torch_dtype: torch.dtype
        +bits: int
        +is_complex: bool
    }

    class DSPTensor {
        +_dsp_dtype: DSPDtype
        +_source: str  "randn|op_output|None"
        +create(data, dsp_dtype)$ DSPTensor
        +torch() Tensor
        +to_dsp(target) DSPTensor
        +fake_quantize() DSPTensor
        +dsp_dtype: DSPDtype
    }

    class TypeCodec {
        <<abstract>>
        +to_float(data)*
        +from_float(data)*
        +fake_quantize(data)*
    }

    class GoldenCCodec {
        +to_float(data)
        +from_float(data)
        +fake_quantize(data)
    }

    class IQ16Codec
    class IQ32Codec

    DSPTensor --> DSPDtype : _dsp_dtype
    DSPTensor --|> "torch.Tensor" : IS-A
    GoldenCCodec --|> TypeCodec
    IQ16Codec --|> GoldenCCodec : "dtype=iq16 (auto-register)"
    IQ32Codec --|> GoldenCCodec : "dtype=iq32 (auto-register)"
```

### 4.2 Golden C 封装

```mermaid
classDiagram
    class ComputeKey {
        +op: str
        +in0, in1, in2: str
        +out0, out1, out2: str
        +acc: str
        +compute: str
    }

    class OpConvention {
        <<abstract>>
        +output_shape(*inputs)*
        +call_c_func(func, *inputs_np)*
    }

    class LinearConvention {
        +output_shape(*inputs)
        +call_c_func(func, *inputs_np)
    }

    class CorrelateConvention {
        +output_shape(*inputs)
        +call_c_func(func, *inputs_np)
    }

    class ElementwiseConvention {
        +output_shape(*inputs)
        +call_c_func(func, *inputs_np)
    }

    LinearConvention --|> OpConvention : "op='linear' (auto-register)"
    CorrelateConvention --|> OpConvention : "op='correlate' (auto-register)"
    ElementwiseConvention --|> OpConvention : "op=['add','mul','sub'] (auto-register)"

    note for ComputeKey "manifest.COMPUTE 的 key\n3 输入 + 3 输出槽位"
```

### 4.3 数据管线 (data)

```mermaid
classDiagram
    class DataPipe {
        -_tensor: Tensor
        -_dtype_name: str
        -_fmt: Format
        -_history: list
        +clone() DataPipe
        +to_tensor() Tensor
    }

    class ConvertMixin {
        +convert(target_dtype) self
    }
    class LayoutMixin {
        +layout(fmt) self
    }
    class IOMixin {
        +export(path) self
        +load(path)$ DataPipe
    }
    class CompareMixin {
        +compare(other) CompareResult
    }
    class VizMixin {
        +plot(**kwargs)
    }

    DataPipe --|> ConvertMixin
    DataPipe --|> LayoutMixin
    DataPipe --|> IOMixin
    DataPipe --|> CompareMixin
    DataPipe --|> VizMixin

    note for DataPipe "链式 API:\npipe.convert('iq16').layout('zz').export('out.txt')"
```

---

## Layer 5: 算子注册 — 渐进式四层

```mermaid
graph TB
    subgraph "Layer 0: 纯 torch"
        L0["@register_op<br/>def my_op(a, b): return a + b"]
    end

    subgraph "Layer 1: 格式标注"
        L1["@register_op(weight=Format.NN)<br/>def linear(x, w, b): ..."]
    end

    subgraph "Layer 2: 接 golden C"
        L2["@register_op(golden_c={ComputeKey: 'c_func'})<br/>def linear(x, w, b): ..."]
    end

    subgraph "Layer 3: 数学验证"
        L3["@register_op(math_strategy=_math_fn)<br/>def linear(x, w, b): ..."]
    end

    L0 -->|加 format| L1
    L1 -->|加 golden_c| L2
    L2 -->|加 math_strategy| L3

    style L0 fill:#c8e6c9
    style L1 fill:#fff9c4
    style L2 fill:#ffccbc
    style L3 fill:#e1bee7
```

---

## Layer 6: Math Strategy 链式回归

```mermaid
graph LR
    subgraph "op1: linear (首算子)"
        X1["x = near_diagonal<br/>_source=randn → 替换"]
        W1["w = lstsq(x, target)"]
        B1["b = zeros"]
        Y1["output ≈ near_diagonal<br/>_source=op_output"]
    end

    subgraph "op2: custom_op (无 math_strategy)"
        Y1 -->|被动传入| OP2["custom_op(y, randn_w)"]
        Z1["output = 不可控<br/>_source=op_output"]
        OP2 --> Z1
    end

    subgraph "op3: linear (回归)"
        Z1 -->|被动接受| W3["w = ridge(z, target)<br/>回归到 near_diagonal"]
        OUT["output ≈ near_diagonal"]
        W3 --> OUT
    end

    style X1 fill:#c8e6c9
    style W1 fill:#c8e6c9
    style Y1 fill:#bbdefb
    style Z1 fill:#ffccbc
    style OUT fill:#c8e6c9
```

**核心思想：** linear/matmul 天然具备"投影"能力，利用 lstsq/ridge 把累积误差收回目标 pattern。

---

## Layer 7: Hook 注入 — 解除循环依赖

```mermaid
graph LR
    CTX["context/__init__.py"]
    OPS["ops/__init__.py"]
    DATA["data/factory.py"]

    CTX -->|"set_ops_hooks(get_mode, save_op_inputs, ...)"| OPS
    CTX -->|"set_randn_interceptor(intercepted_randn)"| DATA

    OPS -.->|"_hooks['get_mode']()"| CTX
    OPS -.->|"_hooks['get_current_strategy']()"| CTX
    DATA -.->|"_randn_interceptor(*size)"| CTX

    style CTX fill:#fff3e0
    style OPS fill:#e8eaf6
    style DATA fill:#e8eaf6
```

**实线 = import 时注入**（module load 阶段）
**虚线 = 运行时回调**（通过注入的函数指针）

ops 和 data 永远不 import context，避免循环依赖。import-linter 强制保证。

---

## 附录: 文件清单

| 模块 | 文件 | 一句话 |
|------|------|--------|
| core | `dtype.py` | DSPDtype 定义 + 注册表 |
| core | `tensor.py` | DSPTensor (torch.Tensor 子类 + _dsp_dtype + _source) |
| core | `codec.py` | TypeCodec / GoldenCCodec + __init_subclass__ 自动注册 |
| core | `enums.py` | Mode / Format / RunMode / DType 枚举 |
| core | `errors.py` | 异常层级 + 修复提示 |
| golden | `manifest.py` | TYPES / CONVERT / COMPUTE 三张表 |
| golden | `call.py` | convert() / compute() / is_available() |
| golden | `dispatch.py` | dispatch_golden_c() — 桥接 ops → call |
| golden | `op_convention.py` | OpConvention + __init_subclass__ 自动注册 |
| golden | `fake_so/` | Python 模拟 C 函数（开发用） |
| data | `factory.py` | randn / zeros / ones (打 _source 标记) |
| data | `datagen.py` | DataStrategy + generate_by_strategy |
| data | `pipe.py` | DataPipe (Mixin 组合) |
| data | `convert.py` | ConvertMixin (调 golden.convert) |
| data | `layout.py` | LayoutMixin (block 分块) |
| data | `io.py` | IOMixin (hex 文件) |
| data | `compare.py` | CompareMixin + CompareResult |
| data | `report.py` | 跨模式比数报告 |
| data | `viz.py` | VizMixin (matplotlib) |
| ops | `__init__.py` | @register_op + dispatch + hook 注入 |
| ops | `linear.py` | linear + _linear_math_strategy |
| ops | `correlate.py` | correlate (互相关) |
| context | `__init__.py` | run() + hook 注入 + compute config |
| context | `mode.py` | PseudoQuantMode / GoldenCMode |
| context | `runloop.py` | 状态机 + intercepted_randn + 出数 |
| context | `case.py` | 目录命名 + seed 提取 |
| — | `config.py` | 全局配置单例 |
