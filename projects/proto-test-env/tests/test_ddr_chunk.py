"""DDR 块头 + 分片填写 关键逻辑单测."""
from __future__ import annotations

import struct

import pytest

from proto_test import (
    DEFAULT_MAX_PAYLOAD_PER_CHUNK,
    DataIntegrityError,
    DdrBlockHeader,
    DdrChunk,
    DdrConfig,
    DdrSender,
    fragment_payload,
    pack,
)


# region 块头字段映射 ────────────────────────────────────────────────
def test_header_size_is_512():
    h = DdrBlockHeader(
        frag_flag=0, frag_seq=0, frag_total=1, channel_id=0,
        payload_length=0, block_id=0,
    )
    assert len(bytes(h)) == 512


def test_header_field_offsets():
    """字段位置：magic@0..3, version@4, hw_proto@5, frag_seq@6..7, ..."""
    h = DdrBlockHeader(
        frag_flag=0, frag_seq=0xABCD, frag_total=0x1234, channel_id=0x5678,
        payload_length=0x11223344, block_id=0xCAFEBABE,
    )
    raw = bytes(h)
    assert struct.unpack("<I", raw[0:4])[0] == DdrBlockHeader.MAGIC
    assert raw[4] == 1                                              # version 默认值
    assert struct.unpack("<H", raw[6:8])[0] == 0xABCD              # frag_seq
    assert struct.unpack("<H", raw[8:10])[0] == 0x1234             # frag_total
    assert struct.unpack("<H", raw[10:12])[0] == 0x5678            # channel_id
    assert struct.unpack("<I", raw[12:16])[0] == 0x11223344        # payload_length
    assert struct.unpack("<I", raw[16:20])[0] == 0xCAFEBABE        # block_id
    assert raw[20:].count(0) == 492                                # reserved zeros


def test_header_hw_proto_frag_flag_at_bit0():
    """frag_flag 必须在 bit 0；其它位 0 时整字节 == 0x01。"""
    h = DdrBlockHeader(
        frag_flag=1, frag_seq=0, frag_total=1, channel_id=0,
        payload_length=0, block_id=0,
    )
    assert bytes(h)[5] == 0x01


def test_header_hw_proto_priority_and_encrypt():
    """priority @ bit 1..3, encrypt @ bit 4."""
    h = DdrBlockHeader(
        frag_flag=1, frag_seq=0, frag_total=1, channel_id=0,
        payload_length=0, block_id=0,
        priority=0x5,                 # 二进制 101
        encrypt=1,
    )
    # bit 4 (encrypt=1) | bit 1..3 (priority=0b101 → << 1 = 0b1010) | bit 0 (frag=1) = 0x1B
    assert bytes(h)[5] == 0x1B
# endregion


# region 块头 round-trip ────────────────────────────────────────────
def test_header_round_trip():
    orig = DdrBlockHeader(
        frag_flag=1, frag_seq=3, frag_total=10, channel_id=0x100,
        payload_length=2048, block_id=0xDEADBEEF,
        priority=2, encrypt=1, version=1,
    )
    parsed = DdrBlockHeader.from_bytes(bytes(orig))
    assert parsed == orig


def test_header_from_bytes_bad_magic():
    bad = b"\x00\x00\x00\x00" + b"\x00" * 16
    with pytest.raises(DataIntegrityError, match="magic"):
        DdrBlockHeader.from_bytes(bad)


def test_header_from_bytes_truncated():
    with pytest.raises(DataIntegrityError, match="至少 20B"):
        DdrBlockHeader.from_bytes(b"\x00\x00")
# endregion


# region 分片填写 (核心) ────────────────────────────────────────────
def test_fragment_empty_payload():
    chunks = fragment_payload(b"", block_id=1)
    assert len(chunks) == 1
    h = chunks[0].header
    assert h.frag_flag == 0
    assert h.frag_total == 1
    assert h.payload_length == 0


def test_fragment_small_payload_single_chunk():
    """payload <= max_per_chunk → 1 chunk，非分片。"""
    payload = b"\xAA" * 100
    chunks = fragment_payload(payload, block_id=1)
    assert len(chunks) == 1
    h = chunks[0].header
    assert h.frag_flag == 0                               # 非分片
    assert h.frag_seq == 0
    assert h.frag_total == 1
    assert h.payload_length == 100
    assert chunks[0].payload == payload


def test_fragment_at_boundary_single_chunk():
    """payload 刚好 == max_per_chunk → 仍 1 chunk（边界）。"""
    payload = b"\xBB" * DEFAULT_MAX_PAYLOAD_PER_CHUNK
    chunks = fragment_payload(payload, block_id=1)
    assert len(chunks) == 1
    assert chunks[0].header.frag_flag == 0


def test_fragment_large_payload_multi_chunk():
    """payload > max_per_chunk → N chunks，所有 frag_flag=1，序号 0..N-1。"""
    size = DEFAULT_MAX_PAYLOAD_PER_CHUNK * 2 + 100        # 跨 3 个 chunk
    payload = bytes((i % 256) for i in range(size))
    chunks = fragment_payload(
        payload, block_id=42, config=DdrConfig(channel_id=7),
    )
    assert len(chunks) == 3
    for i, ch in enumerate(chunks):
        assert ch.header.frag_flag == 1
        assert ch.header.frag_seq == i
        assert ch.header.frag_total == 3
        assert ch.header.block_id == 42                   # 共享
        assert ch.header.channel_id == 7
    # payload_length 字段：前两片满，最后一片 100B
    assert chunks[0].header.payload_length == DEFAULT_MAX_PAYLOAD_PER_CHUNK
    assert chunks[1].header.payload_length == DEFAULT_MAX_PAYLOAD_PER_CHUNK
    assert chunks[2].header.payload_length == 100
    # 拼回原 payload
    rejoined = b"".join(c.payload for c in chunks)
    assert rejoined == payload


