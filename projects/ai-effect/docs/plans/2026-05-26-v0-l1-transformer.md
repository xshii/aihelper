# V0 Milestone 1 — L1 Compile-time Transformer 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 `pa-debug instrument`:输入含 `PA_INSTR_CONV(...)` 的 C 源码 + stub header,自动在宏调用前后插入 `pa_hook_before/after` 调用,输出新 `.c` + 站点清单 `sites.json`,原文件不动。

**Architecture:** 纯 Python L1 层。libclang 负责"能解析含自定义宏的源码 + 定位宏展开点";token 级参数分割器(本里程碑核心难点,评审 D)负责提取宏参数;声明式 Rule 描述符(评审 C)声明参数语义;基于 source-location 的 Edit 模型倒序改写源码字符串。本里程碑**不涉及** L2/L3/L4,只产出可独立验证的插桩器。

**Tech Stack:** Python 3.14, `libclang`(PyPI,绑定 + 内置 libclang.dylib),`pytest`,`click`(CLI)。

**范围边界(对齐 ADR 0001):**
- 只 `DUMP_AND_RUN`,无 SKIP → 生成的 hook 调用**不需要 `if` 包裹**,纯前后插入即可。
- 只处理**语句位置**的宏(独立成句);表达式位置的宏进黑名单(评审 H)。
- 生成的 hook 调用采用**简化可读形式**(`pa_hook_before("CONV", site_id, in, w, out)`),
  完整的 `pa_hook_ctx_t` ABI marshalling 是 M3(L2)的事,本里程碑不做。

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `pyproject.toml` | 包定义 + 依赖(libclang/click/pytest)+ `pa-debug` entry point |
| `pa_debug/__init__.py` | 包标记 |
| `pa_debug/l1_transformer/__init__.py` | 子包标记 |
| `pa_debug/l1_transformer/arg_splitter.py` | **核心**:把宏实参文本切成参数列表(处理嵌套括号/字符串/逗号) |
| `pa_debug/l1_transformer/frontend.py` | libclang 薄封装:解析 TU(开 detailed preprocessing record)、定位宏实例、取 token |
| `pa_debug/l1_transformer/macro_extractor.py` | 组合 frontend + arg_splitter,产出 `MacroCall`(宏名/参数/offset) |
| `pa_debug/l1_transformer/rules.py` | 声明式 `Arg`/`Rule` 描述符 + `PA_INSTR_CONV` 规则 |
| `pa_debug/l1_transformer/edits.py` | `Edit` dataclass + 倒序应用 |
| `pa_debug/l1_transformer/transformer.py` | 编排:解析→匹配→产生 Edit→应用→输出 .c + sites.json |
| `pa_debug/cli.py` | `pa-debug instrument <src>` |
| `stubs/pa_intrinsics.h` | stub header,让 Clang 认识 `PA_INSTR_CONV` 与 `pa_tensor_t` |
| `examples/conv.c` | 端到端 fixture 输入 |
| `tests/unit/test_arg_splitter.py` | arg_splitter 单测 |
| `tests/unit/test_frontend.py` | frontend 解析单测(需 libclang) |
| `tests/unit/test_macro_extractor.py` | 宏调用提取单测 |
| `tests/unit/test_edits.py` | Edit 倒序应用单测 |
| `tests/integration/test_instrument.py` | 端到端:input.c → expected.c diff |
| `tests/fixtures/instrument/conv.input.c` | 集成 fixture 输入 |
| `tests/fixtures/instrument/conv.expected.c` | 集成 fixture 期望输出 |

---

## Task 1: Python 包骨架 + libclang 环境就绪

**Files:**
- Create: `pyproject.toml`, `pa_debug/__init__.py`, `pa_debug/l1_transformer/__init__.py`
- Create: `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`

- [ ] **Step 1: 写 pyproject.toml**

```toml
[project]
name = "pa-debug"
version = "0.0.1"
description = "算子调试与对照工具 (L1 transformer)"
requires-python = ">=3.11"
dependencies = ["libclang>=16", "click>=8.1"]

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
pa-debug = "pa_debug.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["pa_debug*"]
```

