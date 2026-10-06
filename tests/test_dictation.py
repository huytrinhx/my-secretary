from my_secretary.dictation import Dictation, State
from my_secretary.transcriber import TranscriptionError
from tests.fakes import DeferredRunner, FakeCleaner, FakeInserter, FakeRecorder, FakeTranscriber, run_now


def make_dictation(
    recorder=None,
    transcriber=None,
    inserter=None,
    run_in_background=run_now,
    on_error=None,
    on_state_change=None,
):
    inserter = inserter or FakeInserter()
    dictation = Dictation(
        recorder=recorder or FakeRecorder(),
        transcriber=transcriber or FakeTranscriber(),
        cleaner=FakeCleaner(),
        inserter=inserter,
        run_in_background=run_in_background,
        on_error=on_error or (lambda kind: None),
        on_state_change=on_state_change or (lambda state: None),
    )
    return dictation, inserter


def test_press_and_release_inserts_cleaned_text():
    dictation, inserter = make_dictation(transcriber=FakeTranscriber("um hello world"))

    dictation.press()
    dictation.release()

    assert inserter.inserted == ["cleaned(um hello world)"]
    assert dictation.state is State.IDLE


def test_accidental_tap_inserts_nothing():
    dictation, inserter = make_dictation(recorder=FakeRecorder(duration=0.2))

    dictation.press()
    dictation.release()

    assert inserter.inserted == []
    assert dictation.state is State.IDLE


def test_press_while_transcribing_is_ignored():
    runner = DeferredRunner()
    dictation, inserter = make_dictation(
        transcriber=FakeTranscriber("first"), run_in_background=runner
    )
    dictation.press()
    dictation.release()
    assert dictation.state is State.TRANSCRIBING

    dictation.press()
    dictation.release()
    runner.run_all()

    assert inserter.inserted == ["cleaned(first)"]


def test_silent_utterance_inserts_nothing():
    dictation, inserter = make_dictation(transcriber=FakeTranscriber("   \n"))

    dictation.press()
    dictation.release()

    assert inserter.inserted == []
    assert dictation.state is State.IDLE


def test_transcription_failure_is_reported_and_returns_to_idle():
    errors = []
    dictation, inserter = make_dictation(
        transcriber=FakeTranscriber(error=TranscriptionError("auth")), on_error=errors.append
    )

    dictation.press()
    dictation.release()

    assert errors == ["auth"]
    assert inserter.inserted == []
    assert dictation.state is State.IDLE


class BrokenInserter:
    def insert(self, text: str) -> None:
        raise RuntimeError("access denied")


def test_unexpected_failure_is_reported_and_returns_to_idle():
    errors = []
    dictation, _ = make_dictation(inserter=BrokenInserter(), on_error=errors.append)

    dictation.press()
    dictation.release()

    assert errors == ["unexpected"]
    assert dictation.state is State.IDLE


def test_every_state_change_is_announced():
    seen = []
    dictation, _ = make_dictation(on_state_change=seen.append)

    dictation.press()
    dictation.release()

    assert seen == [
        State.RECORDING,
        State.TRANSCRIBING,
        State.CLEANING,
        State.INSERTING,
        State.IDLE,
    ]


class UnpluggedRecorder(FakeRecorder):
    def start(self) -> None:
        raise OSError("no input device")


def test_missing_microphone_is_reported_and_stays_idle():
    errors = []
    dictation, inserter = make_dictation(recorder=UnpluggedRecorder(), on_error=errors.append)

    dictation.press()
    dictation.release()

    assert errors == ["microphone"]
    assert inserter.inserted == []
    assert dictation.state is State.IDLE


class MidwayUnpluggedRecorder(FakeRecorder):
    def stop(self):
        raise OSError("device removed")


def test_microphone_lost_while_recording_is_reported_and_returns_to_idle():
    errors = []
    dictation, _ = make_dictation(recorder=MidwayUnpluggedRecorder(), on_error=errors.append)

    dictation.press()
    dictation.release()

    assert errors == ["microphone"]
    assert dictation.state is State.IDLE


def test_cancelled_recording_is_discarded_without_transcribing():
    transcriber = FakeTranscriber(error=AssertionError("must not transcribe"))
    errors = []
    dictation, inserter = make_dictation(transcriber=transcriber, on_error=errors.append)

    dictation.press()
    dictation.cancel()
    dictation.release()

    assert inserter.inserted == []
    assert errors == []
    assert dictation.state is State.IDLE
