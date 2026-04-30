"""DebugConsole 远端 transport — socket 连桩 CPU.

最小 JSON-line RPC（每行一条消息）：

    client → server: {"op":"read",   "addr":0x1000, "n":4}
    server → client: {"ok":true, "data":"2a000000"}             (hex str)

    client → server: {"op":"write",  "addr":0x1000, "data":"2a000000"}
    server → client: {"ok":true}

    client → server: {"op":"invoke", "name":"FN", "args":[10,20]}
    server → client: {"ok":true, "ret":0, "stdout":"[fn] ...\\n"}

    client → server: {"op":"resolve", "symbol":"g_x"}
    server → client: {"ok":true, "addr":4096}

入口：
- ``RemoteMemPort``       — client 端 MemPort 实现（read/write 走 socket）
- ``RemoteSymbolMap``     — client 端 SymbolMap（resolve 走 socket）
- ``LogSource``           — 服务端"日志来源"Protocol（drain() → str）
- ``StdoutLogSource``     — demo 用：把 ``print()`` 重定向到 buffer
- ``RttLogSource``        — 真部署骨架：从 RTT 环形缓冲 pump 日志
- ``StubServer``          — demo mock server（同进程跑桩 CPU 角色，演示协议）

日志回显设计（重要）：
- 真桩 CPU / DUT 没有 ``print()``；``dbginfo`` 写 RTT / 串口 / 自家日志环
- ``LogSource`` 抽象封装"取本次 invoke 期间产生的日志"
- demo 用 ``StdoutLogSource``（stdout capture）；真部署换成 ``RttLogSource``
  （内部调 ``DUT_DBG_RttPump`` 或自家日志 pump 函数），协议层不变
"""
from __future__ import annotations

import io
import json
import socket
import socketserver
import threading
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Protocol, runtime_checkable

from ..foundation.errors import (
    CommError,
    DataIntegrityError,
    ERR_DATA_CRC_MISMATCH,
    SymbolNotFoundError,
)


# region client side ─────────────────────────────────────────────
@dataclass
class _LineSocket:
    """JSON-line socket 封装：发一条 / 收一条。"""

    sock: socket.socket
    _rfile: Any = field(init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self) -> None:
        self._rfile = self.sock.makefile("r", encoding="utf-8")

    def request(self, msg: dict) -> dict:
        line = json.dumps(msg, separators=(",", ":")) + "\n"
        with self._lock:
            self.sock.sendall(line.encode("utf-8"))
            reply = self._rfile.readline()
        if not reply:
            raise CommError("connection closed by peer")
        return json.loads(reply)

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


@dataclass
class RemoteMemPort:
    """``MemPort`` 协议的 socket 实现 — read/write 走 RPC."""

    link: _LineSocket

    def read(self, addr: int, n: int) -> bytes:
        rep = self.link.request({"op": "read", "addr": addr, "n": n})
        if not rep.get("ok"):
            raise CommError(f"read failed: {rep.get('error')}")
        data = bytes.fromhex(rep["data"])
        if len(data) != n:
            raise DataIntegrityError(
                f"read got {len(data)}B, want {n}B",
                code=ERR_DATA_CRC_MISMATCH,
            )
        return data

    def write(self, addr: int, raw: bytes) -> None:
        rep = self.link.request({"op": "write", "addr": addr, "data": raw.hex()})
        if not rep.get("ok"):
            raise CommError(f"write failed: {rep.get('error')}")


@dataclass
class RemoteSymbolMap:
    """``SymbolMap`` 兼容形：resolve 走 RPC（mimics ``proto_test.protocol.memory.SymbolMap``）."""

    link: _LineSocket
    table: Dict[str, int] = field(default_factory=dict)   # 本地缓存

    def resolve(self, symbol: str) -> int:
        if symbol in self.table:
            return self.table[symbol]
        rep = self.link.request({"op": "resolve", "symbol": symbol})
        if not rep.get("ok"):
            raise SymbolNotFoundError(symbol, code=0x4100)
        addr = int(rep["addr"])
        self.table[symbol] = addr
        return addr


def make_remote_invoker(link: _LineSocket, name: str) -> Callable[..., Any]:
    """生成一个 callable，调用时通过 socket 把 invoke 转发给 server."""
    def _call(*args: Any) -> Any:
        rep = link.request({"op": "invoke", "name": name, "args": list(args)})
        if not rep.get("ok"):
            raise CommError(f"invoke {name} failed: {rep.get('error')}")
        echo = rep.get("stdout", "")
        if echo:
            print(echo, end="" if echo.endswith("\n") else "\n")
        return rep.get("ret")
    return _call


def connect(host: str, port: int) -> _LineSocket:
    sock = socket.create_connection((host, port), timeout=5.0)
    return _LineSocket(sock)
# endregion


# region log source — 真 / mock 两套实现 ────────────────────
@runtime_checkable
class LogSource(Protocol):
    """日志来源 — 取本次 invoke 期间产生的日志.

    实现约定：
    - ``attach()`` 在 invoke 开始前调用，开始累积
    - ``drain()`` 在 invoke 结束后调用，返回累积内容并清空
    - ``detach()`` 在 invoke 后调用做清理（可选 no-op）
    """
    def attach(self) -> None: ...
    def drain(self) -> str: ...
    def detach(self) -> None: ...


