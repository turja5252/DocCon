# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Parent-side drop_host supervisor. Spawns the OLE child; this process does not OLE-register."""
from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from doccon.drop_inbox import inbox_dir
from doccon.drop_protocol import (
    DROP_HELPER_DOWN,
    DROP_HOST_DIED,
    OP_DROP,
    OP_GEOM,
    OP_HELLO,
    OP_HOVER,
    OP_LEAVE,
    OP_LOG,
    OP_QUIT,
    OP_READY,
    decode_line,
    drop_paths,
    drop_point,
    encode_msg,
    parse_frames,
)
from doccon.winproc import drop_host_popen_kwargs

DropPathsCallback = Callable[[list[str], int, int], None]
HoverCallback = Callable[[int, int], None]
LeaveCallback = Callable[[], None]
ScheduleCallback = Callable[[Callable[[], None]], None]
StatusCallback = Callable[[str], None]

RESTART_S = (1.0, 2.0, 5.0, 10.0, 15.0)
# 1.50-1.52 respawned a helper that died instantly, forever, and wrote 2 MB of log
# per session. Give up instead; paste and the watched folder do not need the child.
MAX_RESTARTS = 5
POLL_MS = 80
GEOM_MS = 120
MIN_REGION_W = 80
MIN_REGION_H = 36


def drop_host_src_root() -> Path:
    return Path(__file__).resolve().parent.parent


def drop_host_cwd() -> str:
    # Frozen onefile: do not cd into the parent's _MEI extract folder.
    if getattr(sys, "frozen", False):
        return os.getcwd()
    return str(drop_host_src_root().parent)


def drop_host_env() -> dict[str, str]:
    """PYTHONPATH=src so `python -m doccon.drop_host` works from any cwd."""
    env = os.environ.copy()
    if getattr(sys, "frozen", False):
        # Nested onefile must unpack its own _MEI, not reuse the parent's.
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        return env
    src = str(drop_host_src_root())
    prev = str(env.get("PYTHONPATH") or "").strip()
    env["PYTHONPATH"] = src if not prev else src + os.pathsep + prev
    return env


def drop_host_argv(
    port: int,
    inbox: Path,
    parent_pid: int,
    owner_hwnd: int = 0,
    geom: str = "",
) -> list[str]:
    argv = [
        sys.executable,
        "-m",
        "doccon.drop_host",
        "--port",
        str(int(port)),
        "--inbox",
        str(inbox),
        "--parent-pid",
        str(int(parent_pid)),
        "--owner-hwnd",
        str(int(owner_hwnd or 0)),
    ]
    if geom:
        argv.extend(["--geom", str(geom)])
    return argv


def _log(message: str, *, level: str = "INFO") -> None:
    try:
        from doccon.diag import log

        log(level, "drop", message)
    except Exception:
        return


def _in_pytest() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) and not os.environ.get("DOCCON_TEST_DROP_HOST")


def drop_host_available() -> bool:
    return os.name == "nt"


def client_screen_rect(widget) -> tuple[int, int, int, int, bool]:
    try:
        x = int(widget.winfo_rootx())
        y = int(widget.winfo_rooty())
        w = max(int(widget.winfo_width()), 1)
        h = max(int(widget.winfo_height()), 1)
        visible = bool(widget.winfo_viewable())
        return x, y, w, h, visible
    except Exception:
        return 0, 0, 1, 1, False


def union_screen_rect(widgets) -> tuple[int, int, int, int, bool]:
    """Screen box covering the Drop PDFs dock and drawing board."""
    boxes: list[tuple[int, int, int, int]] = []
    fallback: tuple[int, int, int, int, bool] | None = None
    for widget in widgets or ():
        if widget is None:
            continue
        geom = client_screen_rect(widget)
        if fallback is None:
            fallback = geom
        x, y, w, h, visible = geom
        if visible and w >= 8 and h >= 8:
            boxes.append((x, y, w, h))
    if not boxes:
        return fallback or (0, 0, 1, 1, False)
    x0 = min(box[0] for box in boxes)
    y0 = min(box[1] for box in boxes)
    x1 = max(box[0] + box[2] for box in boxes)
    y1 = max(box[1] + box[3] for box in boxes)
    return x0, y0, max(x1 - x0, 1), max(y1 - y0, 1), True