- [ ] **Step 2: 建空 `__init__.py`**

`pa_debug/__init__.py` 内容:`"""pa-debug: 算子调试与对照工具。"""`
其余 `__init__.py` 留空。

- [ ] **Step 3: 创建 venv 并安装**

Run:
```bash
cd /Users/gakki/dev/aihelper/projects/ai-effect
python3 -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'
```
Expected: 安装成功,`libclang` 与 `click`、`pytest` 就位。

- [ ] **Step 4: 验证 libclang 能加载本机 libclang.dylib**

写临时脚本或直接执行:
```bash
.venv/bin/python -c "import clang.cindex as c; c.Index.create(); print('libclang OK')"
```
Expected: 打印 `libclang OK`。
**若失败**(找不到 libclang):在 `frontend.py` 里用
`clang.cindex.Config.set_library_file('/opt/homebrew/opt/llvm/lib/libclang.dylib')`
回退(本机已确认该路径存在)。把这一步的处理放进 Task 3 的 frontend。

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml pa_debug/ tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py
git commit -m "chore(ai-effect): L1 包骨架 + libclang 环境就绪"
```

---

## Task 2: arg_splitter —— 宏实参分割器(核心难点 D)

**Files:**
- Create: `pa_debug/l1_transformer/arg_splitter.py`
- Test: `tests/unit/test_arg_splitter.py`

> 这是本里程碑风险最高、最该先做的纯算法单元。libclang 不给结构化宏参数,必须自己切。
> 纯 Python、无 libclang 依赖 → 可完全 TDD。

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_arg_splitter.py
import pytest
from pa_debug.l1_transformer.arg_splitter import split_args

def test_simple():
    assert split_args("a, b, c") == ["a", "b", "c"]

def test_nested_call_comma_protected():
    assert split_args("a, foo(b, c), d") == ["a", "foo(b, c)", "d"]

def test_nested_brackets_and_braces():
    assert split_args("a, x[1, 2], (int[]){3, 4}") == ["a", "x[1, 2]", "(int[]){3, 4}"]

def test_string_with_comma():
    assert split_args('a, "x, y", c') == ["a", '"x, y"', "c"]

def test_char_literal_with_comma():
    assert split_args("a, ',', c") == ["a", "','", "c"]

def test_whitespace_trimmed():
    assert split_args("  a ,  b  ") == ["a", "b"]

def test_empty():
    assert split_args("") == []

def test_single():
    assert split_args("only") == ["only"]
```

- [ ] **Step 2: 运行,确认失败**

Run: `.venv/bin/pytest tests/unit/test_arg_splitter.py -v`
Expected: FAIL — `ModuleNotFoundError` / `split_args` 未定义。

- [ ] **Step 3: 实现**

```python
# pa_debug/l1_transformer/arg_splitter.py
"""把宏实参文本切成参数列表,正确处理嵌套括号/方括号/花括号、字符串与字符字面量里的逗号。"""


def split_args(arg_text: str) -> list[str]:
    args: list[str] = []
    buf: list[str] = []
    depth = 0
    quote: str | None = None
    escaped = False
    for ch in arg_text:
        if quote is not None:
            buf.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch in "([{":
            depth += 1
            buf.append(ch)
        elif ch in ")]}":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail or args:
        args.append(tail)
    return args
```

- [ ] **Step 4: 运行,确认通过**

Run: `.venv/bin/pytest tests/unit/test_arg_splitter.py -v`
Expected: 8 passed。

- [ ] **Step 5: Commit**

```bash
git add pa_debug/l1_transformer/arg_splitter.py tests/unit/test_arg_splitter.py
git commit -m "feat(ai-effect): L1 宏实参分割器 (含嵌套/字符串/字符字面量)"
```

---

## Task 3: frontend —— libclang 薄封装

**Files:**
- Create: `pa_debug/l1_transformer/frontend.py`
- Create: `stubs/pa_intrinsics.h`
- Test: `tests/unit/test_frontend.py`

- [ ] **Step 1: 写 stub header**

