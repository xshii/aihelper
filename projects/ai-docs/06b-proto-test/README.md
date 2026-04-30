# proto-test-env

> FPGA 原型测试环境参考实现 —— 配套 `ai-docs/06b_子wiki_原型测试环境详设.md`。
>
> 弱 AI 直接复用 `src/proto_test/` 嵌入到 Autotest 项目；强 AI 看本仓库学**Block 组合 / 通用内存访问 / 比数协议 / 错误体系 / 状态机 / 容错重试** 等核心骨架。

## 仓库结构

```
proto-test-env/
├── src/proto_test/                  # Autotest Python 端（9 个核心模块）
│   ├── block.py            (§ 1.7)  Composite + 512 对齐 + ENDIAN + BitFieldMixin + DDR 块头 + 分片填写
│   ├── memory.py           (§ 4.8)  Datatype + StructDef + register_struct + MemAccessAPI + SymbolMap + CompareEntry
│   ├── compare.py          (§ 1.6)  机制 B 比数（g_debugCnt + g_compAddr）
│   ├── adapters.py         (§ 4.2)  PlatformAdapter / DummyAdapter / Mechanism / FpgaAdapter
│   ├── errors.py           (§ 3.6)  AutotestError 异常树 + code_to_exception
│   ├── domain.py           (§ 4.3)  Verdict / CompareMode / ResultOut / Case / ...
│   ├── retry.py            (§ 3.6)  @retryable + total_backoff
│   ├── buffer_registry.py  (§ 3.8)  M12 alloc/write/read/free + crc32
│   └── lifecycle.py        (§ 2.7)  M06 模型生命周期 FSM
├── dut/                             # 被测 FPGA 固件占位 C
│   ├── compare_buf.h                §  1.6.1 内存契约
│   └── compare_buf.c                §  1.6.3 顺序 + DSB 屏障 + 溢出告警
├── stub_cpu/                        # 桩 CPU 侧 svc 占位 C
│   └── svc_compare.c                桩侧 mem_drv_pull_compare_batch 实现
├── tests/                           # pytest 测试底座（79 用例）
│   ├── conftest.py                  fixtures
│   ├── test_block.py                对齐 / 端序 / 位域 / Mixin / round-trip
│   ├── test_mem_access.py           ReadVal / ReadStruct / 1-based / 端序
│   ├── test_compare.py              机制 B 端到端
│   ├── test_errors_and_domain.py    异常树 / Verdict
│   ├── test_retry.py                @retryable 行为
│   ├── test_buffer_registry.py      M12 容量 / crc / 显式 free
│   ├── test_lifecycle.py            FSM 合法 / 非法转移
│   └── test_fpga_adapter.py         Strategy 分发集成
└── examples/
    └── case_typical.py              Autotest 端到端 demo
```

## 模块依赖

```
                                    block.py        (无下游依赖)
                                    domain.py       (无下游依赖)
                                    buffer_registry.py
                                    errors.py
                                       ↑
                                    retry.py
                                    memory.py       (← errors)
                                       ↑
                                    compare.py      (← memory)
                                       ↑
                                    lifecycle.py    (← errors)
                                       ↑
                                    adapters.py     (← compare, memory, lifecycle, domain)
```

合并历史：原 12 个模块 → 9 个核心模块（`dtypes` + `mem_access` → `memory`；`adapter` + `mechanism` + `fpga_adapter` → `adapters`）。

## 快速试跑

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"   # bitstruct + pytest
.venv/bin/pytest -q                 # 79 passed
.venv/bin/python examples/case_typical.py
```

## 设计要点速查

| 概念 | 落点 | 上游 wiki |
|---|---|---|
| **DDR 块头 + 分片填写**（关键预埋）| `DdrBlockHeader`（512B 含 1bit `frag_flag`）+ `fragment_payload(payload, block_id, channel_id, ...)` 自动切片 | 本项目 / 06b § 1.7 |
| **业务层自由拼**（VPORT 头 / 业务 header / 业务字段）| 用 `struct.pack` 任意拼，整体 bytes 交给 `fragment_payload` | 本项目设计 |
| Block 组合 + 512 对齐 | `block.Block` / `Composite` | 06b § 1.7 |
| 大小端 | `Block.ENDIAN`（`<` / `>`，struct 约定）| 06b § 1.7.2 |
| 位域语法糖 | `BitFieldMixin` + `BIT_LAYOUT = [(name, bits), ...]` | 06b § 1.7.3 |
| 反序列化 | `TensorBlock.from_bytes(raw)` round-trip | 本项目 |
| 类型命名空间 | `Datatype.UINT32` / `Datatype.struct.CompareEntry` | 06b § 4.8 |
| 1-based 索引 | `ReadStruct(symbol, sdef, index=1)` | 06b § 4.8.1 |
| 比数协议 | `g_debugCnt` + `g_compAddr[200]`（先填后 incr） | 06b § 1.6 |
| 异常树 | `AutotestError → CommError / TimeoutError → TransientError / ...` | 06b § 3.6 / § 4.5 |
| 错误码翻译 | `code_to_exception(0x4001)` → `DataIntegrityError` | 06b § 3.6 |
| 重试 | `@retryable(max_retries, backoff_s)` 仅对 `TransientError` | 06b § 3.6 |
| 缓冲区注册 | `BufferRegistry.alloc/write/read/free` + crc32 + 不隐式 LRU | 06b § 3.8 |
| 生命周期 FSM | `LifecycleFSM` + `transition(event)` + 非法转移抛 | 06b § 2.7 |
| 双机制 Strategy | `MessageMechanism` (L6A) / `MemoryMechanism` (MemAccess) | 06b § 4.2 |
| Adapter 分发 | `FpgaAdapter` 按 `case.via` 选 A/B | 06b § 4.2 |

## 嵌入到现有 Autotest 项目

把 `src/proto_test/` 整目录拷过去；只硬依赖 `bitstruct`（位域；缺时 `HeaderBlock` / `BitFieldMixin` 抛 RuntimeError）。
不需要 `pytest` / `ruff` 等 dev 依赖即可运行。
