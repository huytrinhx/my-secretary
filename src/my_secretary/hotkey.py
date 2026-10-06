import ctypes
from concurrent.futures import ThreadPoolExecutor

from pynput import keyboard

from my_secretary.inserter import tap_key

MODIFIER_ALIASES = {
    "ctrl": {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r},
    "alt": {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr},
    "shift": {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r},
    "win": {keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r},
}
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0100, 0x0101, 0x0104, 0x0105
LLKHF_INJECTED = 0x10
# An unassigned virtual key. Tapping it while Alt/Win is held stops Windows from treating
# the later Alt/Win release as "open the menu bar / Start menu" (same trick as AutoHotkey).
VK_MASK = 0xE8


class HotkeyListener:
    """Turns a held key chord into on_press()/on_release() calls, on their own thread
    (Windows drops low-level keyboard hooks that respond slowly).

    Two shapes of chord:
    - modifiers + key, e.g. "ctrl+alt+space": the key is swallowed so it never types.
    - modifiers only, e.g. "ctrl+alt": since that is also the start of other shortcuts,
      pressing any other key during the hold calls on_cancel() instead of on_release(),
      and nothing restarts until the chord is fully let go.
    """

    def __init__(self, chord: str, on_press, on_release, on_cancel):
        *modifiers, last = [part.strip().lower() for part in chord.split("+")]
        if last in MODIFIER_ALIASES:
            modifiers, last = modifiers + [last], None
        self._modifier_groups = [MODIFIER_ALIASES[name] for name in modifiers]
        self._chord_keys = set().union(*self._modifier_groups)
        self._trigger_vk = _vk_of(last) if last else None
        self._on_press = on_press
        self._on_release = on_release
        self._on_cancel = on_cancel
        self._callbacks = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hotkey")
        self._held: set = set()
        self._active = False
        self._spoiled = False
        self._listener = keyboard.Listener(
            on_press=self._key_down,
            on_release=self._key_up,
            win32_event_filter=self._filter,
        )

    def start(self) -> None:
        self._listener.start()

    def stop(self) -> None:
        self._listener.stop()
        self._callbacks.shutdown(wait=False)

    def _modifiers_held(self) -> bool:
        return all(group & self._held for group in self._modifier_groups)

    def _foreign_keys_held(self) -> bool:
        return bool(self._held - self._chord_keys)

    def _activate(self) -> None:
        self._active = True
        self._callbacks.submit(self._on_press)
        if self._modifier_groups and self._chord_keys & (MODIFIER_ALIASES["alt"] | MODIFIER_ALIASES["win"]):
            self._callbacks.submit(tap_key, VK_MASK)

    def _deactivate(self, callback) -> None:
        self._active = False
        self._callbacks.submit(callback)

    def _key_down(self, key) -> None:
        self._forget_released_keys()
        self._held.add(key)
        if self._trigger_vk is not None:
            return  # trigger mode is handled in _filter
        if key in self._chord_keys:
            if not self._active and not self._spoiled and self._modifiers_held() and not self._foreign_keys_held():
                self._activate()
        elif self._active:
            self._spoiled = True
            self._deactivate(self._on_cancel)
        elif self._modifiers_held():
            self._spoiled = True

    def _key_up(self, key) -> None:
        self._held.discard(key)
        if self._active and not self._modifiers_held():
            self._deactivate(self._on_release)
        if not self._held & self._chord_keys:
            self._spoiled = False

    def _forget_released_keys(self) -> None:
        """Key-ups are never delivered while the secure desktop is up (Ctrl+Alt+Del, Win+L),
        so drop any key Windows says is no longer physically down."""
        self._held = {key for key in self._held if _is_down(key)}
        if not self._held & self._chord_keys:
            self._active, self._spoiled = False, False

    def _filter(self, msg, data) -> bool:
        if data.flags & LLKHF_INJECTED:
            return False  # our own Ctrl+V / mask key: let it through, but don't track it
        if self._trigger_vk is None or data.vkCode != self._trigger_vk:
            return True
        if msg in (WM_KEYDOWN, WM_SYSKEYDOWN) and (self._active or self._modifiers_held()):
            if not self._active:  # ignore auto-repeat
                self._activate()
            self._listener.suppress_event()
        if msg in (WM_KEYUP, WM_SYSKEYUP) and self._active:
            self._deactivate(self._on_release)
            self._listener.suppress_event()
        return True


def _is_down(key) -> bool:
    vk = key.value.vk if isinstance(key, keyboard.Key) else key.vk
    return vk is None or bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)


def _vk_of(name: str) -> int:
    if len(name) == 1:
        return ord(name.upper())
    return keyboard.Key[name].value.vk
