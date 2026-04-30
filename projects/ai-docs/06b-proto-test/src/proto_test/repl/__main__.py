"""``python -m proto_test.repl`` — REPL CLI 入口.

两种模式（subcommand）：

- ``server`` — 起一个 mock 桩 CPU 服务（演示协议；真部署用 RTOS 实现）
- ``client`` — 连 server，进入交互 REPL

样例两 terminal::

    # terminal 1
    python -m proto_test.repl server --port 5000

    # terminal 2
    python -m proto_test.repl client --host 127.0.0.1 --port 5000 \\
        --invoke DUT_DBG_ClientHandshake --invoke SVC_COMPARE_PullBatch
"""
from __future__ import annotations

import argparse
import sys
import time

from ..protocol.memory import Datatype
from .console import DebugConsole
from .transport import StubServer


def _cmd_server(args: argparse.Namespace) -> int:
    """起 mock 服务（demo 用；填一组示例数据 + 函数注册表）."""
    backing = bytearray(args.size)
    backing[0x100000:0x100004] = (0xD06DBE60).to_bytes(4, "little")
    backing[0x1000:0x1004]     = (3).to_bytes(4, "little")              # g_compareBufDebugCnt = 3
    for i, (tid, cnt, length, addr) in enumerate(
        [(0x10, 0, 100, 0x4000), (0x10, 1, 200, 0x4100), (0x20, 0, 64, 0x4200)],
        start=0,
    ):
        off = 0x1100 + i * 16
        backing[off:off + 16] = (
            tid.to_bytes(2, "little") + cnt.to_bytes(2, "little")
            + length.to_bytes(4, "little") + addr.to_bytes(8, "little")
        )

    def _dut_dbg_handshake() -> int:
        magic = int.from_bytes(backing[0x100000:0x100004], "little")
        print(f"[stub] region magic = 0x{magic:x}")
        return 0 if magic == 0xD06DBE60 else -1

    def _svc_compare_pull() -> int:
        n = int.from_bytes(backing[0x1000:0x1004], "little")
        print(f"[stub] g_compareBufDebugCnt = {n}")
        return n

    server = StubServer(
        backing=backing,
        symbols={
            "g_compareBufDebugCnt": 0x1000,
            "g_compareBufCompAddr": 0x1100,
        },
        functions={
            "DUT_DBG_ClientHandshake": _dut_dbg_handshake,
            "SVC_COMPARE_PullBatch":   _svc_compare_pull,
        },
        host=args.host, port=args.port,
    )
    server.serve_forever_in_thread()
    print(f"[server] listening on {args.host}:{args.port}; Ctrl-C to stop")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[server] stopping")
    server.shutdown()
    return 0


def _cmd_client(args: argparse.Namespace) -> int:
    print(f"[client] connecting to {args.host}:{args.port}")
    console = DebugConsole.from_socket(
        host=args.host,
        port=args.port,
        function_names=list(args.invoke or []),
        default_dtype=Datatype.UINT32,
    )
    console.run()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="proto_test.repl")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("server", help="run mock stub-CPU RPC server (demo)")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", default=5000, type=int)
    s.add_argument("--size", default=1 << 24, type=int, help="backing memory size")
    s.set_defaults(func=_cmd_server)

    c = sub.add_parser("client", help="connect to stub-CPU and run REPL")
    c.add_argument("--host", default="127.0.0.1")
    c.add_argument("--port", default=5000, type=int)
    c.add_argument("--invoke", action="append",
                   help="register a remote function name (repeatable)")
    c.set_defaults(func=_cmd_client)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
