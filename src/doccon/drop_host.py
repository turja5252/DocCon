# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Child process: OLE IDropTarget lives here. A native AV must not kill DocCon."""
from __future__ import annotations

import argparse
import contextlib
import os
import select
import socket
import time
import traceback
from pathlib import Path

from doccon.drop_inbox import inbox_dir, stage_sources
from doccon.drop_protocol import (
    OP_DROP,
    OP_GEOM,
    OP_HELLO,
    OP_HOVER,
    OP_LEAVE,
    OP_LOG,
    OP_QUIT,
    OP_READY,
    encode_msg,
    parse_frames,
)

# WindowFromPoint skips WS_EX_TRANSPARENT, so IDropTarget never runs (no-entry cursor).
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
LWA_ALPHA = 0x00000002
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_HIDEWINDOW = 0x0080
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
WM_DESTROY = 0x0002
WM_PAINT = 0x000F
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A
WM_QUIT = 0x0012
PM_REMOVE = 1
CS_DBLCLKS = 0x0008
GWL_EXSTYLE = -20
ERROR_CLASS_ALREADY_EXISTS = 1410
DT_CENTER = 0x00000001
DT_VCENTER = 0x00000004
DT_SINGLELINE = 0x00000020
# Layered board overlay: alpha > 0 is still hit-tested with SetLayeredWindowAttributes.
OVERLAY_ALPHA = 60
DOCK_HEIGHT = 52
MIN_OVERLAY_W = 80
MIN_OVERLAY_H = 48
DOCK_CAPTION = "Drop PDFs — drag from Outlook or Explorer"
CLASS_DOCK = "EliteDocConDropDock"
CLASS_BOARD = "EliteDocConDropOverlay"
# COLORREF 0x00BBGGRR for Elite teal #2DD4BF and navy #102A43.
DOCK_FILL = 0x00BFD42D
DOCK_TEXT = 0x00432A10

# Clicks may be forwarded; WM_MOUSEMOVE must not hide the overlay (OLE hit-test).
MOUSE_FORWARD = (
    WM_LBUTTONDOWN,
    WM_LBUTTONUP,
    WM_LBUTTONDBLCLK,
    WM_RBUTTONDOWN,
    WM_RBUTTONUP,
    WM_MBUTTONDOWN,
    WM_MBUTTONUP,
    WM_MOUSEWHEEL,
)


def overlay_ex_style(*, layered: bool = True) -> int:
    """IDropTarget HWND styles. Never WS_EX_TRANSPARENT — that blocks OLE."""
    bits = WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST
    if layered:
        bits |= WS_EX_LAYERED
    return bits & ~WS_EX_TRANSPARENT


def overlay_accepts_ole_input(ex_style: int) -> bool:
    return (int(ex_style) & WS_EX_TRANSPARENT) == 0


def parse_geom_arg(text: str) -> tuple[int, int, int, int] | None:
    parts = [part.strip() for part in str(text or "").split(",")]
    if len(parts) != 4:
        return None
    try:
        x, y, w, h = (int(part) for part in parts)
    except ValueError:
        return None
    return x, y, max(w, 1), max(h, 1)


def split_overlay_geom(
    x: int, y: int, w: int, h: int, *, dock_h: int = DOCK_HEIGHT
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int] | None]:
    """Top strip is the always-on-top Drop PDFs dock; the rest covers the board."""
    width = max(int(w), 1)
    height = max(int(h), 1)
    strip = min(max(int(dock_h), 1), height)
    dock = (int(x), int(y), width, strip)
    rest = height - strip
    if rest <= 0:
        return dock, None
    return dock, (int(x), int(y) + strip, width, rest)


def geom_is_usable(w: int, h: int) -> bool:
    return int(w) >= MIN_OVERLAY_W and int(h) >= MIN_OVERLAY_H


def _log(message: str, *, level: str = "INFO") -> None:
    try:
        from doccon.diag import log

        log(level, "drop_host", message)
    except Exception:
        return


def _send(sock: socket.socket | None, payload: bytes) -> None:
    if sock is None:
        return
    with contextlib.suppress(OSError):
        sock.sendall(payload)


def parent_alive(pid: int) -> bool:
    """Only a genuine "no such process" counts as gone.

    A denied OpenProcess is not proof the parent died, and treating it as proof
    made the helper exit ~0.3s after every spawn ("parent gone"), which burned
    all five restarts before the operator could drag anything. Parent death is
    also visible as a closed socket, so failing open here is safe.
    """
    if pid <= 0:
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        _log(f"parent pid={pid} no longer exists")
        return False
    except PermissionError as exc:
        _log(f"parent pid={pid} query denied ({exc}); assuming alive")
        return True
    except OSError as exc:
        _log(f"parent pid={pid} check failed ({exc}); assuming alive", level="WARN")
        return True
    return True


