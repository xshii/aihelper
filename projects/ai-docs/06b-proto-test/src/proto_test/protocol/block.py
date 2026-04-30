"""DATA_BUF Block 组合协议 — 机制 A 发包载荷生成（详见 06b § 1.7）.

入口（按层次）：

**基础协议** ::
- ``Block``         — 抽象基类；子类只需实现 ``_payload() -> bytes``
- ``Composite``     — 多 Block 拼接（``a + b`` 自动产出）
- ``BitFieldMixin`` — 位域 Mixin（声明 ``BIT_LAYOUT`` 即自动 ``_payload``）
- ``pack(blocks)``  — 顶层 helper；多 Block → 字节流（替代 ``bytes(sum(_, 0))``）

**业务层 Block 示例** ::
- ``TensorBlock``  — 字节对齐范式（``struct.pack`` + ENDIAN，含 ``from_bytes`` 反向）
- ``HeaderBlock``  — 位域范式（``BitFieldMixin`` 实例化样例，注意：是**业务**头不是 DDR 头）
- ``EndBlock``     — 结束标记块
- ``RawBlock``     — 裸字节透传

**DDR 层（关键预埋）** ::
- ``DdrBlockHeader``    — 物理 DDR 块头（512B；含 ``frag_flag`` 等位域）
- ``DdrChunk``          — DDR chunk = 头 + payload
- ``DdrConfig``         — 发送配置（channel / priority / encrypt / max_payload）
- ``DdrSender``         — 发送器（绑定 config + 自增 block_id；典型 ``sender.send(payload)``）
- ``fragment_payload``  — 函数式入口：payload → ``List[DdrChunk]``（自动切片 + 填头）

设计模式：Composite Pattern + dataclass + 512 字节强对齐 + 大小端可配 + 位域支持。

序列化合约：
- ``bytes(blk)`` 返回**已填充对齐**的字节串；零分支算法 ``(-len) % ALIGN``
- ``len(blk)``   返回对齐后总长度
- 子类用 ``ENDIAN`` 控制 byte order；用 ``BIT_LAYOUT`` 声明位域

依赖：
- ``bitstruct`` — 位域声明式打包；缺时 ``BitFieldMixin._payload`` 抛 ``RuntimeError``
"""
from __future__ import annotations

import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar, Iterable, Iterator, List, Literal, Optional, Tuple

try:
    import bitstruct  # type: ignore
except ImportError:
    bitstruct = None  # type: ignore[assignment]

from ..foundation.errors import DataIntegrityError, ERR_DATA_CRC_MISMATCH

EndianStr = Literal["<", ">"]


class Block(ABC):
    """所有 DATA_BUF 块的基类。

    子类约定：
    - 实现 ``_payload(self) -> bytes`` 返回**纯净** payload（不含填充）
    - 可覆盖 ``ALIGNMENT`` / ``ENDIAN`` 两个 ClassVar
    - 推荐 ``@dataclass(frozen=True, slots=True)``
    """

    ALIGNMENT: ClassVar[int] = 512                # 单一来源；硬件约束
    ENDIAN: ClassVar[EndianStr] = "<"             # struct 约定：< 小端 / > 大端

    @abstractmethod
    def _payload(self) -> bytes:
        """返回纯净 payload（不含对齐填充）。"""

    def __bytes__(self) -> bytes:
        raw = self._payload()
        pad = (-len(raw)) % self.ALIGNMENT        # 负数取模 = 对齐填充长度（零分支）
        return raw + b"\x00" * pad

    def __len__(self) -> int:
        return len(bytes(self))

    def __add__(self, other: object) -> "Composite":
        # pyright 对 dunder __add__ 返回 NotImplemented 有特殊豁免，无需 type ignore
        if not isinstance(other, Block):
            return NotImplemented
        return Composite([self, other])

    def __radd__(self, other: object) -> "Block":
        # 让 sum(blocks, 0) 可用：起点 0，0.__add__(blk) 失败 → 回落 blk.__radd__(0)
        if other == 0:
            return self
        return NotImplemented


@dataclass
class Composite(Block):
    """Block 序列。子块已对齐 → 拼接时不再额外 padding。"""

    parts: List[Block] = field(default_factory=list)

    def _payload(self) -> bytes:
        return b"".join(bytes(p) for p in self.parts)

    def __add__(self, other: object) -> "Composite":
        if not isinstance(other, Block):
            return NotImplemented
        rhs = other.parts if isinstance(other, Composite) else [other]
        return Composite(self.parts + rhs)

    def __iter__(self) -> Iterator[Block]:
        yield from self.parts


