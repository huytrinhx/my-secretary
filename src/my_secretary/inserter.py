"""Insertion into the Target (whatever has focus right now), Windows only. See ADR-0002."""

import ctypes
import time
from ctypes import wintypes

from my_secretary.errors import DictationError

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_CONTROL, VK_MENU, VK_SHIFT, VK_LWIN, VK_RWIN, VK_RETURN, VK_V = (
    0x11, 0x12, 0x10, 0x5B, 0x5C, 0x0D, 0x56,
)
# Clipboard formats that are GDI handles rather than global memory; they cannot be
# snapshotted byte-for-byte. Windows re-synthesises CF_BITMAP from CF_DIB on restore.
GDI_FORMATS = {2, 3, 9, 14, 0x0082, 0x0083, 0x008E}
PASTE_SETTLE_SECONDS = 0.3
MODIFIER_WAIT_SECONDS = 2.0


class InsertionError(DictationError):
    """kind is one of: elevated_target, clipboard_busy."""


class ULONG_PTR(ctypes.c_size_t):
    pass


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.EnumClipboardFormats.argtypes = [wintypes.UINT]
user32.EnumClipboardFormats.restype = wintypes.UINT
user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
user32.RegisterClipboardFormatW.restype = wintypes.UINT
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetAsyncKeyState.restype = ctypes.c_short
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalSize.restype = ctypes.c_size_t
kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
advapi32.GetTokenInformation.argtypes = [
    wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
]


class ClipboardPasteInserter:
    """Puts the text on the clipboard (excluded from Win+V history and Cloud Clipboard),
    sends Ctrl+V, then restores whatever was on the clipboard before."""

    def insert(self, text: str) -> None:
        _refuse_elevated_target()
        _wait_for_modifiers_released()
        snapshot = _snapshot_clipboard()
        _set_clipboard({CF_UNICODETEXT: _utf16z(text), **_exclusion_formats()})
        _send_keys([(VK_CONTROL, False), (VK_V, False), (VK_V, True), (VK_CONTROL, True)])
        time.sleep(PASTE_SETTLE_SECONDS)
        _set_clipboard({**snapshot, **_exclusion_formats()} if snapshot else {})


class UnicodeTypingInserter:
    """Types the text as Unicode keystrokes. Never touches the clipboard; slower."""

    def insert(self, text: str) -> None:
        _refuse_elevated_target()
        _wait_for_modifiers_released()
        inputs = []
        for char in text.replace("\r\n", "\n"):
            if char == "\n":
                inputs += [_vk_input(VK_RETURN, False), _vk_input(VK_RETURN, True)]
                continue
            for unit in _utf16_units(char):
                inputs += [_unicode_input(unit, False), _unicode_input(unit, True)]
        _send(inputs)


def tap_key(vk: int) -> None:
    """Press and release one virtual key."""
    _send_keys([(vk, False), (vk, True)])


def _refuse_elevated_target() -> None:
    """UIPI silently drops input sent to elevated windows, so detect it up front."""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
    if _is_elevated(pid.value) and not _is_elevated(None):
        raise InsertionError("elevated_target")


def _is_elevated(pid: int | None) -> bool:
    PROCESS_QUERY_LIMITED_INFORMATION, TOKEN_QUERY, TOKEN_ELEVATION = 0x1000, 0x0008, 20
    process = kernel32.GetCurrentProcess() if pid is None else kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, pid
    )
    if not process:
        # We cannot even query it, which in practice means it runs elevated.
        return pid is not None
    token = wintypes.HANDLE()
    try:
        if not advapi32.OpenProcessToken(process, TOKEN_QUERY, ctypes.byref(token)):
            return pid is not None
        elevation, size = wintypes.DWORD(), wintypes.DWORD()
        advapi32.GetTokenInformation(
            token, TOKEN_ELEVATION, ctypes.byref(elevation), 4, ctypes.byref(size)
        )
        return bool(elevation.value)
    finally:
        if token:
            kernel32.CloseHandle(token)
        if pid is not None:
            kernel32.CloseHandle(process)


def _wait_for_modifiers_released() -> None:
    """If the user still holds Ctrl/Alt/Shift/Win, Ctrl+V would become another shortcut."""
    deadline = time.monotonic() + MODIFIER_WAIT_SECONDS
    while time.monotonic() < deadline:
        if not any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in (VK_CONTROL, VK_MENU, VK_SHIFT, VK_LWIN, VK_RWIN)):
            return
        time.sleep(0.02)


def _exclusion_formats() -> dict[int, bytes]:
    zero = (0).to_bytes(4, "little")
    return {
        user32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing"): b"\0",
        user32.RegisterClipboardFormatW("CanIncludeInClipboardHistory"): zero,
        user32.RegisterClipboardFormatW("CanUploadToCloudClipboard"): zero,
    }


def _snapshot_clipboard() -> dict[int, bytes]:
    snapshot = {}
    with _open_clipboard():
        fmt = user32.EnumClipboardFormats(0)
        while fmt:
            if fmt not in GDI_FORMATS:
                handle = user32.GetClipboardData(fmt)
                if handle:
                    size = kernel32.GlobalSize(handle)
                    pointer = kernel32.GlobalLock(handle)
                    if pointer:
                        snapshot[fmt] = ctypes.string_at(pointer, size)
                        kernel32.GlobalUnlock(handle)
            fmt = user32.EnumClipboardFormats(fmt)
    return snapshot


def _set_clipboard(formats: dict[int, bytes]) -> None:
    with _open_clipboard():
        user32.EmptyClipboard()
        for fmt, data in formats.items():
            handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, max(len(data), 1))
            pointer = kernel32.GlobalLock(handle)
            ctypes.memmove(pointer, data, len(data))
            kernel32.GlobalUnlock(handle)
            user32.SetClipboardData(fmt, handle)  # the clipboard now owns the memory


class _open_clipboard:
    def __enter__(self):
        for _ in range(20):  # another app may briefly hold it
            if user32.OpenClipboard(None):
                return self
            time.sleep(0.025)
        raise InsertionError("clipboard_busy")

    def __exit__(self, *exc):
        user32.CloseClipboard()


def _utf16z(text: str) -> bytes:
    return text.encode("utf-16-le") + b"\0\0"


def _utf16_units(char: str) -> list[int]:
    data = char.encode("utf-16-le")
    return [int.from_bytes(data[i : i + 2], "little") for i in range(0, len(data), 2)]


def _vk_input(vk: int, up: bool) -> INPUT:
    return INPUT(INPUT_KEYBOARD, _INPUTUNION(ki=KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, 0)))


def _unicode_input(unit: int, up: bool) -> INPUT:
    flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0)
    return INPUT(INPUT_KEYBOARD, _INPUTUNION(ki=KEYBDINPUT(0, unit, flags, 0, 0)))


def _send_keys(keys: list[tuple[int, bool]]) -> None:
    _send([_vk_input(vk, up) for vk, up in keys])


def _send(inputs: list[INPUT]) -> None:
    array = (INPUT * len(inputs))(*inputs)
    user32.SendInput(len(inputs), array, ctypes.sizeof(INPUT))
