"""测试底座 fixtures."""
from __future__ import annotations

import pytest

from proto_test import CompareEntry, DummyAdapter, MemoryCompareDriver


@pytest.fixture
def adapter() -> DummyAdapter:
    """空白 1 MiB 内存平台。"""
    return DummyAdapter(mem_size=1 << 20, endian="<")


@pytest.fixture
def adapter_with_compare_symbols(adapter: DummyAdapter) -> DummyAdapter:
    """已安装 ``g_compareBufDebugCnt`` + ``g_compareBufCompAddr`` 符号 + 张量缓冲。

    地址布局（示意，可任意改）::
        0x1000  g_compareBufDebugCnt           (uint32, 4B)
        0x1100  g_compareBufCompAddr[200]      (CompareEntry × 200)
        0x4000  tensor 数据缓冲区     (32 KiB 给比数张量)
    """
    adapter.install_symbol("g_compareBufDebugCnt", 0x1000)
    adapter.install_symbol("g_compareBufCompAddr", 0x1100)
    return adapter


@pytest.fixture
def cmp_driver(adapter_with_compare_symbols: DummyAdapter) -> MemoryCompareDriver:
    return MemoryCompareDriver(mem=adapter_with_compare_symbols.mem)