def pack(blocks: Iterable[Block]) -> bytes:
    """把多个 Block 拼成 DATA_BUF 字节流（顶层 helper）.

    等价于 ``bytes(sum(blocks, 0))`` 但**类型清晰**：sum 返回 ``int | Block``
    会让 type checker 推不准；本函数直接返回 ``bytes``。

    用法::

        # 业务 Block 拼接
        raw = pack([HeaderBlock(...), TensorBlock(...), EndBlock()])

        # DDR chunk 拼接
        raw = pack(sender.send(payload))

    空可迭代返回 ``b""``。
    """
    parts = list(blocks)
    if not parts:
        return b""
    return bytes(Composite(parts=parts))


# region 业务层 Block 示例 ───────────────────────────────────────────
# 这些 Block 演示三种典型范式（字节对齐 / 位域 / 透传）；正式业务字段待 Q-001 定型。
# 实际项目里业务部分常用 ``struct.pack`` 直接拼，这些类作教学样例 / 也可继承扩展。

@dataclass(frozen=True, slots=True)
class TensorBlock(Block):
    """字节对齐范式：纯 ``struct.pack`` + ENDIAN.

    布局（小端）::
        offset 0   uint16  tid
        offset 2   uint16  cnt
        offset 4   uint32  length
        offset 8   bytes   data[length]
    """

    HEAD_FMT_TAIL: ClassVar[str] = "HHI"          # 不含端序前缀；与 ENDIAN 拼接

    tid: int
    cnt: int
    data: bytes

    def _payload(self) -> bytes:
        head = struct.pack(f"{self.ENDIAN}{self.HEAD_FMT_TAIL}",
                           self.tid, self.cnt, len(self.data))
        return head + self.data

    @classmethod
    def from_bytes(cls, raw: bytes) -> "TensorBlock":
        """反序列化：从对齐后的字节串还原 TensorBlock。

        使用场景：抓包验证 / 离线分析；正常发送链路用不到。
        """
        head_size = struct.calcsize(f"{cls.ENDIAN}{cls.HEAD_FMT_TAIL}")
        if len(raw) < head_size:
            raise DataIntegrityError(
                f"raw {len(raw)}B 不足以装下头 {head_size}B",
                code=ERR_DATA_CRC_MISMATCH,
            )
        tid, cnt, length = struct.unpack(
            f"{cls.ENDIAN}{cls.HEAD_FMT_TAIL}", raw[:head_size]
        )
        data = raw[head_size:head_size + length]
        if len(data) < length:
            raise DataIntegrityError(
                f"raw 不足以装下 length={length} 字节数据",
                code=ERR_DATA_CRC_MISMATCH,
            )
        return cls(tid=tid, cnt=cnt, data=data)


class BitFieldMixin:
    """位域 Mixin：声明 ``BIT_LAYOUT = [(name, bits), ...]`` 即自动生成 ``_payload``.

    用法::

        @dataclass(frozen=True, slots=True)
        class HeaderBlock(BitFieldMixin, Block):
            BIT_LAYOUT = [("version", 4), ("flags", 4), ("rsv", 8), ("count", 16)]
            version: int
            flags: int
            rsv: int = 0
            count: int = 0

    比手动写 ``bitstruct.pack(...)`` 节省两件事：
    1. 自动按 ``BIT_LAYOUT`` 拼 format 串
    2. 自动 ``ENDIAN="<"`` 时调用 ``byteswap``
    """

    BIT_LAYOUT: ClassVar[List[Tuple[str, int]]] = []
    ENDIAN: ClassVar[EndianStr] = "<"             # 让 mypy 知道 mixin 也读 ENDIAN

    def _payload(self) -> bytes:                  # type: ignore[override]
        if bitstruct is None:                     # type: ignore[truthy-bool]
            raise RuntimeError("BitFieldMixin 需要 bitstruct 库")
        if not self.BIT_LAYOUT:
            raise RuntimeError(
                f"{type(self).__name__}.BIT_LAYOUT 未声明；位域 Block 必须提供"
            )
        fmt = "".join(f"u{bits}" for _, bits in self.BIT_LAYOUT)
        values = [getattr(self, name) for name, _ in self.BIT_LAYOUT]
        raw = bitstruct.pack(fmt, *values)
        if self.ENDIAN == "<":
            raw = bitstruct.byteswap(str(len(raw)), raw)
        return raw


