#!/usr/bin/env python3
"""
deploy.py 的 mock 测试套件

每个 case 在独立 tmpdir 里写 mock shell 脚本 + manifest.json，
然后把 deploy.py 作为子进程跑起来，验证 stdout / exit code。

运行:  python3 test_deploy.py
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent.resolve()
DEPLOY = HERE / "deploy.py"
PY = sys.executable

tests = []


def case(name):
    def deco(fn):
        tests.append((name, fn))
        return fn

    return deco


def run_deploy(workdir: Path, timeout: float = 15):
    result = subprocess.run(
        [PY, str(DEPLOY)],
        cwd=str(workdir),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout


def write_exec(p: Path, body: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    os.chmod(p, 0o755)


def write_manifest(workdir: Path, manifest: dict):
    (workdir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False)
    )


def assert_in(needle: str, out: str, msg: str = ""):
    if needle not in out:
        raise AssertionError(
            f"期望 '{needle}' 出现在输出中{(' (' + msg + ')') if msg else ''}\n"
            f"─── stdout ───\n{out}\n──────────────"
        )


def assert_not_in(needle: str, out: str, msg: str = ""):
    if needle in out:
        raise AssertionError(
            f"不该出现 '{needle}'{(' (' + msg + ')') if msg else ''}\n"
            f"─── stdout ───\n{out}\n──────────────"
        )


# ════════════════════════════════════════════════════════════
# T1 · 两级 cont_ref 链 + 命名组跨任务传递
# ════════════════════════════════════════════════════════════
@case("T1 · happy path 两级链 + 命名组传递")
def t1(wd):
    write_exec(
        wd / "server.sh",
        """#!/bin/bash
echo "starting..."
sleep 0.3
echo "listening on port 8080"
sleep 0.3
echo "request served: /hello"
sleep 0.3
echo "shutting down"
exit 0
""",
    )
    write_manifest(
        wd,
        {
            "tasks": [
                {
                    "name": "start-server",
                    "order": 1,
                    "usage": f"bash {wd}/server.sh",
                    "keyword": [
                        {
                            "type": "success",
                            "cont_ref": "server_up",
                            "word": r"listening on port (?P<port>\d+)",
                        }
                    ],
                },
                {
                    "name": "call-api",
                    "order": 2,
                    "depends": "server_up",
                    "usage": "echo calling api on port #{port}",
                },
                {
                    "name": "#server_up",
                    "keyword": [
                        {
                            "type": "success",
                            "cont_ref": "first_req",
                            "word": r"request served: (?P<path>/\S+)",
                        }
                    ],
                },
                {
                    "name": "log-analyze",
                    "order": 3,
                    "depends": "first_req",
                    "usage": "echo first request path: #{path}",
                },
            ]
        },
    )
    rc, out = run_deploy(wd)
    assert_in("calling api on port 8080", out, "call-api 没拿到 #{port}")
    assert_in("first request path: /hello", out, "log-analyze 没拿到 #{path}")
    assert_in("#{port} = 8080", out, "命名组未出现在总结")
    assert_in("#{path} = /hello", out, "命名组未出现在总结")
    return f"rc={rc}, 4 task 全部推进"


# ════════════════════════════════════════════════════════════
# T2 · times=3
# ════════════════════════════════════════════════════════════
@case("T2 · times=3 第 3 次命中才触发")
def t2(wd):
    write_exec(
        wd / "emit.sh",
        """#!/bin/bash
