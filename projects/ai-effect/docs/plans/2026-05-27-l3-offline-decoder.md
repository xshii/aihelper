# L3 离线解码器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现把 `trace.jsonl` 的透传 word 还原成有意义算子配置的离线框架(聚合 + 组合式解码 + 外部引用)。

**Architecture:** 三块纯框架,见 [specs/0002-l3-offline-decoder-design.md](../specs/0002-l3-offline-decoder-design.md)。L3-a 聚合阅读器按执行顺序 bracketing 把一个 op 的 `call`+整套 `macro` 聚成 `OpRecord`;L3-b 组合式解码器用 Python 声明式 schema(`U/I/Ref/Atom/Layout/Dispatch`)消费 word 流出命名字段树,引擎 `match` 分发、纯函数;L3-c 的 `Ref` 字段经注入的 `BlobResolver` 端口取外部 word 后同引擎递归解码。真实位宽/布局是项目配置,框架不写死。

**Tech Stack:** Python 3.10,`pytest`,`import-linter`。无第三方依赖(纯标准库)。

> **细化 spec 0002**:真实 trace 把公共头放在其**参数名**下(如 `"h":{"opid":...}`),不是 `"common"`。故 `OpRecord` 用 `fields: dict`(call 记录里除 kind/op/fn 外的全部),`Dispatch.source` 是**点路径**(如 `"h.optype"`)。位序定为 **LSB-first**、字长由 `word_bits` 参数给(默认 32);均可随项目数据 P1 调整。

---

## File Structure

- `pa_debug/l3_analyzer/__init__.py` — 空包标记。
- `pa_debug/l3_analyzer/model.py` — `MacroHit` / `OpRecord` 数据类 + `DecodeError`。
- `pa_debug/l3_analyzer/reader.py` — `aggregate(records)` 聚合(纯)+ `load_trace(path)` IO 边界。
- `pa_debug/l3_analyzer/schema.py` — schema *类型*(端口):`U/I/Ref/Field/Atom/Layout/Dispatch`。
- `pa_debug/l3_analyzer/resolver.py` — `BlobResolver` Protocol(端口)。
- `pa_debug/l3_analyzer/decoder.py` — `_BitReader` / `_dig` / `decode_op` 引擎。
- `tests/unit/test_l3_reader.py` / `tests/unit/test_l3_decoder.py` — 单元测试(纯,免 libclang)。
- `pyproject.toml` — import-linter 契约加 `l3_analyzer`。

> schema *实例* 的项目加载器(`schema_loader`,仿 rules_loader)等真实项目 schema 出现再加(YAGNI,本计划不做)。

---

## Task 1: L3-a 聚合阅读器

**Files:**
- Create: `pa_debug/l3_analyzer/__init__.py`
- Create: `pa_debug/l3_analyzer/model.py`
- Create: `pa_debug/l3_analyzer/reader.py`
- Test: `tests/unit/test_l3_reader.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_l3_reader.py
import pytest

from pa_debug.l3_analyzer.model import DecodeError
from pa_debug.l3_analyzer.reader import aggregate, load_trace


def test_aggregate_groups_call_with_following_macros():
    records = [
        {"kind": "call", "op": "pa_conv", "fn": "layer3", "h": {"opid": 42}, "ish": 8},
        {"kind": "macro", "macro": "hac_3r", "words": [1, 2, 3]},
        {"kind": "call", "op": "pa_pool", "fn": "layer3", "h": {"opid": 43}},
        {"kind": "macro", "macro": "hac_2r", "words": [4, 5]},
    ]
    ops = aggregate(records)
    assert [o.op for o in ops] == ["pa_conv", "pa_pool"]
    assert ops[0].fields == {"h": {"opid": 42}, "ish": 8}
    assert [(m.name, m.words) for m in ops[0].macros] == [("hac_3r", [1, 2, 3])]
    assert [m.name for m in ops[1].macros] == ["hac_2r"]


def test_macro_before_any_call_raises():
    with pytest.raises(DecodeError):
        aggregate([{"kind": "macro", "macro": "x", "words": [1]}])


def test_load_trace_reads_jsonl(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text('{"kind":"call","op":"a"}\n\n{"kind":"macro","macro":"m","words":[1]}\n')
    assert load_trace(p) == [
        {"kind": "call", "op": "a"},
        {"kind": "macro", "macro": "m", "words": [1]},
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_l3_reader.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'pa_debug.l3_analyzer'`.

- [ ] **Step 3: Write minimal implementation**

```python
# pa_debug/l3_analyzer/__init__.py
```