```c
/* stubs/pa_intrinsics.h — 让 Clang 能解析含自定义宏的源码 */
#ifndef PA_INTRINSICS_H
#define PA_INTRINSICS_H

typedef struct { void* data; int ndim; int shape[8]; int dtype; } pa_tensor_t;

/* 保留参数列表的空展开:Clang 认得它是函数式宏,展开为空,不影响 AST 其余部分 */
#define PA_INSTR_CONV(op_id, in, w, out, ish, wsh, osh) do {} while (0)

#endif
```

- [ ] **Step 2: 写失败测试**

```python
# tests/unit/test_frontend.py
from pa_debug.l1_transformer.frontend import parse_source, macro_instantiations

SRC = '''#include "pa_intrinsics.h"
void f(pa_tensor_t* in, pa_tensor_t* w, pa_tensor_t* out) {
    PA_INSTR_CONV(c0, in, w, out, s1, s2, s3);
}
'''

def test_parse_no_fatal_errors(tmp_path, stub_include_args):
    src = tmp_path / "f.c"
    src.write_text(SRC)
    tu = parse_source(str(src), args=stub_include_args)
    fatals = [d for d in tu.diagnostics if d.severity >= 4]
    assert fatals == []

def test_finds_macro_instantiation(tmp_path, stub_include_args):
    src = tmp_path / "f.c"
    src.write_text(SRC)
    tu = parse_source(str(src), args=stub_include_args)
    names = [m.spelling for m in macro_instantiations(tu)]
    assert "PA_INSTR_CONV" in names
```

加 fixture(conftest):

```python
# tests/conftest.py
import pathlib
import pytest

@pytest.fixture
def stub_include_args():
    stubs = pathlib.Path(__file__).resolve().parents[1] / "stubs"
    return ["-I", str(stubs)]
```

- [ ] **Step 3: 运行,确认失败**

Run: `.venv/bin/pytest tests/unit/test_frontend.py -v`
Expected: FAIL — `parse_source` 未定义。

- [ ] **Step 4: 实现 frontend**

```python
# pa_debug/l1_transformer/frontend.py
"""libclang 薄封装:解析 TU(开 detailed preprocessing record)、遍历宏实例、取 token。"""
import clang.cindex as ci

_FALLBACK_LIB = "/opt/homebrew/opt/llvm/lib/libclang.dylib"
_configured = False


def _ensure_lib() -> None:
    global _configured
    if _configured:
        return
    try:
        ci.Index.create()
    except ci.LibclangError:
        ci.Config.set_library_file(_FALLBACK_LIB)
    _configured = True


def parse_source(path: str, args: list[str] | None = None) -> ci.TranslationUnit:
    _ensure_lib()
    index = ci.Index.create()
    return index.parse(
        path,
        args=args or [],
        options=ci.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD,
    )


def macro_instantiations(tu: ci.TranslationUnit):
    for cur in tu.cursor.walk_preorder():
        if cur.kind == ci.CursorKind.MACRO_INSTANTIATION:
            yield cur
```

- [ ] **Step 5: 运行,确认通过**

Run: `.venv/bin/pytest tests/unit/test_frontend.py -v`
Expected: 2 passed。(若 libclang 加载失败,fallback 路径生效后应通过。)

- [ ] **Step 6: Commit**

```bash
git add pa_debug/l1_transformer/frontend.py stubs/pa_intrinsics.h tests/unit/test_frontend.py tests/conftest.py
git commit -m "feat(ai-effect): L1 libclang frontend + stub header + 宏实例定位"
```

---

## Task 4: macro_extractor —— 提取宏调用(名/参数/offset)

**Files:**
- Create: `pa_debug/l1_transformer/macro_extractor.py`
- Test: `tests/unit/test_macro_extractor.py`

> 宏实例 cursor 的 extent 常只覆盖宏名。用 token 流从宏名处向后做**括号平衡**找到完整
> `(...)`,再用 `split_args` 切参数。offset 用字节偏移,供 Edit 使用。

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_macro_extractor.py
from pa_debug.l1_transformer.frontend import parse_source
from pa_debug.l1_transformer.macro_extractor import find_macro_calls