echo "event A"
echo "event B"
sleep 0.3
echo "event C"
sleep 0.3
exit 0
""",
    )
    write_manifest(
        wd,
        {
            "tasks": [
                {
                    "name": "counter",
                    "order": 1,
                    "usage": f"bash {wd}/emit.sh",
                    "keyword": [
                        {
                            "type": "success",
                            "cont_ref": "three",
                            "word": r"event \w",
                            "times": 3,
                        }
                    ],
                },
                {
                    "name": "after",
                    "order": 2,
                    "depends": "three",
                    "usage": "echo 'three events seen'",
                },
            ]
        },
    )
    rc, out = run_deploy(wd)
    assert_in("three events seen", out, "times=3 没触发")
    return f"rc={rc}"


# ════════════════════════════════════════════════════════════
# T3 · 命名组冲突加载期报错
# ════════════════════════════════════════════════════════════
@case("T3 · 命名组冲突加载期报错")
def t3(wd):
    write_manifest(
        wd,
        {
            "tasks": [
                {
                    "name": "a",
                    "usage": "echo a",
                    "keyword": [{"type": "success", "word": r"port (?P<port>\d+)"}],
                },
                {
                    "name": "b",
                    "usage": "echo b",
                    "keyword": [{"type": "success", "word": r"(?P<port>\w+) ok"}],
                },
            ]
        },
    )
    rc, out = run_deploy(wd)
    if rc == 0:
        raise AssertionError(f"期望非零 exit, 实际 0\n{out}")
    assert_in("命名组冲突", out)
    return f"rc={rc}"


# ════════════════════════════════════════════════════════════
# T4 · 引用不存在的 cont_ref
# ════════════════════════════════════════════════════════════
@case("T4 · #task 指向不存在的 cont_ref")
def t4(wd):
    write_manifest(
        wd,
        {
            "tasks": [
                {"name": "a", "usage": "echo a"},
                {"name": "#nonexistent", "keyword": [{"type": "success", "word": "."}]},
            ]
        },
    )
    rc, out = run_deploy(wd)
    if rc == 0:
        raise AssertionError(f"期望非零 exit\n{out}")
    assert_in("cont_ref", out)
    assert_in("nonexistent", out)
    return f"rc={rc}"


# ════════════════════════════════════════════════════════════
# T5 · 死锁：depends 永远等不到 → 被标记 skip
# ════════════════════════════════════════════════════════════
@case("T5 · 依赖永远不触发的 cont_ref → skip")
def t5(wd):
    write_manifest(
        wd,
        {
            "tasks": [
                {
                    "name": "silent",
                    "order": 1,
                    "usage": "echo hello && sleep 0.2",
                    "keyword": [
                        {
                            "type": "success",
                            "cont_ref": "never",
                            "word": r"NEVER_MATCHES_THIS",
                        }
                    ],
                },
                {
                    "name": "orphan",
                    "order": 2,
                    "depends": "never",
                    "usage": "echo 'SHOULD NOT RUN'",
                },
            ]
        },
    )
    rc, out = run_deploy(wd, timeout=10)
    assert_not_in("SHOULD NOT RUN", out, "orphan 竟然跑了")
    assert_in("orphan", out)
    assert_in("依赖的 cont_ref 未命中", out)
    return f"rc={rc}"


# ════════════════════════════════════════════════════════════
# T6 · 非 cont_ref error 命中 → 共享进程被杀 → #task 也 finalize
# ════════════════════════════════════════════════════════════
@case("T6 · non-cont_ref error 会终止共享进程")
def t6(wd):
    write_exec(
        wd / "server.sh",
        """#!/bin/bash
echo "listening on port 9000"
sleep 0.4
echo "FATAL disk full"
sleep 5
echo "should not appear"
""",
    )
    write_manifest(
        wd,
        {
            "tasks": [
                {
                    "name": "srv",
                    "order": 1,
                    "usage": f"bash {wd}/server.sh",
                    "keyword": [
                        {
                            "type": "success",
                            "cont_ref": "up",
                            "word": r"listening on port \d+",
                        },
                        {"type": "error", "word": r"FATAL"},
                    ],
                },
                {"name": "#up", "keyword": [{"type": "success", "word": r"never"}]},
            ]
        },
    )
    rc, out = run_deploy(wd, timeout=10)
    assert_in("srv", out)
    assert_in("#up", out)
    assert_not_in("should not appear", out, "进程没被 terminate")
    return f"rc={rc}"


# ════════════════════════════════════════════════════════════
# T7 · 快速连续输出 · #task 启动晚但能追上积压
# ════════════════════════════════════════════════════════════
@case("T7 · 快速连续输出 #task 能 catch up")
def t7(wd):
    # 连续 4 行无 sleep → 几乎同时到达 lines[]
    write_exec(
        wd / "burst.sh",
        """#!/bin/bash