```python
# pa_debug/l3_analyzer/model.py
"""L3 数据模型。OpRecord 是聚合产物,喂给解码器。"""

from __future__ import annotations

from dataclasses import dataclass, field


class DecodeError(Exception):
    """trace 边界错误(坏记录 / 缺 op-kind / word 流不足 / 未知 blob)。"""


@dataclass
class MacroHit:
    name: str
    words: list[int] = field(default_factory=list)


@dataclass
class OpRecord:
    op: str
    fn: str | None
    fields: dict  # call 记录里除 kind/op/fn 外的全部(含公共头结构体、指针、标量)
    macros: list[MacroHit] = field(default_factory=list)
```

```python
# pa_debug/l3_analyzer/reader.py
"""L3-a:读 trace + 按执行顺序 bracketing 把每个 op 的 call+整套 macro 聚成 OpRecord。"""

from __future__ import annotations

import json
from pathlib import Path

from .model import DecodeError, MacroHit, OpRecord

_META = ("kind", "op", "fn")


def aggregate(records: list[dict]) -> list[OpRecord]:
    """一条 call 开桶,后续 macro 归入当前桶,直到下一条 call(Q3 已确认顺序可靠)。"""
    ops: list[OpRecord] = []
    for rec in records:
        kind = rec.get("kind")
        if kind == "call":
            fields = {k: v for k, v in rec.items() if k not in _META}
            ops.append(OpRecord(op=rec["op"], fn=rec.get("fn"), fields=fields))
        elif kind == "macro":
            if not ops:
                raise DecodeError("macro 记录出现在任何 call 之前,无法归属")
            ops[-1].macros.append(MacroHit(name=rec["macro"], words=list(rec["words"])))
        else:
            raise DecodeError(f"未知 trace 记录 kind: {kind!r}")
    return ops


def load_trace(path: str | Path) -> list[dict]:
    lines = Path(path).read_text().splitlines()
    return [json.loads(ln) for ln in lines if ln.strip()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_l3_reader.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add pa_debug/l3_analyzer/__init__.py pa_debug/l3_analyzer/model.py pa_debug/l3_analyzer/reader.py tests/unit/test_l3_reader.py
git commit -m "ai-effect: L3-a 聚合阅读器(trace → OpRecord)"
```

---

## Task 2: L3-b 标量解码 + 判别 dispatch

**Files:**
- Create: `pa_debug/l3_analyzer/schema.py`
- Create: `pa_debug/l3_analyzer/decoder.py`
- Test: `tests/unit/test_l3_decoder.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_l3_decoder.py
import pytest

from pa_debug.l3_analyzer.decoder import decode_op
from pa_debug.l3_analyzer.model import DecodeError, MacroHit, OpRecord
from pa_debug.l3_analyzer.schema import I, U, Atom, Dispatch, Field, Layout


def test_decode_scalar_fields_lsb_first_by_op_kind():
    op = OpRecord("pa_conv", "layer3", {"h": {"optype": "CONV"}}, [MacroHit("hac_2r", [0xABCD])])
    schema = Dispatch(
        source="h.optype",
        table={"CONV": Layout([Atom("ctrl", [Field("lo", U(8)), Field("hi", U(8))])])},
    )
    out = decode_op(op, schema, word_bits=16)
    assert out["op"] == "pa_conv"
    assert out["config"] == {"ctrl": {"lo": 0xCD, "hi": 0xAB}}  # LSB-first


def test_signed_field_sign_extends():
    op = OpRecord("x", None, {"k": "A"}, [MacroHit("m", [0xF])])  # 4 位全 1 = -1
    schema = Dispatch("k", {"A": Layout([Atom("a", [Field("s", I(4))])])})
    assert decode_op(op, schema, word_bits=4)["config"]["a"]["s"] == -1


def test_unknown_op_kind_raises():
    op = OpRecord("x", None, {"h": {"optype": "NOPE"}}, [])
    with pytest.raises(DecodeError):
        decode_op(op, Dispatch("h.optype", {}), word_bits=16)


def test_missing_op_kind_path_raises():
    op = OpRecord("x", None, {"h": {}}, [])
    with pytest.raises(DecodeError):
        decode_op(op, Dispatch("h.optype", {"CONV": Layout([])}), word_bits=16)


def test_short_word_stream_raises():
    op = OpRecord("x", None, {"k": "A"}, [MacroHit("m", [1])])
    schema = Dispatch("k", {"A": Layout([Atom("a", [Field("f", U(40))])])})
    with pytest.raises(DecodeError):
        decode_op(op, schema, word_bits=16)  # 16 位 < 40
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_l3_decoder.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'pa_debug.l3_analyzer.schema'`.

- [ ] **Step 3: Write minimal implementation**