SRC = '''#include "pa_intrinsics.h"
void f(pa_tensor_t* in, pa_tensor_t* w, pa_tensor_t* out) {
    PA_INSTR_CONV(c0, in, w, out, s1, s2, s3);
}
'''

def test_extract_one_call(tmp_path, stub_include_args):
    src = tmp_path / "f.c"
    src.write_text(SRC)
    tu = parse_source(str(src), args=stub_include_args)
    calls = find_macro_calls(tu, str(src), "PA_INSTR_CONV")
    assert len(calls) == 1
    c = calls[0]
    assert c.name == "PA_INSTR_CONV"
    assert c.args == ["c0", "in", "w", "out", "s1", "s2", "s3"]
    # offset 落在源码中宏名起始处
    assert SRC.encode()[c.start_offset:].startswith(b"PA_INSTR_CONV")
    # end_offset 紧跟右括号
    assert SRC.encode()[c.end_offset - 1:c.end_offset] == b")"
```

- [ ] **Step 2: 运行,确认失败**

Run: `.venv/bin/pytest tests/unit/test_macro_extractor.py -v`
Expected: FAIL — `find_macro_calls` 未定义。

- [ ] **Step 3: 实现**

```python
# pa_debug/l1_transformer/macro_extractor.py
"""从 TU 提取指定宏的调用:宏名、参数列表、源码字节区间。"""
from dataclasses import dataclass

import clang.cindex as ci

from .arg_splitter import split_args
from .frontend import macro_instantiations


@dataclass
class MacroCall:
    name: str
    args: list[str]
    start_offset: int   # 宏名首字节
    end_offset: int     # 右括号后一字节


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def find_macro_calls(tu: ci.TranslationUnit, path: str, macro_name: str) -> list[MacroCall]:
    data = _read_bytes(path)
    calls: list[MacroCall] = []
    for cur in macro_instantiations(tu):
        if cur.spelling != macro_name:
            continue
        start = cur.extent.start.offset
        # 从宏名处向后括号平衡,找到完整实参区间
        i = data.find(b"(", start)
        if i < 0:
            continue
        depth = 0
        j = i
        while j < len(data):
            ch = data[j:j + 1]
            if ch == b"(":
                depth += 1
            elif ch == b")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        arg_text = data[i + 1:j].decode()
        calls.append(MacroCall(
            name=macro_name,
            args=split_args(arg_text),
            start_offset=start,
            end_offset=j + 1,
        ))
    return calls
```

- [ ] **Step 4: 运行,确认通过**

Run: `.venv/bin/pytest tests/unit/test_macro_extractor.py -v`
Expected: 1 passed。

- [ ] **Step 5: Commit**

```bash
git add pa_debug/l1_transformer/macro_extractor.py tests/unit/test_macro_extractor.py
git commit -m "feat(ai-effect): L1 宏调用提取 (token 括号平衡 + 参数切分)"
```

---

## Task 5: rules —— 声明式参数语义描述符(评审 C)

**Files:**
- Create: `pa_debug/l1_transformer/rules.py`
- Test: `tests/unit/test_rules.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_rules.py
from pa_debug.l1_transformer.rules import Arg, Rule, CONV_RULE

def test_conv_rule_shape():
    assert CONV_RULE.macro == "PA_INSTR_CONV"
    assert CONV_RULE.op == "CONV"
    roles = [a.role for a in CONV_RULE.args]
    assert roles == ["id", "in", "in", "out", "meta", "meta", "meta"]

def test_inputs_outputs_helpers():
    # 第 0 个 arg 是 id,第 1/2 是 in,第 3 是 out
    assert CONV_RULE.input_indices() == [1, 2]
    assert CONV_RULE.output_indices() == [3]
    assert CONV_RULE.id_index() == 0
```

- [ ] **Step 2: 运行,确认失败**

Run: `.venv/bin/pytest tests/unit/test_rules.py -v`
Expected: FAIL — 模块/符号未定义。

- [ ] **Step 3: 实现**

```python
# pa_debug/l1_transformer/rules.py
"""声明式规则:每种宏一条,声明每个参数的语义角色(id/in/out/meta)。"""
from dataclasses import dataclass, field


