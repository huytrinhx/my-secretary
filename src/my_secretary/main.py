"""Composition root: wires the real adapters into a Dictation and runs the tray."""

import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from logging.handlers import RotatingFileHandler

from my_secretary.cleaner import OpenRouterCleaner, PassthroughCleaner
from my_secretary.dictation import Dictation
from my_secretary.hotkey import HotkeyListener
from my_secretary.net import check_connection, make_http_client, warm_up
from my_secretary.inserter import ClipboardPasteInserter, UnicodeTypingInserter
from my_secretary.recorder import MicRecorder
from my_secretary.settings import APP_DIR, load_api_key, load_settings, save_api_key
from my_secretary.transcriber import OpenRouterTranscriber
from my_secretary.tray import Tray, prompt_api_key

log = logging.getLogger("my_secretary")


def main() -> None:
    _configure_logging()
    settings = load_settings()
    api_key = load_api_key()
    if not api_key:
        api_key = prompt_api_key()
        if not api_key:
            sys.exit("An OpenRouter API key is required.")
        save_api_key(api_key)

    http = make_http_client()
    cleaner = (
        OpenRouterCleaner(http, api_key, settings.cleanup_model)
        if settings.cleanup_enabled
        else PassthroughCleaner()
    )
    inserter = UnicodeTypingInserter() if settings.inserter == "type" else ClipboardPasteInserter()
    worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dictation")

    def test_connection(announce_success: bool = False) -> None:
        kind = check_connection(http, api_key)
        if kind:
            tray.show_error(kind)
        elif announce_success:
            tray.show_connected()

    tray = Tray(settings.hotkey, test_connection)

    def on_error(kind: str) -> None:
        log.warning("dictation error: %s", kind)
        tray.show_error(kind)

    dictation = Dictation(
        recorder=MicRecorder(settings.microphone),
        transcriber=OpenRouterTranscriber(http, api_key, settings.transcription_model),
        cleaner=cleaner,
        inserter=inserter,
        run_in_background=worker.submit,
        on_error=on_error,
        on_state_change=tray.show_state,
    )
    def press() -> None:
        warm_up(http, api_key)  # runs while you speak
        dictation.press()

    hotkey = HotkeyListener(settings.hotkey, press, dictation.release, dictation.cancel)
    hotkey.start()
    log.info("ready: hotkey=%s model=%s cleanup=%s", settings.hotkey,
             settings.transcription_model, settings.cleanup_enabled and settings.cleanup_model)
    try:
        tray.run(on_ready=test_connection)  # setup check on every launch
    finally:
        hotkey.stop()
        worker.shutdown(wait=False, cancel_futures=True)
        http.close()


def _configure_logging() -> None:
    """Events and timings only. Nothing that holds audio or text is ever logged (ADR-0001)."""
    APP_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(APP_DIR / "app.log", maxBytes=512_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    logging.getLogger("httpx").setLevel(logging.WARNING)
