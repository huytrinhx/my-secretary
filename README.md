# My Secretary

Push-to-talk dictation for Windows. Hold **Ctrl+Alt** and speak, then let go. Your words are transcribed by OpenRouter, cleaned up, and pasted wherever your caret is. Nothing you say is saved (see [ADR-0001](docs/adr/0001-ephemeral-by-design.md)).

Design: [docs/design.md](docs/design.md) · Glossary: [CONTEXT.md](CONTEXT.md)

## First run

1. Start `my-secretary.exe` (or `uv run python -m my_secretary`).
2. Paste your OpenRouter API key when asked. It is stored in Windows Credential Manager.
3. A grey dot appears in the tray. Hold the hotkey, speak, and release.

On every launch the app checks that it can reach OpenRouter and that the key works. Run the same check from Tray → *Test connection*. On a corporate network that inspects HTTPS (e.g. Zscaler), the app trusts the certificates already installed in Windows, so there is nothing to export.

Tray colours: grey = idle, red = recording, amber = transcribing and cleaning.

**Privacy on OpenRouter's side:** in OpenRouter → Settings → Privacy, turn off prompt/response logging.

## Settings

Tray → *Open settings file*, edit it, then Tray → *Restart (apply settings)*.

| Key | Default | Notes |
|---|---|---|
| `hotkey` | `ctrl+alt` | Modifiers only (pressing another key mid-hold cancels, so Ctrl+Alt+T and similar shortcuts still work), or modifiers + one key, e.g. `ctrl+alt+space` |
| `transcription_model` | `openai/whisper-large-v3-turbo` | Any model id that lists `transcription` as an output modality |
| `cleanup_enabled` | `true` | `false` inserts the raw Transcript |
| `cleanup_model` | `inception/mercury-2.5` | Compare models with `scripts/bench_cleanup.py` |
| `inserter` | `paste` | `type` types out keystrokes and never touches the clipboard |
| `microphone` | `null` | Device name or index. `null` uses the Windows default |

The log is at `%APPDATA%\MySecretary\app.log`. It holds events and timings only.

## Development

```sh
uv sync
uv run pytest                                   # Dictation behaviour tests
uv run python -m my_secretary                   # run from source
uv run python scripts/bench_cleanup.py          # Cleanup Model latency/quality bake-off
uv run pyinstaller --noconfirm --onefile --noconsole --name my-secretary --paths src src/my_secretary/__main__.py
```

The `.exe` lands in `dist/`.

## Manual checks (not automated, by decision)

- [ ] Dictate into Notepad, VS Code, a browser text box and Windows Terminal.
- [ ] Win+V history does not show the dictated text, and what you had copied before is still on the clipboard.
- [ ] Switch windows while it is transcribing: the text lands in the new window.
- [ ] Dictating into an admin window shows the "runs as administrator" toast.
- [ ] Unplugging the mic shows the microphone toast and the next dictation works after you plug it back in.
- [ ] Ctrl+Alt+T (or another Ctrl+Alt shortcut) still works and inserts nothing.
- [ ] Releasing Ctrl+Alt in Notepad does not focus the menu bar.
- [ ] After Ctrl+Alt+Del → Cancel, or Win+L → unlock, the hotkey still works.
- [ ] AltGr characters on an international layout still type normally.
- [ ] The `.exe` starts on a clean user profile (no Python installed).