echo "listening on port 7777"
echo "request served: /a"
echo "request served: /b"
echo "request served: /c"
sleep 1.0
exit 0
""",
    )
    write_manifest(
        wd,
        {
            "tasks": [
                {
                    "name": "srv",
                    "order": 1,
                    "usage": f"bash {wd}/burst.sh",
                    "keyword": [
                        {
                            "type": "success",
                            "cont_ref": "up",
                            "word": r"listening on port \d+",
                        }
                    ],
                },
                {
                    "name": "#up",
                    "keyword": [
                        {
                            "type": "success",
                            "cont_ref": "got3",
                            "word": r"request served: /\w",
                            "times": 3,
                        }
                    ],
                },
                {"name": "done", "depends": "got3", "usage": "echo 'caught backlog'"},
            ]
        },
    )
    rc, out = run_deploy(wd, timeout=10)
    assert_in("caught backlog", out, "#task 没追上快速输出")
    return f"rc={rc}"


# ════════════════════════════════════════════════════════════
# T8 · 无 keyword 纯命令 · 退出码决定
# ════════════════════════════════════════════════════════════
@case("T8 · 无 keyword 纯命令 exit code 决定")
def t8(wd):
    write_manifest(
        wd,
        {
            "tasks": [
                {"name": "ok", "order": 1, "usage": "true"},
                {"name": "bad", "order": 2, "usage": "false"},
            ]
        },
    )
    rc, out = run_deploy(wd)
    assert_in("ok", out)
    assert_in("bad", out)
    if rc == 0:
        raise AssertionError(f"bad 失败了 rc 应非零\n{out}")
    return f"rc={rc}"


# ════════════════════════════════════════════════════════════
# T9 · 重名 task 加载期报错
# ════════════════════════════════════════════════════════════
@case("T9 · 重名 task 加载期报错")
def t9(wd):
    write_manifest(
        wd,
        {
            "tasks": [
                {"name": "dup", "usage": "echo a"},
                {"name": "dup", "usage": "echo b"},
            ]
        },
    )
    rc, out = run_deploy(wd)
    if rc == 0:
        raise AssertionError(f"期望非零\n{out}")
    assert_in("重复", out)
    return f"rc={rc}"


# ════════════════════════════════════════════════════════════
# T10 · error + cont_ref · 不终止 进程 depends 能触发
# ════════════════════════════════════════════════════════════
@case("T10 · error + cont_ref 不 terminate，depends 能捕获")
def t10(wd):
    write_exec(
        wd / "srv.sh",
        """#!/bin/bash
echo "starting"
sleep 0.2
echo "WARN something bad but alive"
sleep 0.4
echo "still kicking"
sleep 0.2
exit 1
""",
    )
    write_manifest(
        wd,
        {
            "tasks": [
                {
                    "name": "srv",
                    "order": 1,
                    "usage": f"bash {wd}/srv.sh",
                    "keyword": [
                        {
                            "type": "error",
                            "cont_ref": "srv_err",
                            "word": r"WARN (?P<msg>.+)",
                        }
                    ],
                },
                {
                    "name": "err-handler",
                    "order": 2,
                    "depends": "srv_err",
                    "usage": "echo 'handling: #{msg}'",
                },
            ]
        },
    )
    rc, out = run_deploy(wd, timeout=10)
    assert_in("handling: something bad but alive", out, "err handler 没拿到 #{msg}")
    return f"rc={rc}"


# ════════════════════════════════════════════════════════════
# T11 · keyword.word 支持 ${var} 静态替换
# ════════════════════════════════════════════════════════════
@case("T11 · keyword.word 支持 ${var} 替换")
def t11(wd):
    write_exec(
        wd / "emit.sh",
        """#!/bin/bash