@dataclass(frozen=True, slots=True)
class HeaderBlock(BitFieldMixin, Block):
    """位域范式：通过 ``BitFieldMixin`` + ``BIT_LAYOUT`` 声明.

    布局（4 字节，bitstruct 默认 MSB-first）::
        bit  0..3   uint4   version
        bit  4..7   uint4   flags
        bit  8..15  uint8   reserved (常量 0)
        bit 16..31  uint16  count
    """

    BIT_LAYOUT: ClassVar[List[Tuple[str, int]]] = [
        ("version", 4),
        ("flags", 4),
        ("rsv", 8),
        ("count", 16),
    ]
    version: int
    flags: int
    count: int
    rsv: int = 0


@dataclass(frozen=True, slots=True)
class EndBlock(Block):
    """结束标记块（魔术字）。"""

    magic: int = 0xDEADBEEF

    def _payload(self) -> bytes:
        return struct.pack(f"{self.ENDIAN}I", self.magic)


@dataclass(frozen=True, slots=True)
class RawBlock(Block):
    """裸字节块；调试 / 未识别载荷透传用。"""

    data: bytes

    def _payload(self) -> bytes:
        return self.data
# endregion


# region DDR 块头与分片填写 ─────────────────────────────────────────
# DATA_BUF 的物理单元 = DDR chunk。每 chunk = 512B 头 + payload。
# 大 payload 自动切片：每片 chunk 头里填 frag_flag / frag_seq / frag_total / block_id。
# 业务层（VPORT 头 / 业务 header / 业务字段）由调用方用 ``struct.pack`` 自由拼接，
# 整体 bytes 传给 ``fragment_payload`` 即可。

