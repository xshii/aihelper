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
        dtype["DSPDtype<br/>bf8, bf16, double"]
        tensor["DSPTensor<br/>torch.Tensor 子类 (存储 torch.double)"]
        codec["TypeCodec<br/>from_double / to_double / fake_quantize"]
        block["block.py<br/>pad_to_block / to_block / from_block"]
        convention["convention.py<br/>OpConvention 注册表"]
        enums["Mode / Format / DType / TensorSource"]
    end

    subgraph golden ["golden — C++ 封装"]
        manifest["manifest.py<br/>ComputeKey → C 函数名"]
        call["call.py<br/>调用 C++ 绑定"]
        auto["auto_register.py<br/>从 dsp_* 函数名自动建表"]
        dispatch["dispatch.py<br/>桥接 ops → convention → C"]
    end

    subgraph data ["data — 数据管线"]
        factory["factory.py<br/>randn / zeros / ones"]
        datagen["datagen.py<br/>数据策略"]
        pipe["DataPipe<br/>链式 API"]
        io["io.py<br/>hex 文件读写"]
        layout["layout.py<br/>block 分块"]
        compare["compare.py<br/>比数"]
    end

    subgraph ops ["ops — 算子（每个 op 一个目录）"]
        register["@register_op<br/>装饰器 + wrapper"]
        linear["linear/<br/>__init__.py + dsp_matrix.h + bind.cpp"]
        layernorm["layernorm/<br/>__init__.py + dsp_vector.h + bind.cpp"]
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

    U->>F: dsp.data.randn(4, 8, dtype=bf16)
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
        +name: str                "bf8 | bf16 | double"
        +torch_dtype: torch.dtype "语义标签，非存储类型"
        +subblock_size: int       "128-bit 寄存器内的元素数"
    }

    class DSPTensor {
        +_dsp_dtype: DSPDtype
        +_source: TensorSource    "RANDN | RANDN_QUANTIZED | OP_OUTPUT"
        +create(data, dsp_dtype)$ DSPTensor
        +torch() Tensor
        +fake_quantize() DSPTensor
        +dsp_dtype: DSPDtype
    }

    class TypeCodec {
        <<abstract>>
        +to_double(raw, dtype)*
        +from_double(t, dtype)*
        +fake_quantize(t, dtype)*
    }

    class GoldenCCodec {
        +to_double(raw, dtype)    "走 golden C convert"
        +from_double(t, dtype)    "走 golden C convert"
        +fake_quantize(t, dtype)  "按 subblock_size 对齐后做 round trip"
    }

    class PassthroughCodec {
        +to_double(raw, dtype)    "raw.double()"
        +from_double(t, dtype)    "t.to(torch_dtype)"
    }

    DSPTensor --> DSPDtype : _dsp_dtype
    DSPTensor --|> "torch.Tensor" : IS-A（存储始终 torch.double）
    GoldenCCodec --|> TypeCodec
    PassthroughCodec --|> TypeCodec

    note for GoldenCCodec "bf8 / bf16 都复用同一个 _golden_codec 实例\n不再为每个 dtype 造子类"
```

### 4.2 Golden C 封装

```mermaid
classDiagram
    class ComputeKey {
        +op: str
        +src0, src1, src2: str  "输入 dtype 字符串"
        +dst0, dst1, dst2: str  "输出 dtype 字符串"
        +compute_dtype: str     "可选 compute dtype"
    }

    class OpConvention {
        <<abstract>>
        +output_shape(*inputs)*
        +call_c_func(func, *inputs_np, **params)*
    }

    class MatmulConvention
    class LinearConvention
    class LayernormConvention
    class TransposeConvention

    MatmulConvention --|> OpConvention : "op='matmul'"
    LinearConvention --|> OpConvention : "op='linear'"
    LayernormConvention --|> OpConvention : "op='layernorm'"
    TransposeConvention --|> OpConvention : "op='transpose' (纯 Python)"

    note for OpConvention "__init_subclass__ 用 op= 参数自动注册到 _CONVENTIONS"
    note for ComputeKey "manifest.COMPUTE 的 key\nauto_register 从 dsp_{op}_{dut} 函数名反解"
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

    note for DataPipe "链式 API:\npipe.layout(Format.ZZ).export('blocked.txt')"
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
        L2["class LinearConvention(OpConvention, op='linear')<br/>bind.cpp 导出 dsp_linear_bf16<br/>(装饰器无需 golden_c 参数)"]
    end

    subgraph "Layer 3: 数学验证"
        L3["@register_op(weight=..., math_strategy=_math_fn)<br/>def linear(x, w, b): ..."]
    end

    L0 -->|加 format| L1
    L1 -->|加 OpConvention + bind.cpp| L2
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
| core | `dtype.py` | DType 枚举 + DSPDtype（bf8/bf16/double）+ TypeCodec + GoldenCCodec + PassthroughCodec |
| core | `tensor.py` | DSPTensor（torch.Tensor 子类 + _dsp_dtype + _source，存储始终 torch.double） |
| core | `block.py` | BlockShape / pad_dim / pad_to_block / to_block / from_block / format_to_dut |
| core | `convention.py` | OpConvention 基类 + __init_subclass__ 自动注册到 _CONVENTIONS |
| core | `enums.py` | Mode / Format / RunMode / TensorSource |
| core | `errors.py` | 异常层级 + 修复提示 |
| golden | `bind_helpers.h` | to_dut / from_dut / num_blocks 模板（pybind11 桥接） |
| golden | `bindings.cpp` | pybind11 顶层入口（编译为 _raw_bindings.so） |
| golden | `manifest.py` | CONVERT / COMPUTE 表 + ComputeKey NamedTuple |
| golden | `call.py` | convert() / compute() / is_available() |
| golden | `auto_register.py` | 从 _raw_bindings 的 dsp_* 函数名反解并填 manifest |
| golden | `dispatch.py` | dispatch_golden_c() — 桥接 ops → require_convention → call |
| data | `factory.py` | randn / zeros / ones / tensor（一律 torch.double 存储，打 _source 标记） |
| data | `datagen.py` | DataStrategy + generate_by_strategy（math / random / ...） |
| data | `pipe.py` | DataPipe（Mixin 组合：layout + io + compare + viz） |
| data | `layout.py` | LayoutMixin（ND ↔ ZZ / NN） |
| data | `io.py` | IOMixin（hex txt 读写，按文件名 dtype 读写 double/bf16 bits） |
| data | `compare.py` | CompareMixin + CompareResult（QSNR / cosine / max_diff） |
| data | `report.py` | 跨模式比数报告 |
| data | `viz.py` | VizMixin（plotly HTML 报告） |
| ops | `__init__.py` | _auto_import_ops: pkgutil 自动扫描 ops/ 下子目录 |
| ops | `__init__.pyi` | Pylance 类型提示 stub |
| ops | `_convert/` | dsp_convert.h + bind.cpp（double ↔ DUT 类型转换） |
| ops | `linear/` | __init__.py（LinearConvention + math_strategy）+ dsp_matrix.h + bind.cpp |
| ops | `layernorm/` | __init__.py + dsp_vector.h + bind.cpp |
| ops | `transpose/` | __init__.py（纯 Python OpConvention，无 C） |
| context | `__init__.py` | run() + hook 注入（set_ops_hooks + set_randn_interceptor） |
| context | `mode.py` | torch / pseudo_quant / golden_c 的 dispatch mode |
| context | `runloop.py` | 状态机 + intercepted_randn + save_op_inputs/output + load_op_inputs |
| context | `case.py` | 目录命名 + seed 提取 |