echo "APP_PROD listening on port 9090"
sleep 0.3
exit 0
""",
    )
    write_manifest(
        wd,
        {
            "variables": {"prefix": "APP_PROD"},
            "tasks": [
                {
                    "name": "srv",
                    "order": 1,
                    "usage": f"bash {wd}/emit.sh",
                    "keyword": [
                        {
                            "type": "success",
                            "cont_ref": "up",
                            "word": r"${prefix} listening on port (?P<port>\d+)",
                        }
                    ],
                },
                {
                    "name": "after",
                    "order": 2,
                    "depends": "up",
                    "usage": "echo 'caught port #{port}'",
                },
            ],
        },
    )
    rc, out = run_deploy(wd)
    assert_in("caught port 9090", out, "keyword 里的 ${prefix} 没替换或提取失败")
    return f"rc={rc}"


# ════════════════════════════════════════════════════════════
# T12 · keyword.word 里的 ${var} 拼错 → 加载期严格报错
# ════════════════════════════════════════════════════════════
@case("T12 · keyword.word 未定义变量严格报错")
def t12(wd):
    write_manifest(
        wd,
        {
            "variables": {"prefix": "APP"},
            "tasks": [
                {
                    "name": "srv",
                    "usage": "echo a",
                    "keyword": [
                        {"type": "success", "word": r"${preffix} oops (?P<x>\d+)"}
                    ],
                }
            ],
        },
    )
    rc, out = run_deploy(wd)
    if rc == 0:
        raise AssertionError(f"期望非零 exit\n{out}")
    assert_in("preffix", out)
    return f"rc={rc}"


# ════════════════════════════════════════════════════════════
# T13 · variables 内部链式引用
# ════════════════════════════════════════════════════════════
@case("T13 · variables 链式展开 a→${b}→${c}")
def t13(wd):
    write_manifest(
        wd,
        {
            "variables": {
                "base": "/tmp",
                "sub": "${base}/deploy",
                "full": "${sub}/demo-v1",
            },
            "tasks": [
                {
                    "name": "show",
                    "usage": "echo 'resolved to: ${full}'",
                }
            ],
        },
    )
    rc, out = run_deploy(wd)
    assert_in("resolved to: /tmp/deploy/demo-v1", out, "链式展开失败")
    assert_in("${full} = /tmp/deploy/demo-v1", out, "variables 打印没展开")
    return f"rc={rc}"


# ════════════════════════════════════════════════════════════
# T14 · variables 循环引用 → 加载期报错
# ════════════════════════════════════════════════════════════
@case("T14 · variables 循环引用检测")
def t14(wd):
    write_manifest(
        wd,
        {
            "variables": {
                "a": "${b}_x",
                "b": "${a}_y",
            },
            "tasks": [{"name": "t", "usage": "echo hi"}],
        },
    )
    rc, out = run_deploy(wd)
    if rc == 0:
        raise AssertionError(f"期望非零 exit\n{out}")
    assert_in("循环引用", out)
    return f"rc={rc}"


# ════════════════════════════════════════════════════════════
# T15 · 一次 match 提取多个命名组
# ════════════════════════════════════════════════════════════
@case("T15 · 一次 match 提取多个命名组")
def t15(wd):
    write_exec(
        wd / "srv.sh",
        """#!/bin/bash
echo "bound to 127.0.0.1:8080 for service api-v1"
sleep 0.3
exit 0
""",
    )
    write_manifest(
        wd,
        {
            "tasks": [
                {
                    "name": "srv",
                    "order": 1,
                    "usage": f"bash {wd}/srv.sh",
                    "keyword": [
                        {
                            "type": "success",
                            "cont_ref": "bound",
                            "word": (
                                r"bound to (?P<host>\S+):(?P<port>\d+) "
                                r"for service (?P<svc>\S+)"
                            ),
                        }
                    ],
                },
                {
                    "name": "verify",
                    "order": 2,
                    "depends": "bound",
                    "usage": "echo 'host=#{host} port=#{port} svc=#{svc}'",
                },
            ]
        },
    )
    rc, out = run_deploy(wd)
    assert_in("host=127.0.0.1 port=8080 svc=api-v1", out, "多命名组提取失败")
    # 总结里三个命名组都该出现
    assert_in("#{host} = 127.0.0.1", out)
    assert_in("#{port} = 8080", out)
    assert_in("#{svc} = api-v1", out)
    return f"rc={rc}"


# ════════════════════════════════════════════════════════════
# T16 · 三级 cont_ref 链式挂载 (srv → #s1 → #s2 → final)
# ════════════════════════════════════════════════════════════
@case("T16 · 三级 cont_ref 链式挂载")
def t16(wd):
    write_exec(
        wd / "multi.sh",
        """#!/bin/bash
