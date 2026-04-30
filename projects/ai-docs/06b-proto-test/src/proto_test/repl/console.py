"""DebugConsole — 交互式调试 REPL（详见 06b § 4.9）.

三个原子能力（GDB 风格简化语法）：
- ``<symbol>[:DTYPE]``        查变量值（默认 UINT32）
- ``d <addr|sym> [n]``        hex-dump n 字节（默认 16）
- ``! <fn> [args...]``        调被测系统函数 + 显示返回值/DEBUG 回显
"""
from __future__ import annotations

import contextlib
import io
import shlex
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, TextIO

from ..protocol.memory import Datatype, MemAccessAPI, _ScalarType
from .transport import (
    RemoteMemPort,
    RemoteSymbolMap,
    connect,
    make_remote_invoker,
)


@dataclass
class DebugConsole:
    """REPL 主体。``run()`` 进入交互；``handle(line)`` 单行 dispatch（测试用）。"""

    mem: MemAccessAPI
    functions: Dict[str, Callable[..., Any]] = field(default_factory=dict)
    default_dtype: _ScalarType = field(default_factory=lambda: Datatype.UINT32)
    prompt: str = "debug> "
    output: Optional[TextIO] = None

    def __post_init__(self) -> None:
        if self.output is None:
            self.output = sys.stdout

    @classmethod
    def from_socket(cls, host: str, port: int, *,
                    function_names: Optional[list] = None,
                    **kwargs: Any) -> "DebugConsole":
        """连远端桩 CPU socket — 跟 pytest 完全独立的另一个进程跑.

        ``function_names`` 列出要在 REPL 里调的远端函数名；本地透明转发到桩端。
        """
        link = connect(host, port)
        mem = MemAccessAPI(
            port=RemoteMemPort(link),
            symbols=RemoteSymbolMap(link),                 # type: ignore[arg-type]
        )
        functions: Dict[str, Callable[..., Any]] = {
            name: make_remote_invoker(link, name)
            for name in (function_names or [])
        }
        return cls(mem=mem, functions=functions, **kwargs)

    def run(self) -> None:
        """阻塞主循环。Ctrl-D / quit / exit 退出。"""
        while True:
            try:
                line = input(self.prompt)
            except (EOFError, KeyboardInterrupt):
                self._println("")
                return
            line = line.strip()
            if not line:
                continue
            if line in ("quit", "exit", "q"):
                return
            if line == "help":
                self._help()
                continue
            try:
                self.handle(line)
            except Exception as e:                  # noqa: BLE001
                self._println(f"ERROR: {type(e).__name__}: {e}")

    def handle(self, line: str) -> None:
        """单行 dispatch — 前缀决定 ``d ``=dump，``!``=call，其他=查符号。"""
        if line.startswith("!"):
            self._call(line[1:].strip())
        elif line.startswith("d ") or line == "d":
            self._dump(line[1:].strip())
        else:
            self._read_symbol(line)

    # region 三个原子能力 ───────────────────────────────────────
    def _read_symbol(self, expr: str) -> None:
        if ":" in expr:
            symbol, dtype_name = expr.rsplit(":", 1)
            symbol = symbol.strip()
            dtype = self._resolve_dtype(dtype_name.strip())
        else:
            symbol = expr.strip()
            dtype = self.default_dtype
        val = self.mem.ReadVal(symbol, dtype)
        self._println(self._format_value(symbol, val))

    def _dump(self, expr: str) -> None:
        if not expr:
            self._println("usage: d <addr|symbol> [length]")
            return
        parts = expr.split()
        target = parts[0]
        n = int(parts[1], 0) if len(parts) > 1 else 16
        addr = self._resolve_addr(target)
        raw = self.mem.ReadBytes(addr, n)
        self._hex_dump(addr, raw)

    def _call(self, expr: str) -> None:
        if not expr:
            self._println("usage: ! <fn> [args...]")
            return
        parts = shlex.split(expr)
        name = parts[0]
        if name not in self.functions:
            available = ", ".join(sorted(self.functions)) or "(none registered)"
            self._println(f"ERROR: unknown function '{name}'. Available: {available}")
            return
        args = [self._parse_arg(a) for a in parts[1:]]
        # 捕获被调函数 stdout 当作"DEBUG 回显"；返回值单独打印
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ret = self.functions[name](*args)
        echo = buf.getvalue()
        if echo:
            self._print(echo if echo.endswith("\n") else echo + "\n")
        self._println(f"=> {ret!r}")
    # endregion

    # region helpers ─────────────────────────────────────────────
    @staticmethod
    def _resolve_dtype(name: str) -> _ScalarType:
        attr = name.upper()
        dtype = getattr(Datatype, attr, None)
        if not isinstance(dtype, _ScalarType):
            raise ValueError(f"unknown dtype '{name}'; try UINT32 / INT64 / FLOAT 等")
        return dtype

    def _resolve_addr(self, target: str) -> int:
        try:
            return int(target, 0)               # 0x... / 十进制
        except ValueError:
            return self.mem._symbols.resolve(target)

    @staticmethod
    def _parse_arg(s: str) -> Any:
        try:
            return int(s, 0)
        except ValueError:
            return s

    @staticmethod
    def _format_value(symbol: str, val: Any) -> str:
        if isinstance(val, int):
            return f"{symbol} = {val} (0x{val:x})"
        return f"{symbol} = {val!r}"

    def _hex_dump(self, addr: int, raw: bytes) -> None:
        for i in range(0, len(raw), 16):
            chunk = raw[i:i + 16]
            hexs = " ".join(f"{b:02x}" for b in chunk)
            asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            self._println(f"0x{addr + i:08x}  {hexs:<48}  {asc}")

    def _help(self) -> None:
        self._println(
            "commands:\n"
            "  <symbol>[:DTYPE]      query variable value\n"
            "  d <addr|sym> [n]      hex-dump n bytes (default 16)\n"
            "  ! <fn> [args...]      call registered DUT-side function\n"
            "  help / quit / exit / q\n"
        )

    def _println(self, s: str) -> None:
        print(s, file=self.output)

    def _print(self, s: str) -> None:
        print(s, end="", file=self.output)
    # endregion