class StdoutLogSource:
    """demo / mock — 把被调函数 ``print()`` 输出重定向到 buffer.

    用于 demo 的 Python 函数模拟"被测系统 dbginfo"行为；不适用真嵌入式部署。
    """

    def __init__(self) -> None:
        self._buf: io.StringIO = io.StringIO()
        self._cm: Optional[Any] = None

    def attach(self) -> None:
        self._buf = io.StringIO()
        self._cm = redirect_stdout(self._buf)
        self._cm.__enter__()

    def detach(self) -> None:
        if self._cm is not None:
            self._cm.__exit__(None, None, None)
            self._cm = None

    def drain(self) -> str:
        return self._buf.getvalue()


@dataclass
class RttLogSource:
    """真部署骨架 — 从 RTT 环形缓冲 pump 日志.

    ``pump_fn`` 由业务实现，签名 ``() -> bytes``，每次调用返回自上次以来 RTT
    新增字节（实现一般是：读 wrOff/rdOff，按差量 SoftDebug 读出 buffer 段，
    写回 rdOff，参考 06a/stub_cpu/dut_dbg_client.c::DUT_DBG_RttPump）。

    invoke 包围语义：``attach`` 先 drain 一次清掉前置噪音；``drain`` 拿本次。
    """

    pump_fn: Callable[[], bytes]
    encoding: str = "utf-8"

    def attach(self) -> None:
        # 清掉本次 invoke 之前的残余日志
        _ = self.pump_fn()

    def drain(self) -> str:
        return self.pump_fn().decode(self.encoding, errors="replace")

    def detach(self) -> None:
        pass
# endregion


# region server side （demo mock 桩 CPU）─────────────────────
@dataclass
class StubServer:
    """demo mock 桩 CPU — 同进程持有 ``MemPort`` + 函数注册表，监听 socket 提供 RPC.

    真部署里这个 server 跑在桩 CPU RTOS 上（C 实现），协议格式相同。

    ``log_source`` 决定 invoke 回显的来源：
    - 默认 ``StdoutLogSource`` — 捕获 Python 函数 ``print()``（demo 用）
    - 真部署传 ``RttLogSource(rtt_pump_fn)`` — 从 RTT 环形缓冲 pump 日志
    - ``None`` 则 invoke 不带 stdout 字段
    """

    backing: bytearray
    symbols: Dict[str, int] = field(default_factory=dict)
    functions: Dict[str, Callable[..., Any]] = field(default_factory=dict)
    log_source: Optional[LogSource] = None
    host: str = "127.0.0.1"
    port: int = 5000

    _server: Optional[socketserver.ThreadingTCPServer] = field(default=None, init=False)
    _thread: Optional[threading.Thread] = field(default=None, init=False)
    _log_lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self) -> None:
        if self.log_source is None:
            self.log_source = StdoutLogSource()

    def serve_forever_in_thread(self) -> None:
        backing = self.backing
        symbols = self.symbols
        functions = self.functions
        log_source = self.log_source
        log_lock = self._log_lock

        class _Handler(socketserver.StreamRequestHandler):
            def handle(self) -> None:
                while True:
                    line = self.rfile.readline()
                    if not line:
                        return
                    try:
                        req = json.loads(line)
                        rep = _dispatch(req, backing, symbols, functions,
                                        log_source, log_lock)
                    except Exception as e:                  # noqa: BLE001
                        rep = {"ok": False, "error": f"{type(e).__name__}: {e}"}
                    self.wfile.write((json.dumps(rep) + "\n").encode("utf-8"))

        socketserver.ThreadingTCPServer.allow_reuse_address = True
        self._server = socketserver.ThreadingTCPServer((self.host, self.port), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def shutdown(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None


def _dispatch(req: dict,
              backing: bytearray,
              symbols: Dict[str, int],
              functions: Dict[str, Callable[..., Any]],
              log_source: Optional[LogSource],
              log_lock: threading.Lock) -> dict:
    op = req.get("op")
    if op == "read":
        addr = int(req["addr"]); n = int(req["n"])
        if addr < 0 or addr + n > len(backing):
            return {"ok": False, "error": f"read out of range addr=0x{addr:x} n={n}"}
        return {"ok": True, "data": bytes(backing[addr:addr + n]).hex()}
    if op == "write":
        addr = int(req["addr"]); data = bytes.fromhex(req["data"])
        if addr < 0 or addr + len(data) > len(backing):
            return {"ok": False, "error": f"write out of range addr=0x{addr:x}"}
        backing[addr:addr + len(data)] = data
        return {"ok": True}
    if op == "resolve":
        sym = req["symbol"]
        if sym not in symbols:
            return {"ok": False, "error": f"symbol not found: {sym}"}
        return {"ok": True, "addr": symbols[sym]}
    if op == "invoke":
        name = req["name"]
        if name not in functions:
            return {"ok": False, "error": f"unknown function: {name}"}
        args = req.get("args", [])
        # log_source 串行化：StdoutLogSource 用全局 redirect_stdout，多线程并发会乱序
        with log_lock:
            if log_source is not None:
                log_source.attach()
            try:
                ret = functions[name](*args)
            finally:
                log = log_source.drain() if log_source is not None else ""
                if log_source is not None:
                    log_source.detach()
        rep: Dict[str, Any] = {"ok": True, "ret": ret}
        if log:
            rep["stdout"] = log
        return rep
    return {"ok": False, "error": f"unknown op: {op}"}
# endregion
