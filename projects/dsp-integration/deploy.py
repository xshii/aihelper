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
    python deploy.py           # 部署 + 调度
    python deploy.py -h        # 帮助

首次使用: cp manifest.json.example manifest.json && vim manifest.json
"""

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


# ══════════════════════════════════════════════
# 日志辅助：时间戳 + ANSI 颜色 + 线程安全
# ══════════════════════════════════════════════

_USE_COLOR = sys.stdout.isatty()
_PRINT_LOCK = threading.Lock()


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
    """带时间戳前缀的线程安全输出。

    style 可选:
        ""        默认
        "dim"     灰（子进程 stdout、详情、info）
        "ok"      绿（成功）
        "warn"    黄（需注意）
        "err"     红粗（错误）
        "hit"     青粗（keyword 命中等关键事件）
        "section" 粗体（step 标题）
    """
    color = _STYLE.get(style, "")
    with _PRINT_LOCK:
        print(f"{DIM}{_ts()}{RESET} {color}{msg}{RESET}", flush=True)


def br() -> None:
    """空行分隔，无时间戳。"""
    with _PRINT_LOCK:
        print(flush=True)


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
    """静态 ${var} 替换。src/dest 严格；note/usage/cwd 宽松（允许 ${HOME} 透传）。"""
    variables = manifest.get("variables", {})
    if variables:
        for _ in range(10):
            changed = False
            for k, v in variables.items():
                if not isinstance(v, str) or "${" not in v:
                    continue
                new_v = re.sub(
                    r"\$\{(\w+)\}",
                    lambda m: variables.get(m.group(1), m.group(0)),
                    v,
                )
                if new_v != v:
                    variables[k] = new_v
                    changed = True
            if not changed:
                break
        for k, v in variables.items():
            if isinstance(v, str) and "${" in v:
                raise ValueError(f"变量循环引用或未定义: {k} = {v}")

    def replace(text: str, strict: bool) -> str:
        def _sub(m):
            key = m.group(1)
            if key in variables:
                return variables[key]
            if strict:
                raise ValueError(f"未定义的变量: ${{{key}}}")
            return m.group(0)

        return re.sub(r"\$\{(\w+)\}", _sub, text)

    for task in manifest.get("tasks", []):
        if "src" in task:
            task["src"] = replace(task["src"], strict=True)
        if "dest" in task:
            task["dest"] = replace(task["dest"], strict=True)
        if "note" in task:
            task["note"] = replace(task["note"], strict=False)
        if "usage" in task:
            task["usage"] = replace(task["usage"], strict=False)
        if "cwd" in task:
            task["cwd"] = replace(task["cwd"], strict=False)
    return manifest


def validate(manifest: dict) -> None:
    """加载期校验：命名组冲突、cont_ref 引用完整。"""
    seen_groups: dict[str, tuple[str, int]] = {}  # group_name -> (task, kw_index)
    declared_refs: set[str] = set()  # 所有被 cont_ref 声明的值
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
            if kw.get("cont_ref"):
                declared_refs.add(kw["cont_ref"])
            kw_type = kw.get("type", "success")
            if kw_type not in ("error", "success"):
                raise ValueError(f"[{tname}] keyword[{i}] type 只能是 error/success")
        if tname.startswith("#"):
            referenced_refs.add(tname[1:])
        if task.get("depends"):
            referenced_refs.add(task["depends"])

    missing = referenced_refs - declared_refs
    if missing:
        raise ValueError(f"引用的 cont_ref 未定义: {', '.join(sorted(missing))}")


# ══════════════════════════════════════════════
# Context · EventBus
# ══════════════════════════════════════════════


class Context:
    """全局 #{name} → value。first-write-wins（但 P1 已保证不会冲突）。"""

    def __init__(self):
        self._d: dict[str, str] = {}
        self._lock = threading.Lock()

    def set_if_absent(self, name: str, value: str):
        with self._lock:
            if name not in self._d:
                self._d[name] = value

    def substitute(self, text: Optional[str]) -> Optional[str]:
        if not text or "#{" not in text:
            return text

        def _repl(m):
            return self._d.get(m.group(1), m.group(0))

        return re.sub(r"#\{(\w+)\}", _repl, text)

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._d)