@dataclass
class Arg:
    name: str
    role: str                       # "id" | "in" | "out" | "meta"
    dtype: str | None = None
    shape_from: str | None = None   # 引用另一参数名作为 shape 来源


@dataclass
class Rule:
    macro: str
    op: str
    args: list[Arg] = field(default_factory=list)

    def _indices(self, role: str) -> list[int]:
        return [i for i, a in enumerate(self.args) if a.role == role]

    def input_indices(self) -> list[int]:
        return self._indices("in")

    def output_indices(self) -> list[int]:
        return self._indices("out")

    def id_index(self) -> int:
        ids = self._indices("id")
        return ids[0] if ids else -1


CONV_RULE = Rule(
    macro="PA_INSTR_CONV",
    op="CONV",
    args=[
        Arg("op_id", role="id"),
        Arg("in", role="in", dtype="f16", shape_from="ish"),
        Arg("w", role="in", dtype="f16", shape_from="wsh"),
        Arg("out", role="out", dtype="f16", shape_from="osh"),
        Arg("ish", role="meta"),
        Arg("wsh", role="meta"),
        Arg("osh", role="meta"),
    ],
)
```

- [ ] **Step 4: 运行,确认通过**

Run: `.venv/bin/pytest tests/unit/test_rules.py -v`
Expected: 2 passed。

- [ ] **Step 5: Commit**

```bash
git add pa_debug/l1_transformer/rules.py tests/unit/test_rules.py
git commit -m "feat(ai-effect): L1 声明式宏参数语义规则 + CONV 规则"
```

---

## Task 6: edits —— Edit 模型与倒序应用

**Files:**
- Create: `pa_debug/l1_transformer/edits.py`
- Test: `tests/unit/test_edits.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_edits.py
from pa_debug.l1_transformer.edits import Edit, apply_edits

def test_pure_insertions_keep_offsets_valid():
    src = "AAABBB"
    edits = [Edit(offset=3, length=0, replacement="<>"), Edit(offset=0, length=0, replacement="[]")]
    assert apply_edits(src, edits) == "[]AAA<>BBB"

def test_replacement():
    src = "hello world"
    edits = [Edit(offset=6, length=5, replacement="there")]
    assert apply_edits(src, edits) == "hello there"

def test_multiple_edits_applied_in_reverse():
    src = "0123456789"
    edits = [Edit(offset=2, length=0, replacement="A"), Edit(offset=8, length=0, replacement="B")]
    assert apply_edits(src, edits) == "01A234567B89"
```

- [ ] **Step 2: 运行,确认失败**

Run: `.venv/bin/pytest tests/unit/test_edits.py -v`
Expected: FAIL — 未定义。

- [ ] **Step 3: 实现**

```python
# pa_debug/l1_transformer/edits.py
"""基于 source offset 的源码改写。所有 Edit 按 offset 倒序应用,避免位置失效。"""
from dataclasses import dataclass


@dataclass
class Edit:
    offset: int
    length: int          # 0 = 纯插入
    replacement: str


def apply_edits(source: str, edits: list[Edit]) -> str:
    for e in sorted(edits, key=lambda x: x.offset, reverse=True):
        source = source[:e.offset] + e.replacement + source[e.offset + e.length:]
    return source
```

- [ ] **Step 4: 运行,确认通过**

Run: `.venv/bin/pytest tests/unit/test_edits.py -v`
Expected: 3 passed。

- [ ] **Step 5: Commit**

```bash
git add pa_debug/l1_transformer/edits.py tests/unit/test_edits.py
git commit -m "feat(ai-effect): L1 Edit 模型 + 倒序应用"
```

---

## Task 7: transformer —— 编排插桩 + 输出 .c + sites.json

**Files:**
- Create: `pa_debug/l1_transformer/transformer.py`
- Test: `tests/integration/test_instrument.py`
- Create: `tests/fixtures/instrument/conv.input.c`, `tests/fixtures/instrument/conv.expected.c`

> offset 偏移会因换行/编码影响,集成测试用**字符串规范化比对**(去掉行尾空白后逐行比),
> 不做脆弱的逐字节比对。

- [ ] **Step 1: 写 fixture 输入**

```c
/* tests/fixtures/instrument/conv.input.c */
#include "pa_intrinsics.h"