```python
# pa_debug/l3_analyzer/schema.py
"""L3 解码 schema 的*类型*(端口)。项目写*实例*。Atom 嵌套 / Enum 暂不做(YAGNI)。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class U:
    bits: int  # 无符号位宽


@dataclass
class I:  # noqa: E742 - 语义上是 signed,与 U 对称
    bits: int  # 有符号位宽(补码)


@dataclass
class Field:
    name: str
    type: U | I  # Task 3 加入 Ref


@dataclass
class Atom:
    name: str
    fields: list[Field]


@dataclass
class Layout:
    atoms: list[Atom]


@dataclass
class Dispatch:
    source: str  # 点路径,从 OpRecord.fields 取 op-kind
    table: dict[str, Layout]
```

```python
# pa_debug/l3_analyzer/decoder.py
"""L3-b 引擎:按 op-kind 选 Layout,顺序消费 word 流出命名字段树。纯函数。"""

from __future__ import annotations

from .model import DecodeError, OpRecord
from .schema import Atom, Dispatch, I, U


class _BitReader:
    """word 流拉平成一个大整数,LSB-first:word[0] 在低位。"""

    def __init__(self, words: list[int], word_bits: int) -> None:
        self._value = 0
        mask = (1 << word_bits) - 1
        for k, w in enumerate(words):
            self._value |= (w & mask) << (k * word_bits)
        self._total = len(words) * word_bits
        self._pos = 0

    def read(self, n: int) -> int:
        if self._pos + n > self._total:
            raise DecodeError(f"word 流不足:需 {n} 位,剩 {self._total - self._pos} 位")
        value = (self._value >> self._pos) & ((1 << n) - 1)
        self._pos += n
        return value


def _dig(fields: dict, path: str) -> object:
    cur: object = fields
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            raise DecodeError(f"op-kind 路径 {path!r} 在记录里找不到")
        cur = cur[key]
    return cur


def _decode_field(ftype: object, reader: _BitReader) -> int:
    match ftype:
        case U(bits=b):
            return reader.read(b)
        case I(bits=b):
            v = reader.read(b)
            return v - (1 << b) if v >> (b - 1) else v
        case _:
            raise DecodeError(f"不支持的字段类型: {ftype!r}")


def _decode_atom(atom: Atom, reader: _BitReader) -> dict:
    return {f.name: _decode_field(f.type, reader) for f in atom.fields}


def decode_op(op: OpRecord, dispatch: Dispatch, word_bits: int = 32) -> dict:
    kind = _dig(op.fields, dispatch.source)
    if kind not in dispatch.table:
        raise DecodeError(f"未知 op-kind: {kind!r}")
    layout = dispatch.table[kind]
    words = [w for m in op.macros for w in m.words]
    reader = _BitReader(words, word_bits)
    config = {atom.name: _decode_atom(atom, reader) for atom in layout.atoms}
    return {"op": op.op, "fn": op.fn, "fields": op.fields, "config": config}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_l3_decoder.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add pa_debug/l3_analyzer/schema.py pa_debug/l3_analyzer/decoder.py tests/unit/test_l3_decoder.py
git commit -m "ai-effect: L3-b 组合式解码器(标量字段 + op-kind 判别)"
```

---

## Task 3: L3-c 外部引用解析(REF + resolver,递归)

**Files:**
- Create: `pa_debug/l3_analyzer/resolver.py`
- Modify: `pa_debug/l3_analyzer/schema.py`(加 `Ref`,扩 `Field.type`)
- Modify: `pa_debug/l3_analyzer/decoder.py`(`Ref` 分支 + resolver 透传)
- Test: `tests/unit/test_l3_decoder.py`(追加)

- [ ] **Step 1: Write the failing test (追加到 test_l3_decoder.py)**

```python
from pa_debug.l3_analyzer.schema import Ref


class _FakeResolver:
    def __init__(self, table: dict[tuple[str, int], list[int]]) -> None:
        self.table = table

    def fetch(self, blob: str, addr: int) -> list[int]:
        return self.table[(blob, addr)]


def test_ref_field_follows_address_and_recursively_decodes():
    sub = Layout([Atom("w", [Field("v", U(8))])])
    op = OpRecord("x", None, {"k": "A"}, [MacroHit("m", [5, 0x7F])])
    schema = Dispatch("k", {"A": Layout([Atom("hdr", [Field("ptr", Ref(8, "weights", sub))])])})
    resolver = _FakeResolver({("weights", 5): [0x7F]})
    out = decode_op(op, schema, resolver=resolver, word_bits=8)
    assert out["config"]["hdr"]["ptr"] == {"w": {"v": 0x7F}}


def test_ref_without_resolver_raises():
    sub = Layout([Atom("w", [Field("v", U(8))])])
    op = OpRecord("x", None, {"k": "A"}, [MacroHit("m", [5])])
    schema = Dispatch("k", {"A": Layout([Atom("hdr", [Field("ptr", Ref(8, "b", sub))])])})
    with pytest.raises(DecodeError):
        decode_op(op, schema, word_bits=8)  # 没注入 resolver
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_l3_decoder.py -q`
Expected: FAIL — `ImportError: cannot import name 'Ref'`.