def test_fragment_block_id_shared_across_fragments():
    """同一逻辑包所有 chunk 必须共享 block_id。"""
    payload = b"\x00" * (DEFAULT_MAX_PAYLOAD_PER_CHUNK * 3)
    chunks = fragment_payload(payload, block_id=0xCAFE)
    bids = {c.header.block_id for c in chunks}
    assert bids == {0xCAFE}


def test_fragment_custom_max_per_chunk():
    """自定义 max 切成更细的 chunk。"""
    payload = b"\x00" * 1000
    chunks = fragment_payload(
        payload, block_id=1, config=DdrConfig(max_payload_per_chunk=300),
    )
    assert len(chunks) == 4                               # ceil(1000/300)
    assert [c.header.payload_length for c in chunks] == [300, 300, 300, 100]


def test_fragment_invalid_max_rejected():
    with pytest.raises(ValueError, match="必须 > 0"):
        fragment_payload(
            b"\x00", block_id=1, config=DdrConfig(max_payload_per_chunk=0),
        )
# endregion


# region DdrChunk 总长对齐 + 拼接 ────────────────────────────────────
def test_chunk_total_length_512_aligned():
    """每个 chunk 总长应为 512 字节倍数。"""
    payload = b"\xCC" * 1234                              # 任意长度
    chunks = fragment_payload(payload, block_id=1)
    for ch in chunks:
        assert len(bytes(ch)) % 512 == 0


def test_chunk_concat_via_pack():
    """``pack(chunks)`` 拼接（推荐）。"""
    payload = b"\xDD" * (DEFAULT_MAX_PAYLOAD_PER_CHUNK * 2 + 50)
    chunks = fragment_payload(payload, block_id=1)
    raw = pack(chunks)
    assert len(raw) == sum(len(bytes(c)) for c in chunks)
    assert struct.unpack("<I", raw[0:4])[0] == DdrBlockHeader.MAGIC


def test_chunk_concat_via_sum_still_works():
    """``sum(chunks, 0)`` 仍兼容（``__radd__`` 保留）。"""
    payload = b"\xDD" * (DEFAULT_MAX_PAYLOAD_PER_CHUNK * 2 + 50)
    chunks = fragment_payload(payload, block_id=1)
    raw = bytes(sum(chunks, 0))                            # type: ignore[arg-type]
    assert raw == pack(chunks)
# endregion


# region 业务层自由拼（演示用 struct.pack） ────────────────────────
def test_business_layer_free_struct_compose():
    """演示：业务用 struct.pack 任意拼，再交给 fragment_payload。"""
    vport_hdr = struct.pack("<HHI", 0x100, 0x0, 0)         # 8B
    biz_hdr = struct.pack("<II", 0xCAFE, 0x12345678)       # 8B
    biz_field = b"\xAB" * 32
    full_payload = vport_hdr + biz_hdr + biz_field         # 48B

    chunks = fragment_payload(
        full_payload, block_id=1, config=DdrConfig(channel_id=0x100),
    )
    assert len(chunks) == 1                                # 48B 不分片
    assert chunks[0].payload == full_payload
    assert chunks[0].header.payload_length == 48
    assert chunks[0].header.channel_id == 0x100
# endregion


# region DdrSender — 减参 + 自动 block_id ───────────────────────────
def test_sender_auto_increments_block_id():
    """连续 send 的 block_id 自增。"""
    sender = DdrSender(DdrConfig(channel_id=0x100))
    chunks_a = sender.send(b"\xAA" * 10)
    chunks_b = sender.send(b"\xBB" * 10)
    chunks_c = sender.send(b"\xCC" * 10)
    assert chunks_a[0].header.block_id == 1
    assert chunks_b[0].header.block_id == 2
    assert chunks_c[0].header.block_id == 3


def test_sender_propagates_config():
    """config 字段透传到所有 chunk 头。"""
    sender = DdrSender(DdrConfig(channel_id=0x200, priority=3, encrypt=1))
    chunks = sender.send(b"\xFF" * 50)
    h = chunks[0].header
    assert h.channel_id == 0x200
    assert h.priority == 3
    assert h.encrypt == 1


def test_sender_reset():
    """reset 把 block_id 序号清回 1，config 不变。"""
    sender = DdrSender(DdrConfig(channel_id=0x100))
    sender.send(b"a")
    sender.send(b"b")
    assert sender.next_block_id == 3
    sender.reset()
    assert sender.next_block_id == 1
    assert sender.config.channel_id == 0x100              # config 未动


def test_sender_multi_chunk_shared_block_id():
    """单次 send 触发分片时所有分片共享同一 block_id。"""
    sender = DdrSender(DdrConfig(max_payload_per_chunk=100))
    chunks = sender.send(b"\xAA" * 250)                   # 触发 3 分片
    assert len(chunks) == 3
    assert {c.header.block_id for c in chunks} == {1}     # 共享
    sender.send(b"\x00")
    # 下一次 send 拿到 block_id=2
    assert sender.next_block_id == 3                      # 已用 1 + 2


def test_sender_default_config():
    """无参构造用空 config（channel=0 / priority=0 / encrypt=0）。"""
    sender = DdrSender()
    chunks = sender.send(b"x")
    h = chunks[0].header
    assert h.channel_id == 0 and h.priority == 0 and h.encrypt == 0
# endregion