void f(pa_tensor_t* in, pa_tensor_t* w, pa_tensor_t* out) {
    PA_INSTR_CONV(c0, in, w, out, s1, s2, s3);
}
```

- [ ] **Step 2: 写 fixture 期望输出**

```c
/* tests/fixtures/instrument/conv.expected.c */
#include "pa_intrinsics.h"

void f(pa_tensor_t* in, pa_tensor_t* w, pa_tensor_t* out) {
    pa_hook_before("CONV", "CONV@conv.input.c:4", in, w);
    PA_INSTR_CONV(c0, in, w, out, s1, s2, s3);
    pa_hook_after("CONV", "CONV@conv.input.c:4", out);
}
```

- [ ] **Step 3: 写失败测试**

```python
# tests/integration/test_instrument.py
import json
import pathlib

from pa_debug.l1_transformer.transformer import instrument
from pa_debug.l1_transformer.rules import CONV_RULE

FIX = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "instrument"
STUBS = pathlib.Path(__file__).resolve().parents[2] / "stubs"


def _norm(text: str) -> list[str]:
    return [ln.rstrip() for ln in text.strip().splitlines()]


def test_instrument_matches_expected(tmp_path):
    src = tmp_path / "conv.input.c"
    src.write_text((FIX / "conv.input.c").read_text())
    out_c, manifest = instrument(
        str(src), rules=[CONV_RULE], clang_args=["-I", str(STUBS)]
    )
    expected = (FIX / "conv.expected.c").read_text()
    assert _norm(out_c) == _norm(expected)


def test_manifest_has_one_site(tmp_path):
    src = tmp_path / "conv.input.c"
    src.write_text((FIX / "conv.input.c").read_text())
    _, manifest = instrument(
        str(src), rules=[CONV_RULE], clang_args=["-I", str(STUBS)]
    )
    assert len(manifest) == 1
    site = manifest[0]
    assert site["op"] == "CONV"
    assert site["site_id"] == "CONV@conv.input.c:4"
    assert site["args"] == ["c0", "in", "w", "out", "s1", "s2", "s3"]
```

- [ ] **Step 4: 运行,确认失败**

Run: `.venv/bin/pytest tests/integration/test_instrument.py -v`
Expected: FAIL — `instrument` 未定义。

- [ ] **Step 5: 实现 transformer**

```python
# pa_debug/l1_transformer/transformer.py
"""编排:解析→按规则匹配宏调用→生成 hook 调用 Edit→倒序应用→输出 .c + 站点清单。

V0:只 DUMP_AND_RUN(无 if 包裹),只处理语句位置的宏。生成的 hook 调用采用简化可读形式,
完整 pa_hook_ctx_t ABI 是 M3 的事。
"""
import os

from .edits import Edit, apply_edits
from .frontend import parse_source
from .macro_extractor import find_macro_calls
from .rules import Rule


def _site_id(op: str, filename: str, line: int) -> str:
    return f"{op}@{filename}:{line}"


def _line_of(source_bytes: bytes, offset: int) -> int:
    return source_bytes[:offset].count(b"\n") + 1


def instrument(path: str, rules: list[Rule], clang_args: list[str] | None = None):
    with open(path, "rb") as fh:
        data = fh.read()
    source = data.decode()
    filename = os.path.basename(path)
    tu = parse_source(path, args=clang_args)

    edits: list[Edit] = []
    manifest: list[dict] = []

    for rule in rules:
        for call in find_macro_calls(tu, path, rule.macro):
            line = _line_of(data, call.start_offset)
            site_id = _site_id(rule.op, filename, line)
            in_args = [call.args[i] for i in rule.input_indices()]
            out_args = [call.args[i] for i in rule.output_indices()]

            indent = " " * (call.start_offset - (data.rfind(b"\n", 0, call.start_offset) + 1))
            before = (
                f'pa_hook_before("{rule.op}", "{site_id}", '
                + ", ".join(in_args) + ");\n" + indent
            )
            after = (
                "\n" + indent
                + f'pa_hook_after("{rule.op}", "{site_id}", '
                + ", ".join(out_args) + ");"
            )
            # 语句末尾分号在宏调用后;after 插到分号之后
            semi = data.find(b";", call.end_offset)
            after_pos = semi + 1 if semi >= 0 else call.end_offset

            edits.append(Edit(offset=call.start_offset, length=0, replacement=before))
            edits.append(Edit(offset=after_pos, length=0, replacement=after))

            manifest.append({
                "site_id": site_id,
                "op": rule.op,
                "macro": rule.macro,
                "file": filename,
                "line": line,
                "args": call.args,
            })

    return apply_edits(source, edits), manifest
