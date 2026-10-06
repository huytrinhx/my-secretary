import io
import threading
from dataclasses import dataclass

import numpy as np
import sounddevice as sd
import soundfile as sf

SAMPLE_RATE = 16_000
MAX_SECONDS = 10 * 60


@dataclass(frozen=True)
class Utterance:
    """Audio captured between press and release. Lives only in memory (ADR-0001)."""

    audio: bytes
    mime: str
    duration: float


class MicRecorder:
    """Captures 16 kHz mono from the microphone and hands back an in-memory FLAC Utterance.
    Audio beyond MAX_SECONDS is dropped; the Dictation still completes on release."""

    def __init__(self, device: int | str | None = None):
        self._device = device
        self._chunks: list[np.ndarray] = []
        self._frames = 0
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None

    def start(self) -> None:
        self._chunks = []
        self._frames = 0
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            device=self._device,
            callback=self._on_audio,
        )
        self._stream.start()

    def stop(self) -> Utterance:
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        with self._lock:
            chunks, self._chunks = self._chunks, []
            frames = self._frames
        samples = np.concatenate(chunks) if chunks else np.zeros((0, 1), dtype="int16")
        buffer = io.BytesIO()
        sf.write(buffer, samples, SAMPLE_RATE, format="FLAC", subtype="PCM_16")
        return Utterance(audio=buffer.getvalue(), mime="audio/flac", duration=frames / SAMPLE_RATE)

    def _on_audio(self, indata, frames, time, status) -> None:
        with self._lock:
            room = SAMPLE_RATE * MAX_SECONDS - self._frames
            if room <= 0:
                return
            self._chunks.append(indata[:room].copy())
            self._frames += min(frames, room)
