"""IOMixin — 文件读写能力。

hex txt 格式（芯片验证用）：
    文件名: {op}_{id}_{operand}_{dtype}_{shape}_{format}.txt
    内容: 一行一个 0x{:08X}
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch


class IOMixin:
    """文件读写。"""

    def export(self, path: str):
        """写入 hex txt 文件。返回 self（链式）。"""
        lines = tensor_to_uint32_lines(self._tensor)
        with open(path, "w") as f:
            for line in lines:
                f.write(line + "\n")
        self._log(f"export({path})")
        return self

    @classmethod
    def load(cls, path: str):
        """从 hex txt 文件加载。从文件名解析 dtype/shape/format。"""
        meta = parse_filename(path)
        dtype_name = meta.get("dtype", "float32")
        shape = meta.get("shape", ())
        from ..core.enums import Format
        fmt = meta.get("format", Format.ND)

        # 推断 torch dtype
        from ..core.dtype import get_dtype
        try:
            dsp_dtype = get_dtype(dtype_name)
            torch_dtype = dsp_dtype.torch_dtype
        except ValueError:
            torch_dtype = torch.float32

        with open(path) as f:
            lines = f.readlines()
        raw = uint32_lines_to_bytes(lines)
        np_dtype = torch.zeros(1, dtype=torch_dtype).numpy().dtype
        arr = np.frombuffer(raw, dtype=np_dtype)[:np.prod(shape) if shape else len(raw) // 4]
        tensor = torch.from_numpy(arr.copy()).reshape(shape) if shape else torch.from_numpy(arr.copy())

        return cls(tensor, dtype=dtype_name, fmt=fmt)


# ============================================================
# 文件名构造 / 解析
# ============================================================

def make_filename(op: str, op_id: int, operand: str,
                  dtype_name: str, shape: tuple, fmt="nd") -> str:
    shape_str = "x".join(str(s) for s in shape)
    return f"{op}_{op_id}_{operand}_{dtype_name}_{shape_str}_{fmt}.txt"


def parse_filename(filename: str) -> dict:
    name = Path(filename).stem
    # 去掉 .native 后缀
    if name.endswith(".native"):
        name = name[:-7]
    parts = name.split("_")
    if len(parts) < 6:
        return {"raw": name}
    return {
        "op": parts[0], "op_id": int(parts[1]), "operand": parts[2],
        "dtype": parts[3], "shape": tuple(int(d) for d in parts[4].split("x")),
        "format": parts[5],
    }


# ============================================================
# hex 转换
# ============================================================

def tensor_to_uint32_lines(t: torch.Tensor) -> list[str]:
    raw_bytes = t.detach().cpu().contiguous().numpy().tobytes()
    pad_len = (4 - len(raw_bytes) % 4) % 4
    raw_bytes += b'\x00' * pad_len
    lines = []
    for i in range(0, len(raw_bytes), 4):
        word = int.from_bytes(raw_bytes[i:i+4], byteorder='little')
        lines.append(f"0x{word:08X}")
    return lines


def uint32_lines_to_bytes(lines: list[str]) -> bytes:
    result = bytearray()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        word = int(line, 16)
        result.extend(word.to_bytes(4, byteorder='little'))
    return bytes(result)