def _stage_and_notify(sock, sources, x: int, y: int, inbox: Path, kind: str) -> None:
    try:
        paths = stage_sources(list(sources), folder=inbox)
    except Exception as vis:
        _log(f"stage {vis}", level="WARN")
        _send(sock, encode_msg(OP_LOG, level="WARN", msg=f"stage {vis}"))
        return
    names = ",".join(p.name[:80] for p in paths[:6]) or "none"
    _log(f"Drop kind={kind} files={len(paths)} pt={x},{y} names={names}")
    _send(
        sock,
        encode_msg(OP_DROP, paths=[str(p) for p in paths], x=int(x), y=int(y), kind=kind),
    )


def _run_overlay(
    sock: socket.socket,
    inbox: Path,
    parent_pid: int,
    *,
    owner_hwnd: int = 0,
    initial_geom: tuple[int, int, int, int] | None = None,
) -> int:
    """Win32 drop dock + board overlay + IDropTarget. ctypes OLE only in this process."""
    from ctypes import (
        WINFUNCTYPE,
        Structure,
        byref,
        c_byte,
        c_int,
        c_uint,
        c_void_p,
        sizeof,
        windll,
        wintypes,
    )

    from doccon.win_drop import _ensure_ole, register_hwnds

    if not _ensure_ole():
        _log("OleInitialize failed", level="WARN")
        return 5

    user32 = windll.user32
    kernel32 = windll.kernel32
    gdi32 = windll.gdi32
    LRESULT = c_void_p if sizeof(c_void_p) == 8 else c_int
    WNDPROC = WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    ptr_fn = user32.GetWindowLongPtrW if sizeof(c_void_p) == 8 else user32.GetWindowLongW
    set_ptr_fn = user32.SetWindowLongPtrW if sizeof(c_void_p) == 8 else user32.SetWindowLongW
    ptr_fn.restype = c_void_p
    ptr_fn.argtypes = [wintypes.HWND, c_int]
    set_ptr_fn.restype = c_void_p
    set_ptr_fn.argtypes = [wintypes.HWND, c_int, c_void_p]

    class WNDCLASSW(Structure):
        # ctypes.wintypes has no HCURSOR; HANDLE is the same width. Naming it
        # HCURSOR raised AttributeError here and killed every spawn (1.50-1.52).
        _fields_ = [
            ("style", c_uint),
            ("lpfnWndProc", WNDPROC),
            ("cbClsExtra", c_int),
            ("cbWndExtra", c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HANDLE),
            ("hCursor", wintypes.HANDLE),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
        ]

    class POINT(Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    class RECT(Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    class PAINTSTRUCT(Structure):
        _fields_ = [
            ("hdc", wintypes.HDC),
            ("fErase", wintypes.BOOL),
            ("rcPaint", RECT),
            ("fRestore", wintypes.BOOL),
            ("fIncUpdate", wintypes.BOOL),
            ("rgbReserved", c_byte * 32),
        ]

    class MSG(Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", wintypes.WPARAM),
            ("lParam", wintypes.LPARAM),
            ("time", wintypes.DWORD),
            ("pt", POINT),
        ]

    dock_hwnd = 0
    board_hwnd = 0
    last_hover = 0.0
    in_ole = False
    target_hold = []
    dock_brush = int(gdi32.CreateSolidBrush(DOCK_FILL) or 0)

    def _strip_transparent(hwnd: int) -> int:
        if not hwnd:
            return 0
        raw = int(ptr_fn(hwnd, GWL_EXSTYLE) or 0)
        if raw & WS_EX_TRANSPARENT:
            set_ptr_fn(hwnd, GWL_EXSTYLE, raw & ~WS_EX_TRANSPARENT)
            raw = int(ptr_fn(hwnd, GWL_EXSTYLE) or 0)
            _log(f"cleared WS_EX_TRANSPARENT hwnd={hwnd:#x}")
        return raw

    def _raise_targets() -> None:
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        if board_hwnd:
            user32.SetWindowPos(board_hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
        if dock_hwnd:
            user32.SetWindowPos(dock_hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)

    def _place(hwnd: int, box: tuple[int, int, int, int] | None, *, visible: bool) -> None:
        if not hwnd:
            return
        flags = SWP_NOACTIVATE | (SWP_SHOWWINDOW if visible and box else SWP_HIDEWINDOW)
        if box is None:
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 1, 1, flags)
            return
        x, y, w, h = box
        user32.SetWindowPos(hwnd, HWND_TOPMOST, int(x), int(y), max(int(w), 1), max(int(h), 1), flags)

    def apply_geom_box(x: int, y: int, w: int, h: int, visible: bool) -> None:
        if not visible:
            _place(dock_hwnd, None, visible=False)
            return
        width = max(int(w), 1)
        height = max(int(h), DOCK_HEIGHT)
        if width < MIN_OVERLAY_W:
            _log(f"geom skipped size={w}x{h}")
            return
        dock_box = (int(x), int(y), width, height)
        _place(dock_hwnd, dock_box, visible=True)
        _raise_targets()
        _log(f"geom dock={dock_box} visible=1")

    def forward_mouse(hwnd, msg, wparam, lparam) -> None:
        if in_ole:
            return
        user32.ShowWindow(hwnd, SW_HIDE)
        pt = POINT()
        user32.GetCursorPos(byref(pt))
        below = int(user32.WindowFromPoint(pt) or 0)
        user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
        _raise_targets()
        if not below or below in {int(hwnd), dock_hwnd, board_hwnd}:
            return
        screen = POINT(pt.x, pt.y)
        user32.ScreenToClient(below, byref(screen))
        packed = (int(screen.y) << 16) | (int(screen.x) & 0xFFFF)
        user32.PostMessageW(below, msg, wparam, packed)

    def paint_dock(hwnd) -> None:
        ps = PAINTSTRUCT()
        hdc = user32.BeginPaint(hwnd, byref(ps))
        if not hdc:
            return
        try:
            rect = RECT()
            user32.GetClientRect(hwnd, byref(rect))
            if dock_brush:
                user32.FillRect(hdc, byref(rect), dock_brush)
            gdi32.SetBkMode(hdc, 1)
            gdi32.SetTextColor(hdc, DOCK_TEXT)
            user32.DrawTextW(hdc, DOCK_CAPTION, -1, byref(rect), DT_CENTER | DT_VCENTER | DT_SINGLELINE)
        finally:
            user32.EndPaint(hwnd, byref(ps))

    def wndproc(hwnd, msg, wparam, lparam):
        code = int(msg)
        handle = int(hwnd)
        if code == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        if code == WM_PAINT and handle == dock_hwnd:
            with contextlib.suppress(Exception):
                paint_dock(hwnd)
            return 0
        if code in MOUSE_FORWARD and handle == board_hwnd:
            with contextlib.suppress(Exception):
                forward_mouse(hwnd, code, wparam, lparam)
            return 0
        if code == WM_MOUSEMOVE:
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    # Without argtypes ctypes marshals lparam as a 32-bit int, so any message
    # carrying a pointer or a negative handle raises
    # "ArgumentError: int too long to convert" inside the callback. That fired
    # on every dock message in 1.44-1.58 and spammed the helper's stderr.
    user32.DefWindowProcW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.DefWindowProcW.restype = LRESULT

    proc = WNDPROC(wndproc)
    hinst = kernel32.GetModuleHandleW(None)

    def register_class(name: str, brush: int) -> bool:
        wc = WNDCLASSW()
        wc.style = CS_DBLCLKS
        wc.lpfnWndProc = proc
        wc.hInstance = hinst
        wc.hbrBackground = c_void_p(brush or 0)
        wc.lpszClassName = name
        atom = user32.RegisterClassW(byref(wc))
        if atom:
            return True
        err = int(kernel32.GetLastError() or 0)
        if err == ERROR_CLASS_ALREADY_EXISTS:
            return True
        _log(f"RegisterClassW {name} failed err={err}", level="WARN")
        return False

    if not register_class(CLASS_DOCK, dock_brush):
        return 2

    def create(ex_style: int, class_name: str, title: str, w: int, h: int, parent) -> int:
        hwnd = int(
            user32.CreateWindowExW(
                ex_style,
                class_name,
                title,
                WS_POPUP | WS_VISIBLE,
                0,
                0,
                max(int(w), 1),
                max(int(h), 1),
                parent,
                None,
                hinst,
                None,
            )
            or 0
        )
        if not hwnd:
            _log(f"CreateWindowEx {class_name} failed parent={int(parent or 0):#x}", level="WARN")
            return 0
        style = _strip_transparent(hwnd)
        _log(f"{class_name} hwnd={hwnd:#x} ex={style:#x} ole={int(overlay_accepts_ole_input(style))}")
        return hwnd

    # Unowned TOPMOST dock is the IDropTarget HWND (owned popups can lose WindowFromPoint).
    dock_hwnd = create(overlay_ex_style(layered=False), CLASS_DOCK, "DocCon Drop PDFs", 480, DOCK_HEIGHT, None)
    if not dock_hwnd:
        _log("dock hwnd=0 CreateWindowExW failed", level="WARN")
        return 3
    _log(f"dock hwnd={dock_hwnd:#x} IDropTarget=1 owner={int(owner_hwnd or 0):#x}")
    _raise_targets()
    live_ex = int(ptr_fn(dock_hwnd, GWL_EXSTYLE) or 0)
    _log(
        f"dock created hwnd={dock_hwnd:#x} topmost={int(bool(live_ex & WS_EX_TOPMOST))} "
        f"transparent={int(bool(live_ex & WS_EX_TRANSPARENT))} visible={int(bool(user32.IsWindowVisible(dock_hwnd)))}"
    )

    def on_drop(sources, x, y) -> None:
        nonlocal in_ole
        in_ole = False
        kind = "outlook"
        if sources and all(item.path is not None for item in sources) and not any(item.data for item in sources):
            kind = "hdrop"
        _raise_targets()
        _stage_and_notify(sock, sources, x, y, inbox, kind)

    def on_hover(x, y) -> None:
        nonlocal last_hover, in_ole
        in_ole = True
        _raise_targets()
        now = time.monotonic()
        if now - last_hover < 0.05:
            return
        last_hover = now
        _send(sock, encode_msg(OP_HOVER, x=int(x), y=int(y)))

    def on_leave() -> None:
        nonlocal in_ole
        in_ole = False
        _send(sock, encode_msg(OP_LEAVE))

    def drop_gate(entering: bool) -> None:
        nonlocal in_ole
        in_ole = bool(entering)
        if entering:
            _raise_targets()

    _log("RegisterDragDrop on Drop PDFs dock (child only)")
    target = register_hwnds(
        [dock_hwnd],
        on_drop,
        hover=on_hover,
        leave=on_leave,
        schedule=lambda fn: fn(),
        drop_gate=drop_gate,
    )
    if target is None:
        _log(f"RegisterDragDrop hwnd={dock_hwnd:#x} FAILED (no S_OK)", level="WARN")
        return 4
    _log(f"RegisterDragDrop hwnd={dock_hwnd:#x} S_OK - dock accepts Outlook drags")
    target_hold.append(target)
    if initial_geom is not None:
        apply_geom_box(*initial_geom, True)
    else:
        _log("overlay waiting for geom")

    def apply_geom(msg: dict) -> None:
        try:
            x = int(msg.get("x") or 0)
            y = int(msg.get("y") or 0)
            w = max(int(msg.get("w") or 1), 1)
            h = max(int(msg.get("h") or 1), 1)
            visible = bool(msg.get("visible", True))
        except (TypeError, ValueError):
            return
        apply_geom_box(x, y, w, h, visible)

    buffer = b""
    msg = MSG()
    _send(
        sock,
        encode_msg(
            OP_READY,
            pid=os.getpid(),
            hwnd=dock_hwnd,
            dock_hwnd=dock_hwnd,
        ),
    )
    sock.setblocking(False)
    _log("overlay loop")
    try:
        while True:
            if not parent_alive(parent_pid):
                _log("parent gone")
                break
            while user32.PeekMessageW(byref(msg), None, 0, 0, PM_REMOVE):
                if int(msg.message) == WM_QUIT:
                    return 0
                user32.TranslateMessage(byref(msg))
                user32.DispatchMessageW(byref(msg))
            wait = 0.01 if in_ole else 0.05
            ready, _, _ = select.select([sock], [], [], wait)
            if not ready:
                continue
            try:
                chunk = sock.recv(65536)
            except BlockingIOError:
                continue
            except OSError as vis:
                _log(f"socket {vis}", level="WARN")
                break
            if not chunk:
                _log("parent socket closed")
                break
            messages, buffer = parse_frames(buffer + chunk)
            for incoming in messages:
                op = str(incoming.get("op") or "")
                if op == OP_QUIT:
                    _log("quit")
                    return 0
                if op == OP_GEOM:
                    apply_geom(incoming)
                if op == OP_HELLO:
                    _log("hello")
    finally:
        with contextlib.suppress(Exception):
            from doccon.win_drop import windll as ole_windll

            if ole_windll is not None:
                ole_windll.ole32.RevokeDragDrop(dock_hwnd)
        with contextlib.suppress(Exception):
            user32.DestroyWindow(dock_hwnd)
        if dock_brush:
            with contextlib.suppress(Exception):
                gdi32.DeleteObject(dock_brush)
    return 0


def _emit_paste_result(paths: list[Path], result: Path | None) -> None:
    from doccon.clip_paste import format_paste_result

    line = format_paste_result(paths)
    with contextlib.suppress(Exception):
        print(line, flush=True)
    if result is None:
        return
    with contextlib.suppress(Exception):
        dest = Path(result)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(line + "\n", encoding="utf-8")


def run_paste(inbox: Path, result: Path | None = None) -> int:
    """One-shot clipboard read. Stages PDFs, prints the result line, exits.

    No window, no socket, no message loop. The COM surface stays in this process.
    Frozen noconsole exe has no stdout — also write `--result` when the parent asks.
    """
    from doccon.clip_read import (
        merge_folder_paths,
        needs_folder_paste,
        paste_clipboard_into_folder,
        read_clipboard_sources,
    )

    inbox.mkdir(parents=True, exist_ok=True)
    try:
        sources = read_clipboard_sources(inbox)
        if needs_folder_paste(sources):
            _log("FileContents empty; Explorer-folder paste into inbox")
            sources = merge_folder_paths(sources, paste_clipboard_into_folder(inbox))
    except Exception as vis:
        _log(f"paste read {type(vis).__name__}: {vis}", level="WARN")
        _emit_paste_result([], result)
        return 0
    try:
        paths = stage_sources(list(sources), folder=inbox)
    except Exception as vis:
        _log(f"paste stage {type(vis).__name__}: {vis}", level="WARN")
        _emit_paste_result([], result)
        return 0
    names = ",".join(path.name[:80] for path in paths[:6]) or "none"
    _log(f"paste staged pdfs={len(paths)} names={names}")
    _emit_paste_result(paths, result)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="doccon.drop_host")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--inbox", type=str, default="")
    parser.add_argument("--parent-pid", type=int, default=0)
    parser.add_argument("--owner-hwnd", type=int, default=0)
    parser.add_argument("--geom", type=str, default="")
    parser.add_argument("--paste", action="store_true", help="read the clipboard once, then exit")
    parser.add_argument(
        "--result",
        type=str,
        default="",
        help="write the paste JSON line here (frozen noconsole has no stdout)",
    )
    args = parser.parse_args(argv)
    try:
        from doccon.diag import log_session_start

        log_session_start(step="drop_host")
    except Exception:
        pass
    if args.paste:
        return run_paste(
            Path(args.inbox) if args.inbox else inbox_dir(),
            result=Path(args.result) if str(args.result or "").strip() else None,
        )
    if not args.port:
        parser.error("--port is required unless --paste is used")
    _log(f"start pid={os.getpid()} port={args.port} parent={args.parent_pid}")
    inbox = Path(args.inbox) if args.inbox else inbox_dir()
    inbox.mkdir(parents=True, exist_ok=True)
    initial = parse_geom_arg(args.geom)
    try:
        sock = socket.create_connection(("127.0.0.1", int(args.port)), timeout=5)
    except OSError as vis:
        _log(f"connect {vis}", level="WARN")
        return 1
    try:
        if os.name != "nt":
            _send(sock, encode_msg(OP_READY, pid=os.getpid()))
            _send(sock, encode_msg(OP_LOG, level="WARN", msg="drop_host needs Windows"))
            time.sleep(0.2)
            return 0
        return _run_overlay(
            sock,
            inbox,
            int(args.parent_pid),
            owner_hwnd=int(args.owner_hwnd or 0),
            initial_geom=initial,
        )
    except Exception as vis:
        where = ""
        with contextlib.suppress(Exception):
            frame = traceback.extract_tb(vis.__traceback__)[-1]
            where = f" at {Path(frame.filename).name}:{frame.lineno} {frame.name}"
        detail = f"{type(vis).__name__}: {vis}{where}"
        _log(f"crash {detail}", level="WARN")
        with contextlib.suppress(Exception):
            _send(sock, encode_msg(OP_LOG, level="WARN", msg=detail))
        return 1
    finally:
        with contextlib.suppress(Exception):
            sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
