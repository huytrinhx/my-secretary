import logging
import os
import subprocess
import sys
import threading

import pystray
from PIL import Image, ImageDraw

from my_secretary.dictation import State
from my_secretary.settings import SETTINGS_FILE, save_api_key

log = logging.getLogger(__name__)

STATE_COLOURS = {
    State.IDLE: "#8a8f98",
    State.RECORDING: "#e5484d",
    State.TRANSCRIBING: "#f5a524",
    State.CLEANING: "#f5a524",
    State.INSERTING: "#f5a524",
}
ERROR_MESSAGES = {
    "auth": "OpenRouter rejected the API key. Set it again from the tray menu.",
    "credits": "Your OpenRouter account is out of credits.",
    "rate_limit": "OpenRouter is rate-limiting requests. Try again in a moment.",
    "too_large": "That recording was too large to send.",
    "network": "Couldn't reach OpenRouter. Check your connection or VPN.",
    "tls": "Your network intercepts HTTPS with a certificate Windows doesn't trust. Ask IT to install its root certificate.",
    "server": "OpenRouter had a server error. Please try again.",
    "elevated_target": "Can't type into a window that runs as administrator.",
    "clipboard_busy": "The clipboard was busy. Please try again.",
    "microphone": "Microphone unavailable. Check it is connected and allowed in Windows privacy settings.",
    "unexpected": "Something went wrong. See app.log in %APPDATA%\\MySecretary.",
}


def _dot(colour: str) -> Image.Image:
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((6, 6, 58, 58), fill=colour)
    return image


ICONS = {state: _dot(colour) for state, colour in STATE_COLOURS.items()}


class Tray:
    def __init__(self, hotkey: str, test_connection):
        self._test_connection = test_connection
        self._icon = pystray.Icon(
            "my-secretary",
            ICONS[State.IDLE],
            f"My Secretary: hold {hotkey} to dictate",
            menu=pystray.Menu(
                pystray.MenuItem("Test connection", self._run_connection_test),
                pystray.MenuItem("Set OpenRouter API key…", self._set_api_key),
                pystray.MenuItem("Open settings file", open_settings_file),
                pystray.MenuItem("Restart (apply settings)", self._restart),
                pystray.MenuItem("Quit", lambda: self._icon.stop()),
            ),
        )

    def run(self, on_ready) -> None:
        """Blocks until Quit. on_ready runs on its own thread once the icon can show toasts."""

        def setup(icon):
            icon.visible = True
            on_ready()

        self._icon.run(setup=setup)

    def show_state(self, state: State) -> None:
        self._icon.icon = ICONS[state]

    def show_error(self, kind: str) -> None:
        self._icon.icon = _dot("#e5484d")
        self._icon.notify(ERROR_MESSAGES.get(kind, ERROR_MESSAGES["unexpected"]), "My Secretary")

    def show_connected(self) -> None:
        self._icon.notify("Connected to OpenRouter. Ready to dictate.", "My Secretary")

    def _run_connection_test(self) -> None:
        threading.Thread(target=self._test_connection, args=(True,), daemon=True).start()

    def _set_api_key(self) -> None:
        def ask():
            api_key = prompt_api_key()
            if api_key:
                save_api_key(api_key)
                self._restart()

        threading.Thread(target=ask, daemon=True).start()

    def _restart(self) -> None:
        subprocess.Popen(relaunch_command())
        self._icon.stop()


def open_settings_file() -> None:
    """Opens settings.json in the default app, or Notepad if the .json association is
    missing or broken (os.startfile then fails with "Application not found")."""
    try:
        os.startfile(SETTINGS_FILE)
    except OSError as error:
        log.info("no working .json association (%s), using Notepad", error.winerror)
        subprocess.Popen(["notepad.exe", str(SETTINGS_FILE)])


def relaunch_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "my_secretary"]


def prompt_api_key() -> str | None:
    """Small modal prompt. Runs its own Tk loop, so call it from one thread at a time."""
    import tkinter as tk
    from tkinter import simpledialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        value = simpledialog.askstring(
            "My Secretary", "OpenRouter API key (stored in Windows Credential Manager):",
            show="*", parent=root,
        )
    finally:
        root.destroy()
    return value.strip() if value and value.strip() else None
