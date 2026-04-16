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
            f"期望 '{needle}' 出现在输出中{(' ('+msg+')') if msg else ''}\n"
            f"─── stdout ───\n{out}\n──────────────"
        )


def assert_not_in(needle: str, out: str, msg: str = ""):
    if needle in out:
        raise AssertionError(
            f"不该出现 '{needle}'{(' ('+msg+')') if msg else ''}\n"
            f"─── stdout ───\n{out}\n──────────────"
        )


# ════════════════════════════════════════════════════════════
# T1 · 两级 cont_ref 链 + 命名组跨任务传递
# ════════════════════════════════════════════════════════════
@case("T1 · happy path 两级链 + 命名组传递")
def t1(wd):
    write_exec(wd / "server.sh", """#!/bin/bash
echo "starting..."
sleep 0.3
echo "listening on port 8080"
sleep 0.3
echo "request served: /hello"
sleep 0.3
echo "shutting down"
exit 0
""")
    write_manifest(wd, {
        "tasks": [
            {
                "name": "start-server",
                "order": 1,
                "usage": f"bash {wd}/server.sh",
                "keyword": [
                    {
                        "type": "success",
                        "cont_ref": "server_up",
                        "word": r"listening on port (?P<port>\d+)"
                    }
                ]
            },
            {
                "name": "call-api",
                "order": 2,
                "depends": "server_up",
                "usage": "echo calling api on port #{port}"
            },
            {
                "name": "#server_up",
                "keyword": [
                    {
                        "type": "success",
                        "cont_ref": "first_req",
                        "word": r"request served: (?P<path>/\S+)"
                    }
                ]
            },
            {
                "name": "log-analyze",
                "order": 3,
                "depends": "first_req",
                "usage": "echo first request path: #{path}"
            }
        ]
    })
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
    write_exec(wd / "emit.sh", """#!/bin/bash
echo "event A"
echo "event B"
sleep 0.3
echo "event C"
sleep 0.3
exit 0
""")
    write_manifest(wd, {
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
                        "times": 3
                    }
                ]
            },
            {
                "name": "after",
                "order": 2,
                "depends": "three",
                "usage": "echo 'three events seen'"
            }
        ]
    })
    rc, out = run_deploy(wd)
    assert_in("three events seen", out, "times=3 没触发")
    return f"rc={rc}"


# ════════════════════════════════════════════════════════════
# T3 · 命名组冲突加载期报错
# ════════════════════════════════════════════════════════════
@case("T3 · 命名组冲突加载期报错")
def t3(wd):
    write_manifest(wd, {
        "tasks": [
            {
                "name": "a",
                "usage": "echo a",
                "keyword": [{"type": "success", "word": r"port (?P<port>\d+)"}]
            },
            {
                "name": "b",
                "usage": "echo b",
                "keyword": [{"type": "success", "word": r"(?P<port>\w+) ok"}]
            }
        ]
    })
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
    write_manifest(wd, {
        "tasks": [
            {"name": "a", "usage": "echo a"},
            {
                "name": "#nonexistent",
                "keyword": [{"type": "success", "word": "."}]
            }
        ]
    })
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
    write_manifest(wd, {
        "tasks": [
            {
                "name": "silent",
                "order": 1,
                "usage": "echo hello && sleep 0.2",
                "keyword": [
                    {
                        "type": "success",
                        "cont_ref": "never",
                        "word": r"NEVER_MATCHES_THIS"
                    }
                ]
            },
            {
                "name": "orphan",
                "order": 2,
                "depends": "never",
                "usage": "echo 'SHOULD NOT RUN'"
            }
        ]
    })
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
    write_exec(wd / "server.sh", """#!/bin/bash
echo "listening on port 9000"
sleep 0.4
echo "FATAL disk full"
sleep 5
echo "should not appear"
""")
    write_manifest(wd, {
        "tasks": [
            {
                "name": "srv",
                "order": 1,
                "usage": f"bash {wd}/server.sh",
                "keyword": [
                    {
                        "type": "success",
                        "cont_ref": "up",
                        "word": r"listening on port \d+"
                    },
                    {
                        "type": "error",
                        "word": r"FATAL"
                    }
                ]
            },
            {
                "name": "#up",
                "keyword": [
                    {"type": "success", "word": r"never"}
                ]
            }
        ]
    })
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
    write_exec(wd / "burst.sh", """#!/bin/bash
echo "listening on port 7777"
echo "request served: /a"
echo "request served: /b"
echo "request served: /c"
sleep 1.0
exit 0
""")
    write_manifest(wd, {
        "tasks": [
            {
                "name": "srv",
                "order": 1,
                "usage": f"bash {wd}/burst.sh",
                "keyword": [
                    {
                        "type": "success",
                        "cont_ref": "up",
                        "word": r"listening on port \d+"
                    }
                ]
            },
            {
                "name": "#up",
                "keyword": [
                    {
                        "type": "success",
                        "cont_ref": "got3",
                        "word": r"request served: /\w",
                        "times": 3
                    }
                ]
            },
            {
                "name": "done",
                "depends": "got3",
                "usage": "echo 'caught backlog'"
            }
        ]
    })
    rc, out = run_deploy(wd, timeout=10)
    assert_in("caught backlog", out, "#task 没追上快速输出")
    return f"rc={rc}"


# ════════════════════════════════════════════════════════════
# T8 · 无 keyword 纯命令 · 退出码决定
# ════════════════════════════════════════════════════════════
@case("T8 · 无 keyword 纯命令 exit code 决定")
def t8(wd):
    write_manifest(wd, {
        "tasks": [
            {"name": "ok",  "order": 1, "usage": "true"},
            {"name": "bad", "order": 2, "usage": "false"}
        ]
    })
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
    write_manifest(wd, {
        "tasks": [
            {"name": "dup", "usage": "echo a"},
            {"name": "dup", "usage": "echo b"}
        ]
    })
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
    write_exec(wd / "srv.sh", """#!/bin/bash
echo "starting"
sleep 0.2
echo "WARN something bad but alive"
sleep 0.4
echo "still kicking"
sleep 0.2
exit 1
""")
    write_manifest(wd, {
        "tasks": [
            {
                "name": "srv",
                "order": 1,
                "usage": f"bash {wd}/srv.sh",
                "keyword": [
                    {
                        "type": "error",
                        "cont_ref": "srv_err",
                        "word": r"WARN (?P<msg>.+)"
                    }
                ]
            },
            {
                "name": "err-handler",
                "order": 2,
                "depends": "srv_err",
                "usage": "echo 'handling: #{msg}'"
            }
        ]
    })
    rc, out = run_deploy(wd, timeout=10)
    assert_in("handling: something bad but alive", out, "err handler 没拿到 #{msg}")
    return f"rc={rc}"


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
                    tail = (e.stdout if isinstance(e.stdout, str) else e.stdout.decode())[-600:]
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
