#!/usr/bin/env python3
"""
配置文件分发 + keyword 流水线调度

根据 manifest.json 按依赖关系调度 tasks：
- 每个 task 起一个 subprocess，读 stdout 匹配 keyword
- keyword 支持 type(error/success)、cont_ref(命中后不杀进程)、
  命名组提取 (#{group} 全局可引用)、times(N 次命中才算一次)
- depends: <cont_ref>  → 等 cont_ref 命中后并行启动新 subprocess
- name: "#<cont_ref>"   → 挂载到 cont_ref 原进程的 stdout 继续监听
- cont_ref 命中的进程会继续存活，PID 写 .deploy.state；下次启动先 kill

用法:
    python deploy.py                                  # 部署 + 调度
    python deploy.py -y                               # 覆盖确认全部自动 y
    python deploy.py --appid=123 --env=prod           # CLI 覆盖 manifest 变量
    python deploy.py --manifest=path/x.json           # 指定其它 manifest 路径（默认 manifest.json）
    python deploy.py --vars-file=path/vars.json       # 从 JSON 文件批量加载公共变量
    python deploy.py -h                               # 帮助

变量优先级（低→高覆盖）:
    manifest.variables  <  --vars-file  <  --key=value CLI 显式

首次使用: cp manifest.json.example manifest.json && vim manifest.json
"""

from __future__ import annotations

import os
import sys

# ── 究极编码方案：强制 Python UTF-8 模式 ──────────────────
# PYTHONUTF8=1 让 open()/print()/Popen(text=True)/所有 IO 全部默认 UTF-8，
# 但该变量必须在解释器启动时生效（运行时 os.environ 设了没用）。
# 所以：检测到未启用时，设好变量 → os.execv 重新启动自身（同进程替换）。
# 第二次进来时 PYTHONUTF8=1 已生效，跳过此块正常执行。
if os.environ.get("PYTHONUTF8") != "1":
    os.environ["PYTHONUTF8"] = "1"
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")  # 兼容更老的 Python 子进程
    os.execv(sys.executable, [sys.executable] + sys.argv)
# ──────────────────────────────────────────────────────────

import filecmp
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Callable, Optional

EXAMPLE_FILE = "manifest.json.example"
STATE_FILE = ".deploy.state"
_AUTO_YES = False  # -y/--yes 模式：覆盖确认全部自动 y

# 变量替换策略：
# - manifest.variables 内部相互引用用宽松模式，允许分轮展开
# - 其他所有字符串字段（tasks / readme / ...）用 strict：拼错立刻炸
# - shell 变量（$HOME 等）请用无括号形式，不走模板引擎
VAR_RE = re.compile(r"\$\{(\w+)\}")
DYN_RE = re.compile(r"#\{(\w+)\}")


# ══════════════════════════════════════════════
# 日志辅助：时间戳 + ANSI 颜色 + 线程安全
# ══════════════════════════════════════════════

_USE_COLOR = sys.stdout.isatty()
_PRINT_LOCK = threading.Lock()
_LOG_FILE = None  # 运行期由 _open_log 打开，deploy.log 纯文本（无 ANSI）


def _c(code: str) -> str:
    return code if _USE_COLOR else ""


DIM = _c("\033[2m")
RESET = _c("\033[0m")
RED = _c("\033[31m")
GREEN = _c("\033[32m")
YELLOW = _c("\033[33m")
CYAN = _c("\033[36m")
BOLD = _c("\033[1m")

_STYLE = {
    "dim": DIM,
    "ok": GREEN,
    "warn": YELLOW,
    "err": RED + BOLD,
    "hit": CYAN + BOLD,
    "section": BOLD,
}


def _ts() -> str:
    t = time.time()
    ms = int((t - int(t)) * 1000)
    return time.strftime("%H:%M:%S") + f".{ms:03d}"