echo "stage 1 ready"
sleep 0.2
echo "stage 2 ready"
sleep 0.2
echo "stage 3 ready"
sleep 0.3
exit 0
""",
    )
    write_manifest(
        wd,
        {
            "tasks": [
                {
                    "name": "srv",
                    "order": 1,
                    "usage": f"bash {wd}/multi.sh",
                    "keyword": [
                        {"type": "success", "cont_ref": "s1", "word": r"stage 1 ready"}
                    ],
                },
                {
                    "name": "#s1",
                    "keyword": [
                        {"type": "success", "cont_ref": "s2", "word": r"stage 2 ready"}
                    ],
                },
                {
                    "name": "#s2",
                    "keyword": [
                        {"type": "success", "cont_ref": "s3", "word": r"stage 3 ready"}
                    ],
                },
                {
                    "name": "final",
                    "depends": "s3",
                    "usage": "echo 'all three stages done'",
                },
            ]
        },
    )
    rc, out = run_deploy(wd)
    assert_in("all three stages done", out, "三级链没推到末端")
    return f"rc={rc}"


# ════════════════════════════════════════════════════════════
# T17 · copy phase 真的把 src → dest 落盘 + ${var} 替换路径
# ════════════════════════════════════════════════════════════
@case("T17 · copy phase 复制 src→dest + ${var}")
def t17(wd):
    (wd / "src_d").mkdir()
    (wd / "src_d" / "config.txt").write_text("hello from src\n")

    write_manifest(
        wd,
        {
            "variables": {
                "src_dir": str(wd / "src_d"),
                "dest_dir": str(wd / "out"),
            },
            "tasks": [
                {
                    "name": "copy-it",
                    "order": 1,
                    "src": "${src_dir}/config.txt",
                    "dest": "${dest_dir}/config.txt",
                    "usage": "cat ${dest_dir}/config.txt",
                }
            ],
        },
    )
    rc, out = run_deploy(wd)
    assert_in("已复制", out, "copy phase 没汇报成功")
    assert_in("hello from src", out, "cat 没读到复制后的内容")
    if not (wd / "out" / "config.txt").exists():
        raise AssertionError(f"dest 没真正创建\n{out}")
    return f"rc={rc}"


# ════════════════════════════════════════════════════════════
# T18 · 同 order 无 depends 的 task 会并行启动
# ════════════════════════════════════════════════════════════
@case("T18 · 同 order 的 task 并行触发")
def t18(wd):
    # 两个脚本各记录自己的启动时刻 + 睡 0.6s + 记录结束时刻
    # 如果是串行，b.start - a.start 会 >= 0.6s；并行则接近 0
    write_exec(
        wd / "a.sh",
        """#!/bin/bash
date +%s.%N > a.start
sleep 0.6
echo "a done"
""",
    )
    write_exec(
        wd / "b.sh",
        """#!/bin/bash
date +%s.%N > b.start
sleep 0.6
echo "b done"
""",
    )
    write_manifest(
        wd,
        {
            "tasks": [
                {
                    "name": "a",
                    "order": 1,
                    "usage": f"bash {wd}/a.sh",
                    "cwd": str(wd),
                },
                {
                    "name": "b",
                    "order": 1,
                    "usage": f"bash {wd}/b.sh",
                    "cwd": str(wd),
                },
            ]
        },
    )
    rc, out = run_deploy(wd, timeout=10)
    assert_in("a done", out)
    assert_in("b done", out)
    a_start = float((wd / "a.start").read_text())
    b_start = float((wd / "b.start").read_text())
    delta = abs(a_start - b_start)
    # 并行应该 < 100ms（实际通常几十 ms），远小于 sleep 0.6
    if delta > 0.3:
        raise AssertionError(f"启动间隔 {delta * 1000:.0f}ms，看着不像并行\n{out}")
    return f"rc={rc}, a/b 启动间隔 {delta * 1000:.0f}ms"


# ════════════════════════════════════════════════════════════
# T19 · cont_ref 重名应该加载期报错
# ════════════════════════════════════════════════════════════
@case("T19 · cont_ref 重名加载期报错")
def t19(wd):
    write_manifest(
        wd,
        {
            "tasks": [
                {
                    "name": "a",
                    "order": 1,
                    "usage": "echo a",
                    "keyword": [{"type": "success", "cont_ref": "ready", "word": r"a"}],
                },
                {
                    "name": "b",
                    "order": 1,
                    "usage": "echo b",
                    "keyword": [{"type": "success", "cont_ref": "ready", "word": r"b"}],
                },
            ]
        },
    )
    rc, out = run_deploy(wd)
    if rc == 0:
        raise AssertionError(f"期望非零 exit, 实际 0\n{out}")
    assert_in("cont_ref", out)
    assert_in("ready", out)
    return f"rc={rc}"


# ════════════════════════════════════════════════════════════
# T20 · order 支持小数（方便中间插入新节点不用整体挪号）
# ════════════════════════════════════════════════════════════
@case("T20 · order 支持小数并正确排序")
def t20(wd):
    write_manifest(
        wd,
        {
            "tasks": [
                {"name": "first", "order": 1, "usage": "echo first"},
                {"name": "inserted", "order": 1.5, "usage": "echo inserted"},
                {"name": "second", "order": 2, "usage": "echo second"},
            ]
        },
    )
    rc, out = run_deploy(wd)
    assert_in("▶ [order=1] first", out)
    assert_in("▶ [order=1.5] inserted", out)
    assert_in("▶ [order=2] second", out)
    # 三个 header 的位置应当按 order 递增
    p_first = out.find("▶ [order=1] first")
    p_inserted = out.find("▶ [order=1.5] inserted")
    p_second = out.find("▶ [order=2] second")
    if not (p_first < p_inserted < p_second):
        raise AssertionError(
            f"order 排序错乱: first={p_first} inserted={p_inserted} second={p_second}"
        )
    return f"rc={rc}"


# ════════════════════════════════════════════════════════════
# T22 · order 不同的独立 task 按 wave 串行（1 跑完再跑 2）
# ════════════════════════════════════════════════════════════
@case("T22 · 不同 order 的独立 task 按 wave 串行")
def t22(wd):
    write_exec(
        wd / "a.sh",
        """#!/bin/bash
