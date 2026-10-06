import logging
import time
from enum import Enum

from my_secretary.errors import DictationError

log = logging.getLogger(__name__)

MIN_UTTERANCE_SECONDS = 0.3


class State(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    CLEANING = "cleaning"
    INSERTING = "inserting"


class Dictation:
    """One push-to-talk cycle at a time: record, transcribe, clean up, insert."""

    def __init__(
        self,
        recorder,
        transcriber,
        cleaner,
        inserter,
        run_in_background,
        on_error,
        on_state_change,
    ):
        self._recorder = recorder
        self._transcriber = transcriber
        self._cleaner = cleaner
        self._inserter = inserter
        self._run_in_background = run_in_background
        self._on_error = on_error
        self._on_state_change = on_state_change
        self._state = State.IDLE

    @property
    def state(self) -> State:
        return self._state

    @state.setter
    def state(self, state: State) -> None:
        self._state = state
        self._on_state_change(state)

    def press(self) -> None:
        if self.state is not State.IDLE:
            return
        try:
            self._recorder.start()
        except Exception:
            self._on_error("microphone")
            return
        self.state = State.RECORDING

    def release(self) -> None:
        if self.state is not State.RECORDING:
            return
        try:
            utterance = self._recorder.stop()
        except Exception:
            self.state = State.IDLE
            self._on_error("microphone")
            return
        if utterance.duration < MIN_UTTERANCE_SECONDS:
            self.state = State.IDLE
            return
        self.state = State.TRANSCRIBING
        self._run_in_background(lambda: self._finish(utterance))

    def cancel(self) -> None:
        """Abandon the current Utterance (the hotkey turned out to be another shortcut)."""
        if self.state is not State.RECORDING:
            return
        try:
            self._recorder.stop()  # discarded unheard
        except Exception:
            pass
        self.state = State.IDLE

    def _finish(self, utterance) -> None:
        try:
            self._transcribe_clean_insert(utterance)
        except DictationError as error:
            self._on_error(error.kind)
        except Exception:
            log.exception("dictation failed")
            self._on_error("unexpected")
        finally:
            self.state = State.IDLE

    def _transcribe_clean_insert(self, utterance) -> None:
        started = time.perf_counter()
        transcript = self._transcriber.transcribe(utterance)
        transcribed = time.perf_counter()
        if not transcript.strip():
            return
        self.state = State.CLEANING
        text = self._cleaner.clean(transcript)
        cleaned = time.perf_counter()
        self.state = State.INSERTING
        self._inserter.insert(text)
        log.info(
            "dictation: audio=%.1fs transcribe=%.2fs cleanup=%.2fs insert=%.2fs",
            utterance.duration, transcribed - started, cleaned - transcribed,
            time.perf_counter() - cleaned,
        )