def _hwnd_from_token(token: object) -> int:
    text = str(token or "").strip()
    if not text:
        return 0
    try:
        return int(text, 16) if text.lower().startswith("0x") else int(text)
    except ValueError:
        try:
            return int(text)
        except ValueError:
            return 0


def toplevel_owner_hwnd(widget) -> int:
    if widget is None:
        return 0
    with contextlib.suppress(Exception):
        hwnd = _hwnd_from_token(widget.winfo_toplevel().wm_frame())
        if hwnd:
            return hwnd
    with contextlib.suppress(Exception):
        return int(widget.winfo_toplevel().winfo_id())
    return 0


def format_geom_arg(geom: tuple[int, int, int, int, bool]) -> str:
    x, y, w, h, _visible = geom
    return f"{int(x)},{int(y)},{int(w)},{int(h)}"


class DropBridge:
    """Listen on localhost, spawn `python -m doccon.drop_host`, pair paths on the Tk thread."""

    def __init__(
        self,
        on_drop: DropPathsCallback,
        hover: HoverCallback | None = None,
        leave: LeaveCallback | None = None,
        schedule: ScheduleCallback | None = None,
        on_status: StatusCallback | None = None,
    ) -> None:
        self._on_drop = on_drop
        self._hover = hover
        self._leave = leave
        self._schedule = schedule
        self._on_status = on_status
        self._widget = None
        self._regions: list = []
        self._listen: socket.socket | None = None
        self._conn: socket.socket | None = None
        self._proc: subprocess.Popen | None = None
        self._buffer = b""
        self._stopping = False
        self._started = False
        self._port = 0
        self._inbox = inbox_dir()
        self._restarts = 0
        self._restart_after = ""
        self._poll_after = ""
        self._geom_after = ""
        self._last_geom: tuple[int, int, int, int, bool] | None = None
        self._err_handle = None
        self._configure_bound = False

    def start(self, widget, regions=None) -> None:
        self._widget = widget
        self._regions = [item for item in (regions or ()) if item is not None]
        if not self._regions and widget is not None:
            self._regions = [widget]
        self._bind_configure()
        if self._stopping:
            return
        if not drop_host_available():
            return
        if _in_pytest():
            _log("drop_host spawn skipped under pytest")
            return
        if self._started and self._proc is not None and self._proc.poll() is None:
            self._send_geom()
            return
        self._started = True
        self._spawn()
        self._arm_poll()
        self._arm_geom()

    def _bind_configure(self) -> None:
        if self._configure_bound:
            return
        seen: set[int] = set()
        for widget in [self._widget, *self._regions]:
            if widget is None or id(widget) in seen:
                continue
            seen.add(id(widget))
            try:
                widget.bind("<Configure>", lambda _event: self._send_geom(), add="+")
            except Exception:
                continue
        self._configure_bound = True

    def stop(self) -> None:
        self._stopping = True
        self._started = False
        self._cancel_timers()
        with contextlib.suppress(Exception):
            self._send_raw(encode_msg(OP_QUIT))
        proc = self._proc
        self._proc = None
        self._close_conn()
        self._close_listen()
        if proc is not None and proc.poll() is None:
            with contextlib.suppress(Exception):
                proc.terminate()
            try:
                proc.wait(timeout=2)
            except Exception:
                with contextlib.suppress(Exception):
                    proc.kill()
        if self._err_handle is not None:
            with contextlib.suppress(Exception):
                self._err_handle.close()
            self._err_handle = None

    def _cancel_timers(self) -> None:
        widget = self._widget
        for attr in ("_poll_after", "_geom_after", "_restart_after"):
            token = getattr(self, attr)
            if token and widget is not None:
                with contextlib.suppress(Exception):
                    widget.after_cancel(token)
            setattr(self, attr, "")

    def _arm_poll(self) -> None:
        widget = self._widget
        if widget is None or self._stopping:
            return

        def tick() -> None:
            self._poll_after = ""
            try:
                self._poll()
            except Exception as vis:
                _log(f"drop_host poll {vis}", level="WARN")
            self._arm_poll()

        try:
            self._poll_after = widget.after(POLL_MS, tick)
        except Exception as vis:
            _log(f"drop_host poll arm {vis}", level="WARN")

    def _arm_geom(self) -> None:
        widget = self._widget
        if widget is None or self._stopping:
            return

        def tick() -> None:
            self._geom_after = ""
            try:
                self._send_geom()
            except Exception as vis:
                _log(f"drop_host geom {vis}", level="WARN")
            self._arm_geom()

        try:
            self._geom_after = widget.after(GEOM_MS, tick)
        except Exception:
            return

    def _notify_down(self, detail: str = "") -> None:
        text = detail.strip()
        if text:
            _log(text, level="WARN")
        self._status(DROP_HELPER_DOWN)

    def _status(self, text: str) -> None:
        if self._on_status is None:
            return

        def run() -> None:
            if self._on_status is None:
                return
            try:
                self._on_status(text)
            except Exception as vis:
                _log(f"status {vis}", level="WARN")

        self._call_tk(run)

    def _err_path(self) -> Path:
        return Path(self._inbox).parent / "drop_host.err"

    def _err_tail(self) -> str:
        path = self._err_path()
        try:
            data = path.read_bytes()[-2500:]
        except OSError:
            return ""
        return data.decode("utf-8", errors="replace").strip()

    def _spawn(self) -> None:
        if self._stopping:
            return
        self._close_conn()
        self._buffer = b""
        self._listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listen.bind(("127.0.0.1", 0))
        self._listen.listen(1)
        self._listen.setblocking(False)
        self._port = int(self._listen.getsockname()[1])
        self._inbox.mkdir(parents=True, exist_ok=True)
        geom = self._region_geom()
        owner = toplevel_owner_hwnd(self._widget)
        geom_arg = ""
        if geom is not None and geom[4] and geom[2] >= MIN_REGION_W and geom[3] >= MIN_REGION_H:
            geom_arg = format_geom_arg(geom)
        argv = drop_host_argv(self._port, self._inbox, os.getpid(), owner, geom_arg)
        cwd = drop_host_cwd()
        env = drop_host_env()
        _log(
            f"drop_host started bind port={self._port} inbox={self._inbox} owner={owner:#x} "
            f"cwd={cwd} pythonpath={env.get('PYTHONPATH', '')[:180]}"
        )
        try:
            if self._err_handle is not None:
                with contextlib.suppress(Exception):
                    self._err_handle.close()
                self._err_handle = None
            err = self._err_path().open("ab")
            self._err_handle = err
            kwargs = drop_host_popen_kwargs()
            self._proc = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=err,
                cwd=cwd,
                env=env,
                **kwargs,
            )
            _log(f"drop_host started pid={self._proc.pid} bind port={self._port} argv={argv[:6]}")
        except Exception as vis:
            _log(f"drop_host spawn failed {vis} argv={argv} cwd={cwd}", level="WARN")
            self._proc = None
            self._close_listen()
            self._notify_down(f"drop_host spawn failed {vis}")
            self._schedule_restart()

    def _poll(self) -> None:
        if self._stopping:
            return
        self._accept()
        self._recv()
        proc = self._proc
        if proc is not None and proc.poll() is not None:
            code = proc.returncode
            pid = proc.pid
            self._proc = None
            self._close_conn()
            tail = self._err_tail()
            extra = f" err={tail[-400:]}" if tail else ""
            _log(f"{DROP_HOST_DIED} pid={pid} code={code}{extra}", level="WARN")
            self._notify_down()
            self._schedule_restart()

    def _accept(self) -> None:
        if self._conn is not None or self._listen is None:
            return
        try:
            conn, _addr = self._listen.accept()
        except BlockingIOError:
            return
        except OSError as vis:
            _log(f"drop_host accept {vis}", level="WARN")
            return
        conn.setblocking(False)
        self._conn = conn
        _log("drop_host connected")
        with contextlib.suppress(Exception):
            self._send_raw(encode_msg(OP_HELLO, inbox=str(self._inbox)))
        self._send_geom(force=True)

    def _recv(self) -> None:
        conn = self._conn
        if conn is None:
            return
        try:
            chunk = conn.recv(65536)
        except BlockingIOError:
            return
        except OSError as vis:
            _log(f"drop_host recv {vis}", level="WARN")
            self._close_conn()
            return
        if not chunk:
            _log("drop_host socket closed", level="WARN")
            self._close_conn()
            return
        messages, self._buffer = parse_frames(self._buffer + chunk)
        for msg in messages:
            self._dispatch(msg)

    def _dispatch(self, msg: dict) -> None:
        op = str(msg.get("op") or "")
        if op == OP_READY:
            self._restarts = 0
            hwnd = int(msg.get("hwnd") or 0)
            dock = int(msg.get("dock_hwnd") or 0)
            _log(
                f"drop_host started pid={msg.get('pid')} bind port={self._port} "
                f"overlay hwnd={hwnd:#x} dock hwnd={dock:#x}"
            )
            self._send_geom(force=True)
            return
        if op == OP_LOG:
            _log(f"host {msg.get('msg') or ''}", level=str(msg.get("level") or "INFO"))
            return
        if op == OP_DROP:
            paths = drop_paths(msg)
            x, y = drop_point(msg)
            kind = str(msg.get("kind") or "ole")
            _log(f"drop_host drop kind={kind} count={len(paths)} pt={x},{y}")
            self._call_tk(lambda: self._on_drop(paths, x, y))
            return
        if op == OP_HOVER:
            x, y = drop_point(msg)
            if self._hover is not None:
                self._call_tk(lambda: self._hover(x, y) if self._hover else None)
            return
        if op == OP_LEAVE:
            if self._leave is not None:
                self._call_tk(self._leave)
            return
        if op == OP_QUIT:
            return
        _log(f"drop_host unknown op={op}", level="WARN")

    def _call_tk(self, fn: Callable[[], None]) -> None:
        def run(job=fn) -> None:
            try:
                job()
            except Exception as vis:
                _log(f"scheduled {vis}", level="WARN")

        if self._schedule is not None:
            try:
                self._schedule(run)
                return
            except Exception as vis:
                _log(f"schedule {vis}", level="WARN")
        widget = self._widget
        if widget is not None:
            try:
                widget.after(0, run)
                return
            except Exception as vis:
                _log(f"after(0) {vis}", level="WARN")
                return
        run()

    def _region_geom(self) -> tuple[int, int, int, int, bool] | None:
        widgets = list(self._regions) or ([self._widget] if self._widget is not None else [])
        if not widgets:
            return None
        return union_screen_rect(widgets)

    def _send_geom(self, *, force: bool = False) -> None:
        geom = self._region_geom()
        if geom is None:
            return
        x, y, w, h, visible = geom
        if visible and (w < MIN_REGION_W or h < MIN_REGION_H):
            if self._last_geom is not None and self._last_geom[2] >= MIN_REGION_W:
                return
            if not force:
                return
        if not force and geom == self._last_geom:
            return
        self._last_geom = geom
        hwnd = toplevel_owner_hwnd(self._widget)
        self._send_raw(
            encode_msg(OP_GEOM, x=x, y=y, w=w, h=h, visible=visible, hwnd=hwnd)
        )

    def _send_raw(self, payload: bytes) -> None:
        conn = self._conn
        if conn is None:
            return
        try:
            conn.sendall(payload)
        except OSError:
            self._close_conn()

    def _schedule_restart(self) -> None:
        if self._stopping or self._widget is None:
            return
        if self._restarts >= MAX_RESTARTS:
            _log(
                f"drop_host gave up after {self._restarts} failed starts — "
                "use Paste PDF or the watched folder",
                level="WARN",
            )
            self._started = False
            return
        delay = RESTART_S[min(self._restarts, len(RESTART_S) - 1)]
        self._restarts += 1
        _log(f"drop_host restart {self._restarts}/{MAX_RESTARTS} in {delay:.0f}s")

        def go() -> None:
            self._restart_after = ""
            if self._stopping:
                return
            try:
                self._spawn()
            except Exception as vis:
                _log(f"drop_host restart {vis}", level="WARN")

        try:
            self._restart_after = self._widget.after(int(delay * 1000), go)
        except Exception:
            return

    def _close_conn(self) -> None:
        conn = self._conn
        self._conn = None
        self._buffer = b""
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()

    def _close_listen(self) -> None:
        listen = self._listen
        self._listen = None
        if listen is not None:
            with contextlib.suppress(Exception):
                listen.close()

    def note_child_exit(self, code: int, pid: int = 0) -> None:
        """Tests / supervisor hook. Parent stays up."""
        _log(f"{DROP_HOST_DIED} pid={pid} code={code}", level="WARN")
        self._notify_down()


def parent_alive(pid: int) -> bool:
    if pid <= 0:
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def decode_parent_line(line: str) -> dict | None:
    return decode_line(line)