sleep 0.3
date +%s.%N > a.end
echo "a done"
""",
    )
    write_exec(
        wd / "b.sh",
        """#!/bin/bash
date +%s.%N > b.start
echo "b done"
""",
    )
    write_manifest(
        wd,
        {
            "tasks": [
                {
                    "name": "a",
                    "order": 1,
                    "usage": f"bash {wd}/a.sh",
                    "cwd": str(wd),
                },
                {
                    "name": "b",
                    "order": 2,
                    "usage": f"bash {wd}/b.sh",
                    "cwd": str(wd),
                },
            ]
        },
    )
    rc, out = run_deploy(wd, timeout=10)
    assert_in("a done", out)
    assert_in("b done", out)
    a_end = float((wd / "a.end").read_text())
    b_start = float((wd / "b.start").read_text())
    if b_start < a_end:
        raise AssertionError(f"b 在 a 结束前就启动了: a.end={a_end} b.start={b_start}")
    return f"rc={rc}, a→b 串行间隔 {(b_start - a_end) * 1000:.0f}ms"


# ════════════════════════════════════════════════════════════
# T21 · deploy.log 同步写入（纯文本无 ANSI）
# ════════════════════════════════════════════════════════════
@case("T21 · deploy_YYYYMMDD_HHMMSS.log 同步写入")
def t21(wd):
    import glob

    write_manifest(
        wd,
        {"tasks": [{"name": "hi", "order": 1, "usage": "echo hello from log test"}]},
    )
    rc, out = run_deploy(wd)
    # 文件名带时间后缀，用 glob 找
    logs = sorted(glob.glob(str(wd / "deploy_*.log")))
    if not logs:
        raise AssertionError(f"deploy_*.log 未生成\n{out}")
    log_path = Path(logs[-1])
    content = log_path.read_text()
    assert_in("hello from log test", content, "子进程输出未写入 log")
    assert_in("执行总结", content, "总结未写入 log")
    # 验证无 ANSI 转义码
    if "\033[" in content:
        raise AssertionError(f"log 含 ANSI 转义码\n{content[:300]}")
    return f"rc={rc}, {log_path.name} {len(content)} bytes"


# ════════════════════════════════════════════════════════════
# runner
# ════════════════════════════════════════════════════════════


def main():
    print(f"Python: {sys.version.split()[0]}")
    print(f"Deploy: {DEPLOY}")
    print(f"Tests:  {len(tests)}\n")
    passed, failed = 0, 0
    for name, fn in tests:
        with tempfile.TemporaryDirectory(prefix="deploy_test_") as tmp:
            wd = Path(tmp)
            try:
                info = fn(wd)
                print(f"  ✔ {name}")
                if info:
                    print(f"      {info}")
                passed += 1
            except subprocess.TimeoutExpired as e:
                print(f"  ✘ {name}  TIMEOUT")
                if e.stdout:
                    tail = (
                        e.stdout if isinstance(e.stdout, str) else e.stdout.decode()
                    )[-600:]
                    print("      " + tail.replace("\n", "\n      "))
                failed += 1
            except AssertionError as e:
                print(f"  ✘ {name}")
                for line in str(e).split("\n"):
                    print(f"      {line}")
                failed += 1
            except Exception as e:
                print(f"  ✘ {name}  {type(e).__name__}: {e}")
                failed += 1
    print()
    print("═" * 50)
    print(f"  {passed} passed, {failed} failed")
    print("═" * 50)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
