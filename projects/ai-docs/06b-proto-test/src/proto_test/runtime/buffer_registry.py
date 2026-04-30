"""缓冲区注册 M12 — 详见 06b § 3.8.

入口：
- ``BufferKind``         — {INPUT, GOLDEN, RESULT}
- ``BufferEntry``        — id / kind / size / crc32 / addr / created_ts
- ``BufferRegistry``     — alloc / write / read / free / query / list_by_kind
- ``BufferRegistryFull`` — 容量满异常（**不做隐式 LRU**）

约定：
- ``buf_id`` 单调递增；不复用
- 仅显式 ``free``；满了拒绝新分配并报错
- 写入自动算 ``crc32``，与读出 round-trip 校验
"""
from __future__ import annotations

import time
import zlib
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Dict, Iterator, List

from ..foundation.errors import DataIntegrityError, ERR_BUFFER_REGISTRY_FULL


class BufferKind(Enum):
    INPUT = "INPUT"
    GOLDEN = "GOLDEN"
    RESULT = "RESULT"


@dataclass(frozen=True)
class BufferEntry:
    """单 buffer 描述。"""

    buf_id: int
    kind: BufferKind
    size: int
    crc32: int
    addr: int
    created_ts: float


class BufferRegistryFull(DataIntegrityError):
    """容量已满；按 § 3.8 不做隐式 LRU。属 0x4xxx 数据完整性段位。"""


@dataclass
class BufferRegistry:
    """单板 buffer 注册（§ 3.8）。"""

    capacity: int = 64                # 默认 64 个 slot；占满即拒
    _next_id: int = field(default=1, init=False)
    _entries: Dict[int, BufferEntry] = field(default_factory=dict, init=False)
    _data: Dict[int, bytes] = field(default_factory=dict, init=False)

    def alloc(self, kind: BufferKind, size: int, addr: int = 0) -> int:
        """分配 slot，返回 ``buf_id``。"""
        if size <= 0:
            raise ValueError(f"size 必须 > 0，得到 {size}")
        if len(self._entries) >= self.capacity:
            raise BufferRegistryFull(
                f"BufferRegistry 已满（{self.capacity}）；显式 free() 后再试",
                code=ERR_BUFFER_REGISTRY_FULL,
            )
        buf_id = self._next_id
        self._next_id += 1
        self._entries[buf_id] = BufferEntry(
            buf_id=buf_id, kind=kind, size=size, crc32=0,
            addr=addr, created_ts=time.time(),
        )
        return buf_id

    def write(self, buf_id: int, data: bytes) -> None:
        """写入数据并自动算 ``crc32``；size 必须匹配 alloc。"""
        entry = self._require(buf_id)
        if len(data) != entry.size:
            raise ValueError(
                f"buf_id={buf_id}: 数据 {len(data)}B 与 alloc size {entry.size}B 不符"
            )
        crc = zlib.crc32(data) & 0xFFFFFFFF
        self._entries[buf_id] = replace(entry, crc32=crc)
        self._data[buf_id] = data

    def read(self, buf_id: int) -> bytes:
        self._require(buf_id)
        if buf_id not in self._data:
            raise KeyError(f"buf_id={buf_id} 已 alloc 但未 write")
        return self._data[buf_id]

    def query(self, buf_id: int) -> BufferEntry:
        return self._require(buf_id)

    def free(self, buf_id: int) -> None:
        self._require(buf_id)
        del self._entries[buf_id]
        self._data.pop(buf_id, None)

    def list_by_kind(self, kind: BufferKind) -> List[BufferEntry]:
        return [e for e in self._entries.values() if e.kind == kind]

    def __iter__(self) -> Iterator[BufferEntry]:
        return iter(self._entries.values())

    def __len__(self) -> int:
        return len(self._entries)

    def _require(self, buf_id: int) -> BufferEntry:
        if buf_id not in self._entries:
            raise KeyError(f"buf_id={buf_id} 不存在或已 free")
        return self._entries[buf_id]
