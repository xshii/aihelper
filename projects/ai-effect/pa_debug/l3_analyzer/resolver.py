"""外部内容解析端口。具体实现由组合根注入(读本地文件 / 内存等)。"""

from __future__ import annotations

from typing import Protocol


class BlobResolver(Protocol):
    def fetch(self, blob: str, addr: int) -> list[int]:
        """返回 blob 在 addr 处的 word 序列(字节→word 的换算由适配器按真实格式处理)。"""
        ...