@dataclass(frozen=True, slots=True)
class DdrBlockHeader(Block):
    """DDR 块头（固定 512 字节）— 关键预埋：分片标志 + 序号 + 总数 + payload_length.

    布局（占位 — 真实位宽以硬件 datasheet 为准）::

      offset  size  field           说明
      ──────────────────────────────────────────────────────────
      0       4     magic           uint32 = 0xDDB10001
      4       1     version         uint8
      5       1     hw_proto        1B 位域（手工掩码）：
                                        bit 0     frag_flag  (1 = 分片中)
                                        bit 1..3  priority   (3 bit)
                                        bit 4     encrypt    (1 bit)
                                        bit 5..7  reserved
      6..7    2     frag_seq        uint16 (0-based; 非分片时 0)
      8..9    2     frag_total      uint16 (非分片时 1)
      10..11  2     channel_id      uint16 (VPORT 通道 id)
      12..15  4     payload_length  uint32 (本 chunk payload 实际字节数)
      16..19  4     block_id        uint32 (同一逻辑包共享)
      20..511 492   reserved        zero padding

    ``frag_flag`` 放 bit 0，硬件可用单 bit mask 直接检测。
    总长 ``HEADER_SIZE = 512``，与 ALIGNMENT 一致；本身不再额外 padding。
    """

    HEADER_SIZE: ClassVar[int] = 512
    MAGIC: ClassVar[int] = 0xDDB10001
    # struct 格式：magic / version / hw_proto / frag_seq / frag_total / channel_id / payload_length / block_id
    FIXED_FMT_TAIL: ClassVar[str] = "IBBHHHII"      # 头 20 字节固定区

    frag_flag: int
    frag_seq: int
    frag_total: int
    channel_id: int
    payload_length: int
    block_id: int
    priority: int = 0
    encrypt: int = 0
    version: int = 1                                # 协议版本默认值；可覆盖

    def _payload(self) -> bytes:
        head = struct.pack(
            f"{self.ENDIAN}{self.FIXED_FMT_TAIL}",
            self.MAGIC,
            self.version,
            self._hw_proto_byte(),
            self.frag_seq,
            self.frag_total,
            self.channel_id,
            self.payload_length,
            self.block_id,
        )
        # head 长度 = 4 + 1 + 1 + 2 + 2 + 2 + 4 + 4 = 20
        return head + b"\x00" * (self.HEADER_SIZE - len(head))

    def _hw_proto_byte(self) -> int:
        """1B 位域打包：frag_flag@bit0 | priority@bit1..3 | encrypt@bit4."""
        return (
            (self.frag_flag & 0x1)
            | ((self.priority & 0x7) << 1)
            | ((self.encrypt & 0x1) << 4)
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> "DdrBlockHeader":
        """反向解析（抓包 / 回归验证用）。校验 magic；位域按位还原。"""
        if len(raw) < 20:
            raise DataIntegrityError(
                f"DDR header 至少 20B，得到 {len(raw)}",
                code=ERR_DATA_CRC_MISMATCH,
            )
        magic, version, hw, fseq, ftotal, ch, plen, bid = struct.unpack(
            f"{cls.ENDIAN}{cls.FIXED_FMT_TAIL}", raw[:20]
        )
        if magic != cls.MAGIC:
            raise DataIntegrityError(
                f"magic 错位：0x{magic:08x} != 0x{cls.MAGIC:08x}",
                code=ERR_DATA_CRC_MISMATCH,
            )
        return cls(
            frag_flag=hw & 0x1,
            priority=(hw >> 1) & 0x7,
            encrypt=(hw >> 4) & 0x1,
            frag_seq=fseq,
            frag_total=ftotal,
            channel_id=ch,
            payload_length=plen,
            block_id=bid,
            version=version,
        )


@dataclass(frozen=True, slots=True)
class DdrChunk(Block):
    """DDR chunk = 头 (512B) + payload；总长按 512 自动对齐。

    payload 由调用方自由拼（VPORT 头 / 业务 header / 业务字段），常用 ``struct.pack`` 即可。
    """

    header: DdrBlockHeader
    payload: bytes

    def _payload(self) -> bytes:
        return bytes(self.header) + self.payload


# 默认单 chunk payload 上限：让 chunk 总长正好 4 KiB（8×ALIGNMENT），DDR burst 友好
DEFAULT_MAX_PAYLOAD_PER_CHUNK = 4096 - DdrBlockHeader.HEADER_SIZE   # = 3584


@dataclass(frozen=True)
class DdrConfig:
    """DDR 发送配置 — 一组 case / session 内通常不变的字段聚合.

    把会话级稳定参数打包成一个对象，避免每次调 ``fragment_payload`` 重复传。
    """

    channel_id: int = 0
    max_payload_per_chunk: int = DEFAULT_MAX_PAYLOAD_PER_CHUNK
    priority: int = 0
    encrypt: int = 0


_DEFAULT_DDR_CONFIG = DdrConfig()


def fragment_payload(
    payload: bytes,
    *,
    block_id: int,
    config: DdrConfig = _DEFAULT_DDR_CONFIG,
) -> List[DdrChunk]:
    """把 payload 切成 ``DdrChunk`` 列表，自动填好块头 + 分片字段（关键逻辑）.

    切片规则：

    - ``len(payload) == 0``                → 1 个空 chunk（仅 header），``frag_flag=0``
    - ``len(payload) <= max_per_chunk``    → 1 chunk，``frag_flag=0``，``frag_total=1``
    - 否则                                   → N chunks，``frag_flag=1``，``frag_seq=0..N-1``，共享 ``block_id``

    返回的 chunks 用 ``pack(chunks)`` 直接得 DATA_BUF 字节流（推荐），或 ``a + b + c``
    拼成 ``Composite`` 再 ``bytes(...)``；亦兼容 ``bytes(sum(chunks, 0))``。
    """
    if config.max_payload_per_chunk <= 0:
        raise ValueError(
            f"max_payload_per_chunk 必须 > 0，得到 {config.max_payload_per_chunk}"
        )

    if not payload:
        slices: List[bytes] = [b""]
    elif len(payload) <= config.max_payload_per_chunk:
        slices = [payload]
    else:
        step = config.max_payload_per_chunk
        slices = [payload[i:i + step] for i in range(0, len(payload), step)]

    total = len(slices)
    is_fragmented = 1 if total > 1 else 0
    return [
        DdrChunk(
            header=DdrBlockHeader(
                frag_flag=is_fragmented,
                frag_seq=i,
                frag_total=total,
                channel_id=config.channel_id,
                payload_length=len(slc),
                block_id=block_id,
                priority=config.priority,
                encrypt=config.encrypt,
            ),
            payload=slc,
        )
        for i, slc in enumerate(slices)
    ]


@dataclass
class DdrSender:
    """DDR 发送器 — 绑定 ``DdrConfig`` + 自动管理 ``block_id``.

    替代每次手填 channel / priority / encrypt / block_id；一行 ``sender.send(payload)``.

    典型用法::

        sender = DdrSender(DdrConfig(channel_id=0x100, priority=1))
        for payload in payloads:
            chunks = sender.send(payload)
            mem_drv_write_data_buf(pack(chunks))

    用例间切换：``sender.reset()`` 把 ``block_id`` 序号清回 1，``config`` 不变。
    """

    config: DdrConfig = field(default_factory=DdrConfig)
    _next_block_id: int = field(default=1, init=False)

    def send(self, payload: bytes) -> List[DdrChunk]:
        bid = self._next_block_id
        self._next_block_id += 1
        return fragment_payload(payload, block_id=bid, config=self.config)

    def reset(self) -> None:
        """case 间切换重置序号；``config`` 保持不变。"""
        self._next_block_id = 1

    @property
    def next_block_id(self) -> int:
        """只读：下一次 send 将使用的 ``block_id``（断言 / 日志用）。"""
        return self._next_block_id
# endregion
