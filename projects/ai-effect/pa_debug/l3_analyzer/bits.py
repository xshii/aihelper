"""按位读 word 流的公共原语。LSB-first:word[0] 在低位。依赖抽取与解码器共用。"""

from __future__ import annotations

from .model import DecodeError


class BitReader:
    """把 word 流拉平成一个大整数,从低位向高位顺序读。"""

    def __init__(self, words: list[int], word_bits: int = 32) -> None:
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