def log(msg: str, style: str = "") -> None:
    """带时间戳前缀的线程安全输出。终端带颜色，deploy.log 纯文本。"""
    color = _STYLE.get(style, "")
    ts = _ts()
    with _PRINT_LOCK:
        line = f"{DIM}{ts}{RESET} {color}{msg}{RESET}\n"
        sys.stdout.buffer.write(line.encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()
        if _LOG_FILE:
            _LOG_FILE.write(f"{ts} {msg}\n".encode("utf-8", errors="replace"))
            _LOG_FILE.flush()


def br() -> None:
    """空行分隔，无时间戳。"""
    with _PRINT_LOCK:
        sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()
        if _LOG_FILE:
            _LOG_FILE.write(b"\n")


def _open_log(path: str) -> None:
    global _LOG_FILE
    _LOG_FILE = open(path, "wb")  # 二进制模式，write 时自己 encode
    _LOG_FILE.write("── 日志开始记录 ──\n".encode("utf-8"))
    _LOG_FILE.flush()


def _close_log() -> None:
    global _LOG_FILE
    if _LOG_FILE:
        _LOG_FILE.close()
        _LOG_FILE = None


# ══════════════════════════════════════════════
# 公共小工具
# ══════════════════════════════════════════════


def _killpg_safe(pgid: int, sig: int) -> None:
    """killpg 并吞掉 ProcessLookupError/PermissionError。"""
    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def _expand_vars(text: str, variables: dict, strict: bool) -> str:
    """把 text 里的 ${key} 用 variables[key] 替换。

    strict=True  未定义的 key 直接抛 ValueError
    strict=False 未定义的 key 原样保留（用于变量内部相互引用的分轮展开）
    """

    def _sub(m: re.Match) -> str:
        key = m.group(1)
        if key in variables:
            return variables[key]
        if strict:
            raise ValueError(f"未定义的变量: ${{{key}}}")
        return m.group(0)

    return VAR_RE.sub(_sub, text)


def _expand_all(node, variables: dict):
    """递归把任意 JSON-like 结构里的所有字符串都走一遍 ${var} 替换。
    未定义变量立即抛错（strict）。"""
    if isinstance(node, str):
        return _expand_vars(node, variables, strict=True)
    if isinstance(node, dict):
        return {k: _expand_all(v, variables) for k, v in node.items()}
    if isinstance(node, list):
        return [_expand_all(item, variables) for item in node]
    return node


def _task_order(task: dict) -> float:
    return task.get("order", float("inf"))


def _compute_cwd(task: dict, ctx: "Context") -> Optional[str]:
    """优先用 task.cwd，其次回退到 dirname(dest)。动态 #{var} 替换留到运行时。"""
    raw = task.get("cwd") or os.path.dirname(task.get("dest", "")) or None
    return ctx.substitute(raw)


# ══════════════════════════════════════════════
# 加载 · 变量替换 · 校验
# ══════════════════════════════════════════════


def load_manifest(path: str) -> dict:
    if not os.path.exists(path):
        if os.path.exists(EXAMPLE_FILE):
            log(f"  ✘ 未找到 {path}", style="err")
            log(f"  💡 请先执行: cp {EXAMPLE_FILE} {path}", style="dim")
        raise FileNotFoundError(f"清单文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    # 重名校验：dict 查找会让后者覆盖前者，静默吞掉问题
    names = [t["name"] for t in manifest.get("tasks", []) if "name" in t]
    dups = sorted({n for n in names if names.count(n) > 1})
    if dups:
        raise ValueError(f"任务名重复: {', '.join(dups)}")
    return manifest


def resolve_variables(manifest: dict) -> dict:
    """静态 ${var} 替换。所有非 variables 字段里的字符串都统一 strict 替换。

    shell 变量（$HOME 等）请用无括号形式，不会被模板引擎拦截。
    """
    variables = manifest.get("variables", {})
    # 先把 variables 内部相互引用展开到不动点（宽松模式，允许分轮）
    for _ in range(10):
        changed = False
        for k, v in variables.items():
            if not isinstance(v, str) or "${" not in v:
                continue
            new_v = _expand_vars(v, variables, strict=False)
            if new_v != v:
                variables[k] = new_v
                changed = True
        if not changed:
            break
    for k, v in variables.items():
        if isinstance(v, str) and "${" in v:
            raise ValueError(f"变量循环引用或未定义: {k} = {v}")

    # 再对 manifest 其他部分做统一递归替换（strict：拼错立即炸）
    for key in list(manifest.keys()):
        if key == "variables":
            continue
        manifest[key] = _expand_all(manifest[key], variables)
    return manifest


def validate(manifest: dict) -> None:
    """加载期校验：命名组冲突、cont_ref 重名、cont_ref 引用完整。"""
    seen_groups: dict[str, tuple[str, int]] = {}  # group_name -> (task, kw_index)
    declared_refs: dict[str, tuple[str, int]] = {}  # cont_ref -> (task, kw_index)
    referenced_refs: set[str] = set()  # 被 depends / #task 引用的

    for task in manifest.get("tasks", []):
        tname = task["name"]
        for i, kw in enumerate(task.get("keyword", [])):
            if "word" not in kw:
                raise ValueError(f"[{tname}] keyword[{i}] 缺少 word 字段")
            try:
                pat = re.compile(kw["word"])
            except re.error as e:
                raise ValueError(f"[{tname}] keyword[{i}] 正则无效: {e}")
            for gname in pat.groupindex:
                if gname in seen_groups:
                    prev_t, prev_i = seen_groups[gname]
                    raise ValueError(
                        f"命名组冲突: #{{{gname}}} 同时定义在 "
                        f"[{prev_t}].keyword[{prev_i}] 和 [{tname}].keyword[{i}]"
                    )
                seen_groups[gname] = (tname, i)
            ref = kw.get("cont_ref")
            if ref:
                if ref in declared_refs:
                    prev_t, prev_i = declared_refs[ref]
                    raise ValueError(
                        f"cont_ref 重名: '{ref}' 同时声明于 "
                        f"[{prev_t}].keyword[{prev_i}] 和 [{tname}].keyword[{i}]"
                    )
                declared_refs[ref] = (tname, i)
            kw_type = kw.get("type", "success")
            if kw_type not in ("error", "success"):
                raise ValueError(f"[{tname}] keyword[{i}] type 只能是 error/success")
        if tname.startswith("#"):
            referenced_refs.add(tname[1:])
        if task.get("depends"):
            referenced_refs.add(task["depends"])

    missing = referenced_refs - declared_refs.keys()
    if missing:
        raise ValueError(f"引用的 cont_ref 未定义: {', '.join(sorted(missing))}")


# ══════════════════════════════════════════════
# Context · EventBus
# ══════════════════════════════════════════════


class Context:
    """全局 #{name} → value。first-write-wins（但 validate 已保证不会冲突）。"""

    def __init__(self):
        self._d: dict[str, str] = {}
        self._lock = threading.Lock()

    def set_if_absent(self, name: str, value: str) -> None:
        with self._lock:
            if name not in self._d:
                self._d[name] = value

    def substitute(self, text: Optional[str]) -> Optional[str]:
        if not text or "#{" not in text:
            return text
        return DYN_RE.sub(lambda m: self._d.get(m.group(1), m.group(0)), text)

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._d)


class EventBus:
    """cont_ref 命中广播。一个 ref 只触发一次，记录命中时的 cursor 位置。"""

    def __init__(self):
        self._fired: dict[str, tuple[int, "ProcessStream"]] = {}
        self._cond = threading.Condition()

    def fire(self, ref: str, cursor: int, stream: "ProcessStream") -> None:
        with self._cond:
            if ref in self._fired:
                return
            self._fired[ref] = (cursor, stream)
            self._cond.notify_all()

    def wait(self, ref: str) -> tuple[int, "ProcessStream"]:
        with self._cond:
            while ref not in self._fired:
                self._cond.wait()
            return self._fired[ref]

    def fired(self, ref: str) -> bool:
        with self._cond:
            return ref in self._fired


# ══════════════════════════════════════════════
# ProcessStream: 包装 subprocess + append-only 行缓冲 + 共享 reader
# ══════════════════════════════════════════════


class ProcessStream:
    """一个 subprocess 一个 stream，多个 Watcher 各自用 cursor 从 lines 数组读。
    reader 线程负责把 stdout 拉进数组并回显到终端。"""

    def __init__(self, cmd: str, cwd: Optional[str], task_name: str):
        # shell 命令头部注入 UTF-8 环境变量，确保 && / | 后面的 python 也继承
        utf8 = "export PYTHONUTF8=1; export PYTHONIOENCODING=utf-8; "
        stdbuf_bin = shutil.which("stdbuf") or shutil.which("gstdbuf")
        real_cmd = f"{stdbuf_bin} -oL -eL {cmd}" if stdbuf_bin else cmd
        real_cmd = utf8 + real_cmd

        self.cmd = cmd
        self.task_name = task_name
        self.proc = subprocess.Popen(
            real_cmd,
            shell=True,
            cwd=cwd or None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self.pid = self.proc.pid
        try:
            self.pgid = os.getpgid(self.pid)
        except ProcessLookupError:
            self.pgid = self.pid
        self.lines: list[str] = []
        self._cond = threading.Condition()
        self.closed = False
        self.detached = False
        # 区分两种 terminate：
        # - watcher 自己命中 keyword 后调 terminate() = self-terminate（视为正常 verdict）
        # - Scheduler._terminate_all 触发的 = force-terminate（视为被中断，标 skip 不是 fail）
        self.force_terminated = False
        self._reader = threading.Thread(
            target=self._read, daemon=True, name=f"reader-{task_name}"
        )
        self._reader.start()

    def _read(self) -> None:
        try:
            assert self.proc.stdout is not None
            for raw in self.proc.stdout:
                # 原始字节 → UTF-8 decode（非法字节变 ?），剥掉换行
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                with self._cond:
                    self.lines.append(line)
                    self._cond.notify_all()
                log(f"    │ [{self.task_name}] {line}", style="dim")
        except Exception:
            pass
        finally:
            self.proc.wait()
            with self._cond:
                self.closed = True
                self._cond.notify_all()

    def read_from(self, cursor: int) -> tuple[Optional[str], int]:
        """阻塞读 cursor 位置下一行；流关闭且无更多行 → 返回 (None, cursor)。"""
        with self._cond:
            while cursor >= len(self.lines) and not self.closed:
                self._cond.wait(timeout=0.5)
            if cursor < len(self.lines):
                return self.lines[cursor], cursor + 1
            return None, cursor

    def terminate(self) -> None:
        if self.proc.poll() is not None:
            return
        _killpg_safe(self.pgid, signal.SIGTERM)
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _killpg_safe(self.pgid, signal.SIGKILL)

    def detach(self) -> None:
        self.detached = True


# ══════════════════════════════════════════════
# Watcher: 扫 buffer 匹配 keyword
# ══════════════════════════════════════════════


@dataclass
class KeywordState:
    spec: dict
    pattern: "re.Pattern[str]" = field(init=False)
    hit_count: int = 0
    consumed: bool = False
    times: int = field(init=False)

    def __post_init__(self):
        self.pattern = re.compile(self.spec["word"])
        self.times = int(self.spec.get("times", 1))


class Watcher(threading.Thread):
    """一个 task 一个 Watcher，从 stream 的 start_cursor 开始扫 keyword。

    - cont_ref 命中：提取组 + 广播 + detach，不 seal verdict，继续扫其他 keyword
    - 非 cont_ref 命中：terminate + seal verdict 结束
    - stream 关闭：按事件历史 + exit code 决定最终 verdict
    """

    def __init__(
        self,
        task: dict,
        stream: ProcessStream,
        start_cursor: int,
        ctx: Context,
        bus: EventBus,
        on_verdict: Callable[["Watcher"], None],
    ):
        super().__init__(daemon=True, name=f"watcher-{task['name']}")
        self.task = task
        self.stream = stream
        self.cursor = start_cursor
        self.ctx = ctx
        self.bus = bus
        self.on_verdict = on_verdict
        self.keywords = [KeywordState(k) for k in task.get("keyword", [])]
        self.verdict: Optional[str] = None  # "success" | "fail"
        self.reason: str = ""
        self.events: list[str] = []  # 所有命中记录
        self.cont_ref_fired = False  # 有 cont_ref 命中后不再阻塞 wave 推进

    def run(self) -> None:
        try:
            while self.verdict is None:
                line, new_cursor = self.stream.read_from(self.cursor)
                if line is None:
                    self._finalize_on_close()
                    break
                self.cursor = new_cursor
                self._scan(line)
        except Exception as e:
            log(f"    ✘ [{self.task['name']}] watcher 异常: {e}", style="err")
            log(traceback.format_exc().rstrip(), style="dim")
            self._seal("fail", f"watcher 异常: {e}")

    def _scan(self, line: str) -> None:
        """逐 keyword 扫一行；完整命中则分派到 _handle_hit。"""
        for idx, ks in enumerate(self.keywords):
            if ks.consumed:
                continue
            m = ks.pattern.search(line)
            if m is None:
                continue
            ks.hit_count += 1
            if ks.hit_count < ks.times:
                if ks.times > 1:
                    log(
                        f"    ⚡ [{self.task['name']}] keyword#{idx} "
                        f"命中进度 {ks.hit_count}/{ks.times}",
                        style="dim",
                    )
                return
            ks.consumed = True
            if self._handle_hit(idx, ks, m):
                return  # verdict 已 seal，停止本行扫描

    def _handle_hit(self, idx: int, ks: KeywordState, m: re.Match) -> bool:
        """处理一次完整命中。返回 True 表示已 seal verdict 应停止扫描。"""
        name = self.task["name"]
        # 提取命名组 → 全局
        groups = {k: v for k, v in m.groupdict().items() if v is not None}
        for gname, gval in groups.items():
            self.ctx.set_if_absent(gname, gval)

        kw_type = ks.spec.get("type", "success")
        cont_ref = ks.spec.get("cont_ref")

        # 记录事件 + 打印命中行
        tag = f"{kw_type}→{cont_ref}" if cont_ref else kw_type
        self.events.append(tag)
        if cont_ref:
            log(
                f"    ⚡ [{name}] keyword#{idx} 命中 → cont_ref={cont_ref} ({kw_type})",
                style="hit",
            )
        else:
            log(
                f"    ⚡ [{name}] keyword#{idx} 命中 → {kw_type}（终止进程）",
                style="hit",
            )
        log(f"      matched: {m.group(0)!r}", style="dim")
        if groups:
            gs = ", ".join(f"{k}={v}" for k, v in groups.items())
            log(f"      groups:  {gs}", style="dim")

        # 分派
        if cont_ref:
            self.cont_ref_fired = True
            self.stream.detach()
            self.bus.fire(cont_ref, self.cursor, self.stream)
            return False  # 不 seal，继续扫后续 keyword
        self.stream.terminate()
        verdict = "fail" if kw_type == "error" else "success"
        self._seal(verdict, f"keyword#{idx}({kw_type}) matched")
        return True

    def _finalize_on_close(self) -> None:
        if self.verdict is not None:
            return
        # 被外部强杀（fail-fast / Ctrl+C） → skip，不是 fail
        if self.stream.force_terminated:
            self._seal("skip", "被外部中断（fail-fast / 用户中止）")
            return
        rc = self.stream.proc.returncode
        had_error = any(e.startswith("error") for e in self.events)
        had_success = any(e.startswith("success") for e in self.events)
        if had_error:
            self._seal("fail", "流关闭, 曾命中 error 事件")
        elif had_success:
            self._seal("success", "流关闭, 曾命中 success 事件")
        elif rc == 0:
            self._seal("success", "exit 0, 无 keyword 命中")
        else:
            self._seal("fail", f"exit {rc}, 无 keyword 命中")

    def _seal(self, verdict: str, reason: str) -> None:
        if self.verdict is not None:
            return
        self.verdict = verdict
        self.reason = reason
        self.on_verdict(self)


# ══════════════════════════════════════════════
# State file: 跨运行的 PID 追踪
# ══════════════════════════════════════════════


def state_cleanup(state_path: str) -> None:
    """Kill 上次运行留下的常驻进程。"""
    if not os.path.exists(state_path):
        return
    try:
        with open(state_path, encoding="utf-8") as f:
            entries = json.load(f)
    except Exception:
        os.remove(state_path)
        return
    if not entries:
        os.remove(state_path)
        return

    log(f"  ℹ 清理上次留下的 {len(entries)} 个常驻进程", style="dim")
    for e in entries:
        log(f"     ─ pid={e.get('pid')} task={e.get('task', '?')}", style="dim")

    pgids = [e.get("pgid") or e.get("pid") for e in entries]
    for pgid in pgids:
        _killpg_safe(pgid, signal.SIGTERM)
    time.sleep(0.5)
    for pgid in pgids:
        _killpg_safe(pgid, signal.SIGKILL)
    os.remove(state_path)


def state_write(state_path: str, entries: list) -> None:
    if not entries:
        return
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


# ══════════════════════════════════════════════
# 复制阶段
# ══════════════════════════════════════════════


def atomic_copy(src: str, dest: str) -> None:
    tmp = dest + ".tmp"
    shutil.copy2(src, tmp)
    os.replace(tmp, dest)


def _prompt_overwrite(name: str, auto_yes: bool) -> bool:
    log(f"  ⚠ [{name}] dest 与 src 不一致", style="warn")
    if auto_yes:
        log("    ✔ 自动确认覆盖", style="dim")
        return True
    try:
        return input("    覆盖? (y/n): ").strip().lower() == "y"
    except EOFError:
        return False


# ══════════════════════════════════════════════
# Scheduler: DAG 调度 + Watcher 线程池
# ══════════════════════════════════════════════


class Scheduler:
    """按 order/depends 推进 task，管理 Watcher 线程池和共享状态。"""

    def __init__(self, tasks: list, statuses: dict, ctx: Context, bus: EventBus):
        self.tasks = tasks
        self.statuses = statuses
        self.ctx = ctx
        self.bus = bus
        self.watchers: list[Watcher] = []
        self._watcher_lock = threading.Lock()
        self._verdict_cond = threading.Condition()
        self._fail_fast = False  # 任一无 cont_ref 的 task 失败 → 触发，停止启动新 task
        # 初始 pending：有 usage / src / #task 的
        runnable = [
            t
            for t in tasks
            if t.get("usage") or t.get("src") or t["name"].startswith("#")
        ]
        runnable.sort(key=_task_order)
        self._pending: list[dict] = runnable

    # ──────────── 回调 & 基础操作 ────────────

    def _on_verdict(self, w: Watcher) -> None:
        self.statuses[w.task["name"]] = (w.verdict or "fail", w.reason)
        # fail-fast：某 task 失败立即终止所有任务
        # 例外：定义了 cont_ref 的 task（长跑服务）失败不拖死 pipeline
        if w.verdict == "fail" and not self._fail_fast:
            has_cont_ref = any(
                "cont_ref" in kw for kw in w.task.get("keyword", [])
            )
            if not has_cont_ref:
                self._fail_fast = True
                log(
                    f"  ⏹ fail-fast 触发: [{w.task['name']}] 失败，终止所有任务",
                    style="err",
                )
                self._terminate_all()
        with self._verdict_cond:
            self._verdict_cond.notify_all()

    def _header(self, task: dict) -> None:
        note = task.get("note", "")
        order = task.get("order", "-")
        br()
        log(f"  ▶ [order={order}] {note or task['name']}")

    def _launch(self, task: dict, stream: ProcessStream, cursor: int) -> None:
        w = Watcher(task, stream, cursor, self.ctx, self.bus, self._on_verdict)
        with self._watcher_lock:
            self.watchers.append(w)
        w.start()

    # ──────────── per-task 复制 ────────────

    def _copy_for_task(self, task: dict) -> bool:
        """启动前复制 src→dest（如果配了的话）。返回 False 表示复制失败。"""
        name = task["name"]
        src = task.get("src")
        dest = task.get("dest")
        if not src or not dest:
            return True
        if not os.path.exists(src):
            # 源路径缺失是配置错误，不是运行时失败 → 中断整个流水线
            raise ValueError(f"[{name}] 源路径不存在: {src}")
        # global (-y 或 manifest.auto_yes) 或 per-task auto_yes 任一为真即自动 yes
        effective_yes = _AUTO_YES or bool(task.get("auto_yes"))
        # 类型冲突检查：src/dest 必须同类型
        if os.path.exists(dest):
            if os.path.isdir(src) and not os.path.isdir(dest):
                log(f"    ✘ 类型冲突: src 是目录但 dest 是文件 ({dest})", style="err")
                self.statuses[name] = ("fail", "type mismatch: dir src vs file dest")
                return False
            if not os.path.isdir(src) and os.path.isdir(dest):
                log(f"    ✘ 类型冲突: src 是文件但 dest 是目录 ({dest})", style="err")
                self.statuses[name] = ("fail", "type mismatch: file src vs dir dest")
                return False
        if os.path.isdir(src):
            return self._copy_dir(name, src, dest, effective_yes)
        return self._copy_file(name, src, dest, effective_yes)

    def _copy_file(self, name: str, src: str, dest: str, task_yes: bool) -> bool:
        dest_dir = os.path.dirname(dest)
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)
        if not os.path.exists(dest):
            atomic_copy(src, dest)
            log(f"    ✔ 已复制 {src}", style="dim")
            return True
        if filecmp.cmp(src, dest, shallow=False):
            log("    ✔ 内容一致，跳过复制", style="dim")
            return True
        if not _prompt_overwrite(name, task_yes):
            log("    ⏭ 跳过覆盖", style="dim")
            return True
        atomic_copy(src, dest)
        log(f"    ✔ 已覆盖 {src}", style="dim")
        return True

    def _copy_dir(self, name: str, src: str, dest: str, auto_yes: bool) -> bool:
        # 目录直接合并覆盖，不 prompt；dest 已存在时用 warn 提醒
        if os.path.exists(dest):
            log(f"    ⚠ dest 目录已存在，执行合并覆盖: {dest}", style="warn")
            shutil.copytree(src, dest, dirs_exist_ok=True)
            log(f"    ✔ 已合并覆盖 {src}/", style="dim")
        else:
            shutil.copytree(src, dest)
            log(f"    ✔ 已复制目录 {src}/", style="dim")
        return True

    # ──────────── 两种启动路径 ────────────

    def _start_normal(self, task: dict) -> None:
        self._header(task)
        # 先拷配置，再跑命令（dest 目录可能由前序 task 创建）
        if not self._copy_for_task(task):
            return
        usage = self.ctx.substitute(task.get("usage", "")) or ""
        if not usage:
            self.statuses[task["name"]] = ("success", "copy only")
            return
        cwd = _compute_cwd(task, self.ctx)
        log(f"    ▸ 启动: {usage}", style="dim")
        if cwd:
            log(f"    ▸ cwd:  {cwd}", style="dim")
        try:
            stream = ProcessStream(usage, cwd, task["name"])
        except Exception as e:
            self.statuses[task["name"]] = ("fail", f"启动失败: {e}")
            log(f"    ✘ 启动失败: {e}", style="err")
            return
        self._launch(task, stream, 0)

    def _start_hash(self, task: dict, ref: str) -> None:
        cursor, stream = self.bus.wait(ref)  # 已 fired，立即返回
        self._header(task)
        log(f"    ▸ 挂载到 pid={stream.pid} (cursor={cursor})", style="dim")
        self._launch(task, stream, cursor)

    # ──────────── 调度循环 ────────────

    def _current_wave(self) -> float:
        """当前 wave = 所有活跃的独立 task（pending + running）里最小的 order。

        依赖型 task（有 depends 或 # 前缀）不参与 wave 计算——它们靠 cont_ref 触发。
        独立 task 只在自己的 order <= current_wave 时才能启动，
        保证 order=1 全部跑完后 order=2 才开始（同 order 并行）。
        """
        min_o = float("inf")
        # 还没启动的独立 task
        for t in self._pending:
            if t["name"].startswith("#") or t.get("depends"):
                continue
            min_o = min(min_o, t.get("order", float("inf")))
        # 已启动但还没出结果的独立 task（cont_ref 已触发的不再阻塞）
        with self._watcher_lock:
            for w in self.watchers:
                if w.verdict is not None:
                    continue
                if w.cont_ref_fired:
                    continue  # 已完成使命，不阻塞 wave
                t = w.task
                if t["name"].startswith("#") or t.get("depends"):
                    continue
                min_o = min(min_o, t.get("order", float("inf")))
        return min_o

    def _try_start(self) -> bool:
        """尝试启动所有当前可启动的 task。返回是否有 task 被处理（含纯 copy）。"""
        if self._fail_fast:
            for t in self._pending:
                self.statuses.setdefault(
                    t["name"], ("skip", "fail-fast: 前序任务失败")
                )
            self._pending = []
            return False
        wave = self._current_wave()
        still: list[dict] = []
        progressed = False
        for task in self._pending:
            name = task["name"]
            if name.startswith("#"):
                ref = name[1:]
                if self.bus.fired(ref):
                    self._start_hash(task, ref)
                    progressed = True
                else:
                    still.append(task)
                continue
            dep = task.get("depends")
            if dep:
                if self.bus.fired(dep):
                    self._start_normal(task)
                    progressed = True
                else:
                    still.append(task)
                continue
            o = task.get("order", float("inf"))
            if o > wave:
                still.append(task)
                continue
            self._start_normal(task)
            progressed = True
        self._pending = still
        return progressed

    def _alive_watchers(self) -> list[Watcher]:
        with self._watcher_lock:
            return [w for w in self.watchers if w.verdict is None]

    def _mark_unreachable(self) -> None:
        for t in self._pending:
            self.statuses[t["name"]] = ("skip", "依赖的 cont_ref 未命中")
        self._pending = []

    def _terminate_all(self) -> None:
        """终止所有子进程（fail-fast / Ctrl+C 触发）。
        标记 force_terminated 让 watcher 区分"被强杀"和"自己失败"，强杀的标 skip 不是 fail。"""
        with self._watcher_lock:
            for w in self.watchers:
                w.stream.force_terminated = True
                w.stream.terminate()

    def run(self) -> None:
        try:
            while True:
                progressed = self._try_start()
                alive = self._alive_watchers()
                if not self._pending and not alive:
                    break
                if self._pending and not alive and not progressed:
                    # 真正的死锁：没 task 被处理，也没活的 watcher 能 fire
                    self._mark_unreachable()
                    break
                if progressed:
                    continue  # 有进展（含纯 copy），立即重扫下一波
                with self._verdict_cond:
                    self._verdict_cond.wait(timeout=0.3)
        except KeyboardInterrupt:
            br()
            log("⏹ Ctrl+C 中断，终止所有进程", style="warn")
            self._terminate_all()
        except Exception:
            br()
            log("⏹ 致命错误，终止所有进程", style="err")
            self._terminate_all()
            raise

    def detached_entries(self) -> list[dict]:
        with self._watcher_lock:
            return [
                {
                    "pid": w.stream.pid,
                    "pgid": w.stream.pgid,
                    "cmd": w.stream.cmd,
                    "task": w.task["name"],
                }
                for w in self.watchers
                if w.stream.detached and w.stream.proc.poll() is None
            ]


# ══════════════════════════════════════════════
# 总结 · README · main
# ══════════════════════════════════════════════

# summary section 的三类分组：(icon, 中文标签, log 样式, statuses 里的状态值)
_SUMMARY_GROUPS: list[tuple[str, str, str, str]] = [
    ("✅", "成功", "ok", "success"),
    ("❌", "失败", "err", "fail"),
    ("⏭", "跳过", "warn", "skip"),
]


def _print_summary(statuses: dict, watchers: list, ctx: Context) -> None:
    br()
    log("[Step 5] 执行总结", style="section")
    log("═" * 60, style="dim")

    for icon, label, style, key in _SUMMARY_GROUPS:
        names = [n for n, (s, _) in statuses.items() if s == key]
        if not names:
            continue
        log(f"  {icon} {label} ({len(names)}):", style=style)
        for n in names:
            log(f"     ─ {n}  ({statuses[n][1]})", style="dim")

    detailed = [w for w in watchers if w.events]
    if detailed:
        br()
        log("  📜 Watcher 命中事件:", style="dim")
        for w in detailed:
            log(f"     ─ {w.task['name']}: {', '.join(w.events)}", style="dim")

    groups = ctx.snapshot()
    if groups:
        br()
        log("  📦 提取的命名组:", style="dim")
        for k, v in groups.items():
            log(f"     #{{{k}}} = {v}", style="dim")
    log("═" * 60, style="dim")


def _render_readme(readme_config: dict, tasks: list) -> None:
    output_path = readme_config.get("output", "README.md")
    title = readme_config.get("title", "使用指导")
    content_lines = readme_config.get("content", [])

    task_lines = [
        "",
        "## 部署清单",
        "",
        "| 任务 | 源文件 | 目标路径 | 使用方式 |",
        "| ---- | ------ | -------- | -------- |",
    ]
    for task in tasks:
        usage = task.get("usage", "")
        src = task.get("src", "")
        dest = task.get("dest", "")
        task_lines.append(f"| {task['name']} | `{src}` | `{dest}` | `{usage}` |")

    lines = [f"# {title}", "", *content_lines, *task_lines, ""]
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    log(f"  ✔ 已生成 {output_path}", style="ok")


def _load_vars_file(path: str) -> dict:
    """从 JSON 文件加载一组变量（单层 dict，值强转 str）。"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"vars-file 不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"vars-file 必须是 JSON 对象 (dict)，实际: {type(data).__name__}")
    return {str(k): str(v) for k, v in data.items()}


def run_deploy(
    manifest_path: str,
    cli_vars: Optional[dict] = None,
    vars_file: Optional[str] = None,
) -> None:
    manifest_dir = os.path.dirname(os.path.abspath(manifest_path)) or "."
    state_path = os.path.join(manifest_dir, STATE_FILE)

    log("[Step 0] 清理上次遗留进程", style="section")
    state_cleanup(state_path)

    br()
    log(f"[Step 1] 加载 {manifest_path}", style="section")
    manifest = load_manifest(manifest_path)
    log(f"  ✔ 共 {len(manifest.get('tasks', []))} 个任务", style="ok")

    # manifest 里 auto_yes: true 等同命令行 -y
    global _AUTO_YES
    if manifest.get("auto_yes"):
        if not _AUTO_YES:
            log("  ⚙ manifest.auto_yes=true → 覆盖确认全部自动 y", style="warn")
        _AUTO_YES = True

    # 变量合并优先级（低 → 高覆盖）:
    #   manifest.variables  <  --vars-file 文件  <  --key=value CLI 显式
    if vars_file:
        file_vars = _load_vars_file(vars_file)
        variables = manifest.setdefault("variables", {})
        variables.update(file_vars)
        for k, v in file_vars.items():
            log(f"  ⚙ vars-file 覆盖: ${{{k}}} = {v}", style="warn")

    if cli_vars:
        variables = manifest.setdefault("variables", {})
        variables.update(cli_vars)
        for k, v in cli_vars.items():
            log(f"  ⚙ CLI 覆盖: ${{{k}}} = {v}", style="warn")

    br()
    log("[Step 2] 解析变量 & 校验", style="section")
    manifest = resolve_variables(manifest)
    for k, v in manifest.get("variables", {}).items():
        log(f"  ${{{k}}} = {v}", style="dim")
    validate(manifest)
    log("  ✔ 校验通过（命名组无冲突、cont_ref 引用完整）", style="ok")

    tasks = manifest.get("tasks", [])
    statuses: dict[str, tuple[str, str]] = {}

    br()
    log("[Step 3] 调度执行（per-task 复制 + 启动）", style="section")
    ctx = Context()
    bus = EventBus()
    scheduler = Scheduler(tasks, statuses, ctx, bus)
    scheduler.run()

    detached = scheduler.detached_entries()
    state_write(state_path, detached)
    if detached:
        br()
        log(f"  ℹ {len(detached)} 个常驻进程记录到 {STATE_FILE}", style="dim")

    readme_config = manifest.get("readme")
    if readme_config:
        br()
        log("[Step 4] 生成使用指导文档", style="section")
        _render_readme(readme_config, tasks)

    _print_summary(statuses, scheduler.watchers, ctx)
    if any(s == "fail" for s, _ in statuses.values()):
        sys.exit(1)


def print_help() -> None:
    print(__doc__)


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print_help()
        return

    # 解析参数：-y/--yes + --manifest=path + --vars-file=path + --key=value
    global _AUTO_YES
    manifest_path = "manifest.json"
    vars_file: Optional[str] = None
    cli_vars: dict[str, str] = {}
    bad_args: list[str] = []
    for arg in args:
        if arg in ("-y", "--yes"):
            _AUTO_YES = True
        elif arg.startswith("--manifest="):
            manifest_path = arg.split("=", 1)[1]
        elif arg.startswith("--vars-file="):
            vars_file = arg.split("=", 1)[1]
        elif arg.startswith("--") and "=" in arg:
            key, _, value = arg[2:].partition("=")
            cli_vars[key] = value
        else:
            bad_args.append(arg)
    if bad_args:
        log(f"❌ 未知参数: {bad_args[0]}", style="err")
        print_help()
        sys.exit(1)

    log_dir = "deploy_log"
    os.makedirs(log_dir, exist_ok=True)
    _open_log(os.path.join(log_dir, f"deploy_{time.strftime('%Y%m%d_%H%M%S')}.log"))
    try:
        run_deploy(manifest_path, cli_vars=cli_vars, vars_file=vars_file)
    except (FileNotFoundError, ValueError) as e:
        br()
        log(f"❌ 错误: {e}", style="err")
        sys.exit(1)
    except json.JSONDecodeError as e:
        br()
        log(f"❌ JSON 解析错误: {e}", style="err")
        sys.exit(1)
    except Exception as e:
        br()
        log(f"❌ 未知错误: {e}", style="err")
        log(traceback.format_exc().rstrip(), style="dim")
        sys.exit(1)
    finally:
        _close_log()


if __name__ == "__main__":
    main()