```

- [ ] **Step 6: 运行,确认通过**

Run: `.venv/bin/pytest tests/integration/test_instrument.py -v`
Expected: 2 passed。
若行内缩进/换行细节与 expected 不符,**以实际输出更新 expected fixture**(规范化比对下应一致),
不要为凑测试而扭曲生成逻辑。

- [ ] **Step 7: Commit**

```bash
git add pa_debug/l1_transformer/transformer.py tests/integration/test_instrument.py tests/fixtures/
git commit -m "feat(ai-effect): L1 transformer 编排 + 端到端 fixture"
```

---

## Task 8: CLI —— `pa-debug instrument`

**Files:**
- Create: `pa_debug/cli.py`
- Create: `examples/conv.c`
- Test: `tests/integration/test_cli.py`

- [ ] **Step 1: 写 example 输入**

```c
/* examples/conv.c */
#include "pa_intrinsics.h"

void layer3(pa_tensor_t* in, pa_tensor_t* w, pa_tensor_t* out) {
    PA_INSTR_CONV(conv_l3, in, w, out, ish, wsh, osh);
}
```

- [ ] **Step 2: 写失败测试**

```python
# tests/integration/test_cli.py
import json
import pathlib

from click.testing import CliRunner
from pa_debug.cli import main

STUBS = pathlib.Path(__file__).resolve().parents[2] / "stubs"
EX = pathlib.Path(__file__).resolve().parents[2] / "examples"


def test_instrument_writes_outputs(tmp_path):
    src = tmp_path / "conv.c"
    src.write_text((EX / "conv.c").read_text())
    out_dir = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(main, [
        "instrument", str(src),
        "--stub-dir", str(STUBS),
        "--out-dir", str(out_dir),
    ])
    assert result.exit_code == 0, result.output
    inst = out_dir / "conv.c"
    sites = out_dir / "sites.json"
    assert inst.exists() and sites.exists()
    assert "pa_hook_before" in inst.read_text()
    assert json.loads(sites.read_text())[0]["op"] == "CONV"
```

- [ ] **Step 3: 运行,确认失败**

Run: `.venv/bin/pytest tests/integration/test_cli.py -v`
Expected: FAIL — `pa_debug.cli` / `main` 未定义。

- [ ] **Step 4: 实现 CLI**

```python
# pa_debug/cli.py
"""pa-debug CLI。V0 只提供 instrument 子命令。"""
import json
import os

import click

from .l1_transformer.rules import CONV_RULE
from .l1_transformer.transformer import instrument as _instrument


@click.group()
def main() -> None:
    """算子调试与对照工具。"""


@main.command()
@click.argument("src", type=click.Path(exists=True))
@click.option("--stub-dir", type=click.Path(exists=True), required=True, help="stub header 目录")
@click.option("--out-dir", type=click.Path(), default="./out", help="输出目录")
def instrument(src: str, stub_dir: str, out_dir: str) -> None:
    """对 SRC 插桩,输出插桩后 .c 与 sites.json。"""
    out_c, manifest = _instrument(src, rules=[CONV_RULE], clang_args=["-I", stub_dir])
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, os.path.basename(src))
    with open(dst, "w") as fh:
        fh.write(out_c)
    with open(os.path.join(out_dir, "sites.json"), "w") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    click.echo(f"instrumented → {dst}  ({len(manifest)} site(s))")
