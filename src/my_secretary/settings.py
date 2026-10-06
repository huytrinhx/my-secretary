"""User settings (no content, ever: ADR-0001) and the OpenRouter API key in Credential Manager."""

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import keyring

APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "MySecretary"
SETTINGS_FILE = APP_DIR / "settings.json"
KEYRING_SERVICE = "my-secretary"
KEYRING_USER = "openrouter"


@dataclass
class Settings:
    hotkey: str = "ctrl+alt"
    transcription_model: str = "openai/whisper-large-v3-turbo"
    cleanup_enabled: bool = True
    cleanup_model: str = "inception/mercury-2.5"
    inserter: str = "paste"  # "paste" or "type"
    microphone: str | None = None  # None means the Windows default input


def load_settings() -> Settings:
    """Reads settings.json, writing the defaults on first run so there is a file to edit."""
    if not SETTINGS_FILE.exists():
        save_settings(Settings())
    stored = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    known = {f.name for f in fields(Settings)}
    return Settings(**{k: v for k, v in stored.items() if k in known})


def save_settings(settings: Settings) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")


def load_api_key() -> str | None:
    return keyring.get_password(KEYRING_SERVICE, KEYRING_USER)


def save_api_key(api_key: str) -> None:
    keyring.set_password(KEYRING_SERVICE, KEYRING_USER, api_key)
