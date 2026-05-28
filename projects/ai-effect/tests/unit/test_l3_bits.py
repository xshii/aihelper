"""BitReader:LSB-first 按位读 word 流,越界报错。"""

import pytest

from pa_debug.l3_analyzer.bits import BitReader
from pa_debug.l3_analyzer.model import DecodeError


def test_reads_lsb_first_within_one_word():
    r = BitReader([0xABCD], word_bits=16)
    assert r.read(8) == 0xCD
    assert r.read(8) == 0xAB


def test_reads_across_word_boundary():
    r = BitReader([0x0001, 0x0002], word_bits=16)  # 流 = 0x0002_0001
    assert r.read(16) == 0x0001
    assert r.read(16) == 0x0002


def test_read_past_end_raises():
    r = BitReader([0x1], word_bits=4)
    r.read(4)
    with pytest.raises(DecodeError):
        r.read(1)
