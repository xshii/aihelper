# Prompts: proto-test-env

> 配套 `06b_子wiki_原型测试环境详设.md` 的可消费 Prompt 索引。强 AI 用这些 prompt 给弱 AI 复制 / 改造。

## 主索引

| Prompt | 用途 | 输入 | 输出 |
|---|---|---|---|
| `add-block-type` | 新增一种 DATA_BUF Block 类型 | Block 名 + 字段 + 端序 + 是否含位域 | `block.py` 末尾追加的 `@dataclass` 子类 |
| `add-struct-type` | 注册一个 struct 类型给 ReadStruct 用 | struct 名 + 字段表 | `dtypes.py` 中 `register_struct(...)` 调用 |
| `extend-mem-access` | 扩展 MemAccessAPI 一个新方法 | 方法签名 + 语义 | `mem_access.py` 中新方法 + 对应单测 |
| `add-svc-function` | 桩 CPU 端新增 svc 函数 | svc 名 + 机制 + 入参 / 出参 | `stub_cpu/svc_*.c` 文件 + 错误码段位 |

详细 prompt 内容见 `prompts/`（待补，目前以代码骨架 + README 索引）。

## 直接复制可用的最小 prompt

### Prompt: 新增 Block 类型

```
你是 proto-test-env 项目的 Block 类型生成器。

## 输入
- BlockName: <名字>
- Fields: <字段列表，每行 name : type : 含义>
- Endian: < 或 >（默认 <）
- Bitfield: yes 或 no

## 规则
1. 类放在 src/proto_test/block.py 末尾，顺接 RawBlock 之后
2. 必须 @dataclass(frozen=True, slots=True)，继承 Block
3. 字节对齐版（Bitfield: no）：用 struct.pack(f"{self.ENDIAN}...", ...) 拼
4. 位域版（Bitfield: yes）：用 bitstruct.pack(LAYOUT, ...)；ENDIAN="<" 时调 byteswap
5. _payload 函数 < 20 行；docstring 写"布局"小节，标 offset 字节范围
6. 同步在 tests/test_block.py 加 1 条最小用例

## 自检清单
- [ ] @dataclass(frozen=True, slots=True) 装饰
- [ ] _payload 返回纯净 bytes（不含 padding，512 对齐由基类自动加）
- [ ] ENDIAN 用 ClassVar 而非实例字段
- [ ] 单测覆盖：长度 == n × 512 + 头几个字节字面值
```

### Prompt: 注册新 struct

```
你是 proto-test-env 的 struct 注册生成器。

## 输入
- StructName: <名字>
- Fields: <每行 name : Datatype.X>

## 规则
1. 在 src/proto_test/dtypes.py 末尾 # region 内置 struct 内追加
2. 用 register_struct("Name", [("field", Datatype.X), ...])
3. 顶层赋值给同名变量（方便 from dtypes import StructName）
4. 字段顺序与 DUT C struct 必须严格一致；C 端用 __attribute__((packed))
5. 同步在 tests/test_mem_access.py 加 1 条 ReadStruct 用例
```