class EventBus:
    """cont_ref 命中广播。一个 ref 只触发一次，记录命中时的 cursor 位置。"""

    def __init__(self):
        self._fired: dict[str, tuple[int, "ProcessStream"]] = {}
        self._cond = threading.Condition()

    def fire(self, ref: str, cursor: int, stream: "ProcessStream"):
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
        # 有 stdbuf 就强制行缓冲，macOS 的 gstdbuf 也认
        stdbuf_bin = shutil.which("stdbuf") or shutil.which("gstdbuf")
        real_cmd = f"{stdbuf_bin} -oL -eL {cmd}" if stdbuf_bin else cmd

        self.cmd = cmd
        self.task_name = task_name
        self.proc = subprocess.Popen(
            real_cmd,
            shell=True,
            cwd=cwd or None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,  # 独立进程组，方便 killpg
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
        self._reader = threading.Thread(
            target=self._read, daemon=True, name=f"reader-{task_name}"
        )
        self._reader.start()

    def _read(self):
        try:
            assert self.proc.stdout is not None
            for line in self.proc.stdout:
                line = line.rstrip("\n")
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

    def terminate(self):
        if self.proc.poll() is None:
            try:
                os.killpg(self.pgid, signal.SIGTERM)
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(self.pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def detach(self):
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

    def run(self):
        try:
            while self.verdict is None:
                line, new_cursor = self.stream.read_from(self.cursor)
                if line is None:
                    self._finalize_on_close()
                    break
                self.cursor = new_cursor
                self._scan(line)
        except Exception as e:
            log(
                f"    ✘ [{self.task['name']}] watcher 异常: {e}",
                style="err",
            )
            log(traceback.format_exc().rstrip(), style="dim")
            self._seal("fail", f"watcher 异常: {e}")

    def _scan(self, line: str):
        name = self.task["name"]
        for idx, ks in enumerate(self.keywords):
            if ks.consumed:
                continue
            m = ks.pattern.search(line)
            if not m:
                continue
            ks.hit_count += 1
            if ks.hit_count < ks.times:
                # times > 1 时打进度让用户看到累计
                if ks.times > 1:
                    log(
                        f"    ⚡ [{name}] keyword#{idx} 命中进度 "
                        f"{ks.hit_count}/{ks.times}",
                        style="dim",
                    )
                return
            ks.consumed = True

            # 提取命名组 → 全局
            groups = {k: v for k, v in m.groupdict().items() if v is not None}
            for gname, gval in groups.items():
                self.ctx.set_if_absent(gname, gval)

            kw_type = ks.spec.get("type", "success")
            cont_ref = ks.spec.get("cont_ref")

            if cont_ref:
                tag = f"{kw_type}→{cont_ref}"
                self.events.append(tag)
                log(
                    f"    ⚡ [{name}] keyword#{idx} 命中 "
                    f"→ cont_ref={cont_ref} ({kw_type})",
                    style="hit",
                )
            else:
                self.events.append(kw_type)
                log(
                    f"    ⚡ [{name}] keyword#{idx} 命中 → {kw_type}（终止进程）",
                    style="hit",
                )
            # 展示匹配细节
            log(f"      matched: {m.group(0)!r}", style="dim")
            if groups:
                gs = ", ".join(f"{k}={v}" for k, v in groups.items())
                log(f"      groups:  {gs}", style="dim")

            if cont_ref:
                self.stream.detach()
                self.bus.fire(cont_ref, self.cursor, self.stream)
                # 不 seal，继续扫后续 keyword
                return
            else:
                self.stream.terminate()
                self._seal(kw_type, f"keyword#{idx}({kw_type}) matched")
                return

    def _finalize_on_close(self):
        if self.verdict is not None:
            return
        rc = self.stream.proc.returncode
        # 按事件历史优先决定
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

    def _seal(self, verdict: str, reason: str):
        if self.verdict is not None:
            return
        self.verdict = verdict
        self.reason = reason
        self.on_verdict(self)


# ══════════════════════════════════════════════
# State file: 跨运行的 PID 追踪
# ══════════════════════════════════════════════


def state_cleanup(state_path: str):
    """Kill 上次运行留下的常驻进程。"""
    if not os.path.exists(state_path):
        return
    try:
        with open(state_path) as f:
            entries = json.load(f)
    except Exception:
        os.remove(state_path)
        return
    if not entries:
        os.remove(state_path)
        return
    log(f"  ℹ 清理上次留下的 {len(entries)} 个常驻进程", style="dim")
    for e in entries:
        pid = e.get("pid")
        task = e.get("task", "?")
        log(f"     ─ pid={pid} task={task}", style="dim")
    for e in entries:
        pgid = e.get("pgid") or e.get("pid")
        try:
            os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    time.sleep(0.5)
    for e in entries:
        pgid = e.get("pgid") or e.get("pid")
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    os.remove(state_path)


def state_write(state_path: str, entries: list):
    if not entries:
        return
    with open(state_path, "w") as f:
        json.dump(entries, f, indent=2)


# ══════════════════════════════════════════════
# 辅助
# ══════════════════════════════════════════════


def atomic_copy(src: str, dest: str):
    tmp = dest + ".tmp"
    shutil.copy2(src, tmp)
    os.replace(tmp, dest)


def copy_phase(tasks: list, statuses: dict):
    """只处理普通 task (name 不以 # 开头) 的 src → dest。"""
    br()
    log("[Step 3] 复制配置文件", style="section")
    for task in tasks:
        name = task["name"]
        if name.startswith("#"):
            continue
        src = task.get("src")
        dest = task.get("dest")
        if not src or not dest:
            continue
        if not os.path.exists(src):
            log(f"  ✘ [{name}] 源文件不存在: {src}", style="err")
            statuses[name] = ("fail", f"src not found: {src}")
            continue
        dest_dir = os.path.dirname(dest)
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)
        if os.path.exists(dest):
            if filecmp.cmp(src, dest, shallow=False):
                log(f"  ✔ [{name}] 内容一致，跳过", style="dim")
                continue
            log(f"  ⚠ [{name}] dest 与 src 不一致", style="warn")
            try:
                answer = input("    覆盖? (y/n): ").strip().lower()
            except EOFError:
                answer = "n"
            if answer != "y":
                log("    ⏭ 跳过覆盖", style="dim")
                continue
            atomic_copy(src, dest)
            log("    ✔ 已覆盖", style="ok")
        else:
            atomic_copy(src, dest)
            log(f"  ✔ [{name}] 已复制", style="ok")


# ══════════════════════════════════════════════
# 主调度
# ══════════════════════════════════════════════


def run_deploy(manifest_path: str):
    manifest_dir = os.path.dirname(os.path.abspath(manifest_path)) or "."
    state_path = os.path.join(manifest_dir, STATE_FILE)

    log("[Step 0] 清理上次遗留进程", style="section")
    state_cleanup(state_path)

    br()
    log(f"[Step 1] 加载 {manifest_path}", style="section")
    manifest = load_manifest(manifest_path)
    tasks = manifest.get("tasks", [])
    log(f"  ✔ 共 {len(tasks)} 个任务", style="ok")

    br()
    log("[Step 2] 解析变量 & 校验", style="section")
    manifest = resolve_variables(manifest)
    for k, v in manifest.get("variables", {}).items():
        log(f"  ${{{k}}} = {v}", style="dim")
    validate(manifest)
    log("  ✔ 校验通过（命名组无冲突、cont_ref 引用完整）", style="ok")

    statuses: dict[str, tuple[str, str]] = {}  # name -> (status, reason)
    copy_phase(tasks, statuses)

    br()
    log("[Step 4] 调度执行", style="section")
    ctx = Context()
    bus = EventBus()
    watchers: list[Watcher] = []
    watcher_lock = threading.Lock()
    verdict_cond = threading.Condition()

    def on_verdict(w: Watcher):
        statuses[w.task["name"]] = (w.verdict or "fail", w.reason)
        with verdict_cond:
            verdict_cond.notify_all()

    runnable = [
        t
        for t in tasks
        if (t.get("usage") or t["name"].startswith("#"))
        and statuses.get(t["name"], ("", ""))[0] != "fail"
    ]
    runnable.sort(key=lambda t: t.get("order", float("inf")))
    pending = list(runnable)
    started: set[str] = set()

    def start_normal(task: dict):
        usage = ctx.substitute(task.get("usage", "")) or ""
        cwd_raw = task.get("cwd") or os.path.dirname(task.get("dest", "")) or None
        cwd = ctx.substitute(cwd_raw)
        note = task.get("note", "")
        order = task.get("order", "-")
        br()
        log(f"  ▶ [{order}] {note or task['name']}")
        log(f"    ▸ 启动: {usage}", style="dim")
        if cwd:
            log(f"    ▸ cwd:  {cwd}", style="dim")
        try:
            stream = ProcessStream(usage, cwd, task["name"])
        except Exception as e:
            statuses[task["name"]] = ("fail", f"启动失败: {e}")
            log(f"    ✘ 启动失败: {e}", style="err")
            return
        w = Watcher(task, stream, 0, ctx, bus, on_verdict)
        with watcher_lock:
            watchers.append(w)
        w.start()

    def start_hash(task: dict, ref: str):
        cursor, stream = bus.wait(ref)  # 已经 fired，立即返回
        note = task.get("note", "")
        order = task.get("order", "-")
        br()
        log(f"  ▶ [{order}] {note or task['name']}")
        log(f"    ▸ 挂载到 pid={stream.pid} (cursor={cursor})", style="dim")
        w = Watcher(task, stream, cursor, ctx, bus, on_verdict)
        with watcher_lock:
            watchers.append(w)
        w.start()

    def try_start() -> bool:
        """返回本轮是否有新任务被启动。"""
        nonlocal pending
        still: list[dict] = []
        progressed = False
        for task in pending:
            name = task["name"]
            if name in started:
                continue
            if name.startswith("#"):
                ref = name[1:]
                if bus.fired(ref):
                    started.add(name)
                    start_hash(task, ref)
                    progressed = True
                else:
                    still.append(task)
                continue
            dep = task.get("depends")
            if dep and not bus.fired(dep):
                still.append(task)
                continue
            started.add(name)
            start_normal(task)
            progressed = True
        pending = still
        return progressed

    try:
        while True:
            try_start()
            with watcher_lock:
                alive = [w for w in watchers if w.verdict is None]
            if not pending and not alive:
                break
            if pending and not alive:
                # 没有活的 task 可以再触发 cont_ref，剩下的永远等不到
                for t in pending:
                    statuses[t["name"]] = ("skip", "依赖的 cont_ref 未命中")
                pending = []
                break
            with verdict_cond:
                verdict_cond.wait(timeout=0.3)
    except KeyboardInterrupt:
        br()
        log("⏹ Ctrl+C 中断，正在终止非常驻进程", style="warn")
        with watcher_lock:
            for w in watchers:
                if not w.stream.detached:
                    w.stream.terminate()

    # 写 state file（脱离的进程留给下次清理）
    with watcher_lock:
        detached_entries = [
            {
                "pid": w.stream.pid,
                "pgid": w.stream.pgid,
                "cmd": w.stream.cmd,
                "task": w.task["name"],
            }
            for w in watchers
            if w.stream.detached and w.stream.proc.poll() is None
        ]
    state_write(state_path, detached_entries)
    if detached_entries:
        br()
        log(
            f"  ℹ {len(detached_entries)} 个常驻进程记录到 {STATE_FILE}",
            style="dim",
        )

    # README 生成（可选）
    readme_config = manifest.get("readme")
    if readme_config:
        br()
        log("[Step 5] 生成使用指导文档", style="section")
        _render_readme(readme_config, tasks)

    # 总结
    br()
    log("[Step 6] 执行总结", style="section")
    log("═" * 60, style="dim")
    succ = [n for n, (s, _) in statuses.items() if s == "success"]
    fail = [n for n, (s, _) in statuses.items() if s == "fail"]
    skip = [n for n, (s, _) in statuses.items() if s == "skip"]
    if succ:
        log(f"  ✅ 成功 ({len(succ)}):", style="ok")
        for n in succ:
            log(f"     ─ {n}  ({statuses[n][1]})", style="dim")
    if fail:
        log(f"  ❌ 失败 ({len(fail)}):", style="err")
        for n in fail:
            log(f"     ─ {n}  ({statuses[n][1]})", style="dim")
    if skip:
        log(f"  ⏭ 跳过 ({len(skip)}):", style="warn")
        for n in skip:
            log(f"     ─ {n}  ({statuses[n][1]})", style="dim")

    # Watcher 内部事件列表（供调试）
    with watcher_lock:
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

    if fail:
        sys.exit(1)


def _render_readme(readme_config: dict, tasks: list):
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


# ══════════════════════════════════════════════
# main
# ══════════════════════════════════════════════


def print_help():
    print(__doc__)


def main():
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print_help()
        return
    if args:
        log(f"❌ 未知参数: {args[0]}", style="err")
        print_help()
        sys.exit(1)

    try:
        run_deploy("manifest.json")
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


if __name__ == "__main__":
    main()
