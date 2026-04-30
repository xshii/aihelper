"""Block 协议单测 — 对齐 / 端序 / 位域 / 组合."""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import ClassVar, List, Tuple

import pytest

from proto_test import (
    BitFieldMixin,
    Block,
    Composite,
    EndBlock,
    HeaderBlock,
    RawBlock,
    TensorBlock,
    pack,
)


# region 对齐 ────────────────────────────────────────────────────────
def test_alignment_pad_to_512():
    """单个 Block 字节数必须 == 512 的整数倍。"""
    blk = TensorBlock(tid=1, cnt=0, data=b"\x01\x02\x03")
    raw = bytes(blk)
    assert len(raw) % 512 == 0
    assert len(raw) == 512                            # payload 11B → pad 到 512
    assert len(blk) == len(raw)


def test_alignment_zero_padding():
    """填充位必须是 \\x00。"""
    blk = TensorBlock(tid=1, cnt=0, data=b"\xff")
    raw = bytes(blk)
    assert raw[:9] == struct.pack("<HHI", 1, 0, 1) + b"\xff"
    assert raw[9:] == b"\x00" * (512 - 9)


def test_alignment_exact_boundary():
    """payload 已经是 512 倍数时不应额外加 512。"""
    payload = b"\x00" * (512 - 8)                     # 头 8B + 504B = 512B
    blk = TensorBlock(tid=0, cnt=0, data=payload)
    assert len(blk) == 512
# endregion


# region 端序 ────────────────────────────────────────────────────────
def test_endian_little_default():
    blk = TensorBlock(tid=0x1234, cnt=0, data=b"")
    head = bytes(blk)[:4]
    assert head == b"\x34\x12\x00\x00"                # 小端


def test_endian_big_via_subclass():
    class BigTensorBlock(TensorBlock):
        ENDIAN = ">"

    blk = BigTensorBlock(tid=0x1234, cnt=0, data=b"")
    head = bytes(blk)[:4]
    assert head == b"\x12\x34\x00\x00"                # 大端
# endregion


# region 位域 ────────────────────────────────────────────────────────
def test_bitfield_packing():
    """HeaderBlock = u4 ver | u4 flags | u8 rsv | u16 count = 4B."""
    blk = HeaderBlock(version=0x3, flags=0x5, count=0x1234)
    raw = bytes(blk)[:4]
    # bitstruct MSB-first：byte0 = 0x35（ver=3 << 4 | flags=5），byte1=0x00（rsv），
    # byte2..3 = 0x12 0x34（count）；ENDIAN="<" 后整体 byteswap：0x34 0x12 0x00 0x35
    assert len(raw) == 4
    assert raw == b"\x34\x12\x00\x35"


def test_bitfield_max_values():
    blk = HeaderBlock(version=0xF, flags=0xF, count=0xFFFF)
    raw = bytes(blk)[:4]
    assert raw == b"\xff\xff\x00\xff"
# endregion


# region 组合 ────────────────────────────────────────────────────────
def test_compose_via_plus():
    h = HeaderBlock(version=1, flags=0, count=2)
    t1 = TensorBlock(tid=0, cnt=0, data=b"\x01")
    t2 = TensorBlock(tid=1, cnt=0, data=b"\x02")
    buf = h + t1 + t2
    assert isinstance(buf, Composite)
    assert len(buf.parts) == 3
    assert len(buf) == 512 * 3                        # 每块 512B 对齐


def test_compose_via_sum():
    blocks = [TensorBlock(tid=i, cnt=0, data=b"x") for i in range(3)]
    buf = sum(blocks, 0)
    assert len(buf) == 512 * 3                        # type: ignore[arg-type]


def test_pack_helper():
    """pack(blocks) 等价 bytes(sum(blocks, 0))，类型清晰。"""
    blocks = [TensorBlock(tid=i, cnt=0, data=b"x") for i in range(3)]
    raw = pack(blocks)
    assert isinstance(raw, bytes)
    assert len(raw) == 512 * 3
    assert raw == bytes(sum(blocks, 0))               # type: ignore[arg-type]


def test_pack_empty_iterable():
    assert pack([]) == b""


def test_pack_iter_input():
    """pack 接受任何 Iterable，不仅是 list。"""
    gen = (TensorBlock(tid=i, cnt=0, data=b"y") for i in range(2))
    assert len(pack(gen)) == 512 * 2


def test_composite_no_double_padding():
    """子块已对齐时 Composite 不该再额外 pad。"""
    a = RawBlock(data=b"\x00" * 512)                  # 已对齐
    b = RawBlock(data=b"\x00" * 512)
    buf = a + b
    assert len(bytes(buf)) == 1024                    # 严格等于 1024


def test_composite_concat_flattening():
    """Composite + Composite 应扁平拼接，避免嵌套增长。"""
    c1 = TensorBlock(tid=0, cnt=0, data=b"a") + TensorBlock(tid=1, cnt=0, data=b"b")
    c2 = TensorBlock(tid=2, cnt=0, data=b"c") + TensorBlock(tid=3, cnt=0, data=b"d")
    merged = c1 + c2
    assert isinstance(merged, Composite)
    assert len(merged.parts) == 4                     # 扁平，不是 [c1, c2]
# endregion


# region 防御 ────────────────────────────────────────────────────────
def test_add_non_block_returns_notimplemented():
    blk = TensorBlock(tid=0, cnt=0, data=b"")
    with pytest.raises(TypeError):
        _ = blk + "not a block"                       # type: ignore[operator]
# endregion


# region BitFieldMixin 语法糖 ────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class _CustomBitfield(BitFieldMixin, Block):
    """测试用：声明 BIT_LAYOUT 即可自动生成 _payload。"""

    BIT_LAYOUT: ClassVar[List[Tuple[str, int]]] = [
        ("a", 4), ("b", 4), ("c", 8),
    ]
    a: int
    b: int
    c: int


@dataclass(frozen=True, slots=True)
class _BrokenBitfield(BitFieldMixin, Block):
    """测试用：BIT_LAYOUT 未声明（继承基类的空 list）。"""

    x: int = 0


def test_bitfieldmixin_auto_payload():
    """声明 BIT_LAYOUT 即可自动生成 _payload，无需手写 bitstruct.pack。"""
    blk = _CustomBitfield(a=0x3, b=0x5, c=0xAB)
    raw = bytes(blk)
    # 头 2B：bitstruct MSB → "0x35 0xAB"；ENDIAN="<" 后 byteswap → "0xAB 0x35"
    assert raw[:2] == b"\xab\x35"
    assert len(raw) == 512                            # 自动对齐


def test_bitfieldmixin_missing_layout_raises():
    with pytest.raises(RuntimeError, match="BIT_LAYOUT 未声明"):
        bytes(_BrokenBitfield())
# endregion


# region from_bytes round-trip ──────────────────────────────────────
def test_tensor_block_from_bytes_round_trip():
    """TensorBlock.from_bytes 还原原始字段。"""
    original = TensorBlock(tid=0x1234, cnt=2, data=b"\xAA\xBB\xCC\xDD")
    raw = bytes(original)
    parsed = TensorBlock.from_bytes(raw)
    assert parsed.tid == 0x1234
    assert parsed.cnt == 2
    assert parsed.data == b"\xAA\xBB\xCC\xDD"
    assert parsed == original


def test_tensor_block_from_bytes_truncated_raises():
    from proto_test import DataIntegrityError
    with pytest.raises(DataIntegrityError, match="不足"):
        TensorBlock.from_bytes(b"\x00\x00")           # 只有 2B
# endregion
