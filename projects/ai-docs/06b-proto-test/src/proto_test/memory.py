"""通用内存访问 — 类型系统 + 符号映射 + ReadVal/ReadStruct API（详见 06b § 4.8 / § 1.6.1）.

入口：
- ``Datatype``        — 标量类型命名空间（``Datatype.UINT32`` / ``.struct.X``）
- ``StructDef``       — 结构体描述
- ``register_struct`` — 注册一个 struct，``Datatype.struct.<Name>`` 即可访问
- ``CompareEntry``    — 与 § 1.6.1 ``compare_entry_t`` 等价的内置 struct
- ``MemPort``         — 字节级读写 Protocol
- ``SymbolMap``       — symbol → address
- ``MemAccessAPI``    — ``ReadVal`` / ``ReadStruct`` / ``ReadArray`` / ``WriteVal`` / ...

约定：
- 索引 1-based（``index=1`` = 第 1 个元素），对齐 datasheet 计数
- ``CFG_PTR_SIZE`` 控制 ``Datatype.PTR`` 大小（默认 4，32 位 DUT）
- 异常统一走 ``proto_test.errors``：``SymbolNotFoundError`` / ``DataIntegrityError``
"""
from __future__ import annotations

import struct as _struct
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Protocol, Tuple

from .errors import (
    DataIntegrityError,
    ERR_DATA_CRC_MISMATCH,
    ERR_SYMBOL_NOT_FOUND,
    SymbolNotFoundError,
)

CFG_PTR_SIZE = 4  # 32 位 DUT 默认；64 位场景显式置 8

EndianStr = Literal["<", ">"]   # 与 block.EndianStr 一致；struct 模块约定


# region 类型系统 — Datatype / StructDef ────────────────────────────
@dataclass(frozen=True)
class _ScalarType:
    """标量类型描述符（singleton 实例放在 ``Datatype.<NAME>``）。"""

    _code: str           # struct 模块格式字符；"PTR" 为特殊占位
    _bytes: int

    def size(self) -> int:
        return CFG_PTR_SIZE if self._code == "PTR" else self._bytes

    def code(self) -> str:
        if self._code == "PTR":
            return "I" if CFG_PTR_SIZE == 4 else "Q"
        return self._code

    def fmt(self, endian: EndianStr = "<") -> str:
        return endian + self.code()


@dataclass(frozen=True)
class StructDef:
    """结构体描述。无 padding（紧凑布局）。"""

    name: str
    fields: Tuple[Tuple[str, _ScalarType], ...]

    def size(self) -> int:
        return sum(dt.size() for _, dt in self.fields)

    def unpack(self, raw: bytes, endian: EndianStr = "<") -> Dict[str, Any]:
        if len(raw) < self.size():
            raise ValueError(
                f"struct {self.name}: 期望 {self.size()} 字节，得到 {len(raw)}"
            )
        out: Dict[str, Any] = {}
        offset = 0
        for fname, dtype in self.fields:
            sz = dtype.size()
            chunk = raw[offset:offset + sz]
            out[fname] = _struct.unpack(dtype.fmt(endian), chunk)[0]
            offset += sz
        return out

    def pack(self, values: Dict[str, Any], endian: EndianStr = "<") -> bytes:
        parts: List[bytes] = []
        for fname, dtype in self.fields:
            parts.append(_struct.pack(dtype.fmt(endian), values[fname]))
        return b"".join(parts)


_STRUCT_REGISTRY: Dict[str, StructDef] = {}


def register_struct(
    name: str, fields: List[Tuple[str, _ScalarType]]
) -> StructDef:
    """注册 struct；幂等（同名同字段 OK；同名异字段抛 ValueError）。"""
    sdef = StructDef(name=name, fields=tuple(fields))
    existing = _STRUCT_REGISTRY.get(name)
    if existing is not None and existing != sdef:
        raise ValueError(f"struct {name} 重复注册且字段不一致")
    _STRUCT_REGISTRY[name] = sdef
    return sdef


class _StructNS:
    """``Datatype.struct.<Name>`` 命名空间。"""

    def __getattr__(self, name: str) -> StructDef:
        if name not in _STRUCT_REGISTRY:
            raise AttributeError(f"未注册 struct: {name}")
        return _STRUCT_REGISTRY[name]


class Datatype:
    """统一类型命名空间 — ``Datatype.UINT32`` / ``Datatype.struct.CompareEntry``."""

    UINT8: _ScalarType
    UINT16: _ScalarType
    UINT32: _ScalarType
    UINT64: _ScalarType
    INT8: _ScalarType
    INT16: _ScalarType
    INT32: _ScalarType
    INT64: _ScalarType
    FLOAT: _ScalarType
    DOUBLE: _ScalarType
    PTR: _ScalarType
    struct: _StructNS