```

- [ ] **Step 5: 运行,确认通过**

Run: `.venv/bin/pytest tests/integration/test_cli.py -v`
Expected: 1 passed。

- [ ] **Step 6: 全量回归 + 目视检查**

Run:
```bash
.venv/bin/pytest -q
.venv/bin/pa-debug instrument examples/conv.c --stub-dir stubs --out-dir /tmp/pa_out && cat /tmp/pa_out/conv.c
```
Expected: 全部 passed;打印的插桩后源码包含 `pa_hook_before("CONV", ...)` 与
`pa_hook_after("CONV", ...)`,且 `PA_INSTR_CONV(...)` 原样保留。

- [ ] **Step 7: Commit**

```bash
git add pa_debug/cli.py examples/conv.c tests/integration/test_cli.py
git commit -m "feat(ai-effect): pa-debug instrument CLI + 端到端 example"
```

---

## V0 后续里程碑(各自单独成计划,M1 通过后再展开)

> 遵循 spec 的 KISS 与"L1 可行后再铺开"。下面只给目标与验证口径,**不在本计划里写 TDD 步骤**
> ——它们依赖 M1 产物(站点清单格式、hook ABI 最终形态)与 mock 边界,提前写细节会变成占位。

- **M2 — L1 加固**(✅ 本轮已做核心):config/框架隔离(`rule.py` 类型 + `rules_loader` 动态
  加载 + 外置 `rules/`,libclang 路径走 `PA_LIBCLANG_PATH`);语句位置守卫(评审 H,非语句位置宏
  跳过);isomorphism 别名归一(`PA_CONV→PA_INSTR_CONV`);blacklist(整文件 + 函数级跳过);
  第二个示意宏 `PA_INSTR_LOAD`(不同 arg 形状,证明加宏不改框架)。fixture corpus 9 例。
  *验证*:62 passed + ruff + lint-imports 全绿;加 LOAD 仅动 `rules/`+`stubs/`,`pa_debug/` 零改动。
  *待办(真表来了再做)*:其余真实硬件宏规则;函数级 blacklist 的更鲁棒文件匹配。
- **M3 — L2 运行时(mock)**:确定 `pa_hook_ctx_t` 最终 ABI;`HookDispatcher` + per-site 计数器
  + `TraceWriter`(JSONL + .bin);`DmaExporter` 用 **mock**(host 内存模拟片上)。
  *验证*:跑 mock 被插桩程序产出符合 §6.2.4 格式的 trace;trace schema 单测。
- **M4 — L3 离线对照**:`TraceReader`;1 个 `ref_conv`(NumPy,对拍手算黄金值);`Differ`(abs);
  `DivergenceLocator`(paired per-op,A/B 分类);JSON 报告。
  *验证*:构造"第 N 个算子输出注入误差"的 trace fixture,定位到第 N 个且分类正确。
- **M5 — L4 串联**:`pa-debug diff <trace>` → 调 L3 出报告;`pa-debug full` 串 instrument→(mock)run→diff。
  *验证*:端到端集成测试,全程不依赖真硬件。

每个里程碑产出**可独立验证**的软件,符合演进路径 §9 的 V0 定义。

---

## Self-Review 记录

- **Spec coverage(V0)**:FR-1.1/1.2/1.4/1.6/1.7 → M1(插桩、规则、声明式、语句位置约束;
  启停开关在 M5 CLI/编译选项落地);FR-1.5(算子接口入参结构体)→ M2;FR-2(hook 模式 DUMP_AND_RUN)
  → M3;FR-3(reference)→ M4;FR-4(对照定位)→ M4;FR-5(CLI 串联)→ M5。M1 覆盖 L1 的 PoC
  目标(ARCHITECTURE §12)无缺口。
- **Placeholder 扫描**:M1 各步均含完整代码与命令,无 TBD/TODO。M2–M5 明确标注"另立计划",
  非占位而是范围决策。
- **类型一致性**:`Edit(offset,length,replacement)`、`MacroCall(name,args,start_offset,end_offset)`、
  `Rule.input_indices()/output_indices()/id_index()`、`instrument(path,rules,clang_args)`、
  CLI `--stub-dir/--out-dir` 在各 Task 间一致引用,已核对。