- [ ] **Step 3: Write minimal implementation**

```python
# pa_debug/l3_analyzer/resolver.py
"""外部内容解析端口。具体实现由组合根注入(读本地文件 / 内存等)。"""

from __future__ import annotations

from typing import Protocol


class BlobResolver(Protocol):
    def fetch(self, blob: str, addr: int) -> list[int]:
        """返回 blob 在 addr 处的 word 序列(字节→word 的换算由适配器按真实格式处理)。"""
        ...
```

在 `schema.py` 加 `Ref`(放在 `Field` 之前),并把 `Field.type` 改为 `U | I | Ref`:

```python
@dataclass
class Ref:
    bits: int  # 地址位宽
    blob: str  # 外部内容名
    schema: "Layout"  # 取回内容用这套 Layout 递归解码
```

```python
# Field.type 改为:
    type: "U | I | Ref"
```

在 `decoder.py`:把 `resolver` 透传进 `decode_op`/`_decode_atom`/`_decode_field`,并加 `Ref` 分支:

```python
from .resolver import BlobResolver  # 顶部 import
from .schema import Atom, Dispatch, I, Ref, U  # 加 Ref


def decode_op(
    op: OpRecord,
    dispatch: Dispatch,
    resolver: BlobResolver | None = None,
    word_bits: int = 32,
) -> dict:
    kind = _dig(op.fields, dispatch.source)
    if kind not in dispatch.table:
        raise DecodeError(f"未知 op-kind: {kind!r}")
    layout = dispatch.table[kind]
    words = [w for m in op.macros for w in m.words]
    reader = _BitReader(words, word_bits)
    config = {a.name: _decode_atom(a, reader, resolver, word_bits) for a in layout.atoms}
    return {"op": op.op, "fn": op.fn, "fields": op.fields, "config": config}


def _decode_atom(atom: Atom, reader: _BitReader, resolver, word_bits: int) -> dict:
    return {f.name: _decode_field(f.type, reader, resolver, word_bits) for f in atom.fields}


def _decode_field(ftype: object, reader: _BitReader, resolver, word_bits: int):
    match ftype:
        case U(bits=b):
            return reader.read(b)
        case I(bits=b):
            v = reader.read(b)
            return v - (1 << b) if v >> (b - 1) else v
        case Ref(bits=b, blob=blob, schema=sub):
            if resolver is None:
                raise DecodeError("遇到 REF 字段但未注入 resolver")
            addr = reader.read(b)
            sub_reader = _BitReader(resolver.fetch(blob, addr), word_bits)
            return {a.name: _decode_atom(a, sub_reader, resolver, word_bits) for a in sub.atoms}
        case _:
            raise DecodeError(f"不支持的字段类型: {ftype!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_l3_decoder.py -q`
Expected: PASS (7 passed)。

- [ ] **Step 5: Commit**

```bash
git add pa_debug/l3_analyzer/resolver.py pa_debug/l3_analyzer/schema.py pa_debug/l3_analyzer/decoder.py tests/unit/test_l3_decoder.py
git commit -m "ai-effect: L3-c 外部引用(REF + BlobResolver 递归解码)"
```

---

## Task 4: import-linter 契约纳入 l3_analyzer

**Files:**
- Modify: `pyproject.toml:37-41`(layers 契约)

- [ ] **Step 1: 改契约**

把现有 layers 契约的 `layers` 行改为:

```toml
[[tool.importlinter.contracts]]
name = "单向分层依赖(组合根 cli 在上,l1/l3 同层独立)"
type = "layers"
layers = ["pa_debug.cli", "pa_debug.l1_transformer | pa_debug.l3_analyzer"]
```

- [ ] **Step 2: 跑契约 + 全量 gate**

Run:
```
.venv/bin/lint-imports
.venv/bin/python -m pytest -q
.venv/bin/ruff check pa_debug tests && .venv/bin/ruff format --check pa_debug tests
.venv/bin/mypy --ignore-missing-imports pa_debug
```
Expected: lint-imports `Contracts: 1 kept, 0 broken`;pytest 全 PASS;ruff/mypy 干净。
(`l3_analyzer` 不 import `cli`/`l1_transformer`,契约保持。)

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "ai-effect: import-linter 契约纳入 l3_analyzer(与 l1 同层独立)"
```

---

## 范围外(本计划不做,留作后续)

- `schema_loader`(动态加载项目 schema 目录)—— 等真实项目 schema 出现再加。
- CLI `decode` 子命令 + 真实 `BlobResolver` 实现 —— 需项目数据 P1–P4(字长/字节序、op-kind 来源、真实 Layout、外部文件格式)。
- Atom 嵌套、`Enum` 字段、跨 op 的依赖图(commopheader `aopid` 等)。