Datatype.UINT8 = _ScalarType("B", 1)
Datatype.UINT16 = _ScalarType("H", 2)
Datatype.UINT32 = _ScalarType("I", 4)
Datatype.UINT64 = _ScalarType("Q", 8)
Datatype.INT8 = _ScalarType("b", 1)
Datatype.INT16 = _ScalarType("h", 2)
Datatype.INT32 = _ScalarType("i", 4)
Datatype.INT64 = _ScalarType("q", 8)
Datatype.FLOAT = _ScalarType("f", 4)
Datatype.DOUBLE = _ScalarType("d", 8)
Datatype.PTR = _ScalarType("PTR", 0)
Datatype.struct = _StructNS()


# 与 06b § 1.6.1 C struct ``compare_entry_t`` 等价
CompareEntry = register_struct(
    "CompareEntry",
    [
        ("tid", Datatype.UINT16),
        ("cnt", Datatype.UINT16),
        ("length", Datatype.UINT32),
        ("addr", Datatype.PTR),
    ],
)
# endregion


# region 端口 + 符号映射 ───────────────────────────────────────────
class MemPort(Protocol):
    """字节级内存读写端口（具体 Adapter 实现）。"""

    def read(self, addr: int, n: int) -> bytes: ...
    def write(self, addr: int, raw: bytes) -> None: ...


@dataclass
class SymbolMap:
    """symbol → address 字典；``image_activate`` 后由 L5 重载。"""

    table: Dict[str, int]

    def resolve(self, symbol: str) -> int:
        if symbol not in self.table:
            raise SymbolNotFoundError(symbol, code=ERR_SYMBOL_NOT_FOUND)
        return self.table[symbol]

    @classmethod
    def from_map_file(cls, path: str) -> "SymbolMap":
        """解析极简 .map 格式：每行 ``<name>  <hex_addr>``；其它行忽略。"""
        table: Dict[str, int] = {}
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) != 2:
                    continue
                name, addr = parts
                try:
                    table[name] = int(addr, 16)
                except ValueError:
                    continue
        return cls(table=table)
# endregion


# region MemAccessAPI ───────────────────────────────────────────────
class MemAccessAPI:
    """§ 4.8 通用内存访问 API。

    PascalCase 命名匹配"底层访问原语"约定（与领域服务函数 snake_case 区分）。
    """

    def __init__(self, port: MemPort, symbols: SymbolMap, endian: EndianStr = "<"):
        self._port = port
        self._symbols = symbols
        self._endian = endian

    def ReadVal(self, symbol: str, dtype: _ScalarType) -> Any:
        addr = self._symbols.resolve(symbol)
        sz = dtype.size()
        raw = self._port.read(addr, sz)
        if len(raw) != sz:
            raise DataIntegrityError(
                f"{symbol}: read {len(raw)}B, want {sz}B",
                code=ERR_DATA_CRC_MISMATCH,
            )
        return _struct.unpack(dtype.fmt(self._endian), raw)[0]

    def WriteVal(self, symbol: str, dtype: _ScalarType, value: Any) -> None:
        addr = self._symbols.resolve(symbol)
        self._port.write(addr, _struct.pack(dtype.fmt(self._endian), value))

    def ReadStruct(
        self, symbol: str, sdef: StructDef, index: int = 1
    ) -> Dict[str, Any]:
        self._check_index(index)
        base = self._symbols.resolve(symbol)
        sz = sdef.size()
        raw = self._port.read(base + (index - 1) * sz, sz)
        return sdef.unpack(raw, self._endian)

    def WriteStruct(
        self, symbol: str, sdef: StructDef, index: int, values: Dict[str, Any]
    ) -> None:
        self._check_index(index)
        base = self._symbols.resolve(symbol)
        addr = base + (index - 1) * sdef.size()
        self._port.write(addr, sdef.pack(values, self._endian))

    def ReadArray(
        self, symbol: str, dtype: _ScalarType, count: int, start: int = 1
    ) -> List[Any]:
        self._check_index(start)
        base = self._symbols.resolve(symbol)
        sz = dtype.size()
        raw = self._port.read(base + (start - 1) * sz, count * sz)
        fmt = self._endian + dtype.code() * count
        return list(_struct.unpack(fmt, raw))

    def ReadBytes(self, addr: int, n: int) -> bytes:
        """绝对地址裸读；用于地址来自数据结构（如 ``g_compAddr[i].addr``）的场景。"""
        return self._port.read(addr, n)

    def WriteBytes(self, addr: int, raw: bytes) -> None:
        self._port.write(addr, raw)

    @staticmethod
    def _check_index(index: int) -> None:
        if index < 1:
            raise ValueError(f"index 必须 >= 1（1-based），收到 {index}")
# endregion
