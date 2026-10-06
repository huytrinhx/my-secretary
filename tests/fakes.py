from my_secretary.recorder import Utterance


class FakeRecorder:
    def __init__(self, duration: float = 2.0):
        self.duration = duration

    def start(self) -> None:
        pass

    def stop(self) -> Utterance:
        return Utterance(audio=b"fake-flac", mime="audio/flac", duration=self.duration)


class FakeTranscriber:
    def __init__(self, transcript: str = "um hello world", error: Exception | None = None):
        self.transcript = transcript
        self.error = error

    def transcribe(self, utterance: Utterance) -> str:
        if self.error:
            raise self.error
        return self.transcript


class FakeCleaner:
    def clean(self, transcript: str) -> str:
        return f"cleaned({transcript})"


class FakeInserter:
    def __init__(self):
        self.inserted: list[str] = []

    def insert(self, text: str) -> None:
        self.inserted.append(text)


def run_now(job):
    job()


class DeferredRunner:
    """Holds background jobs until the test decides to run them."""

    def __init__(self):
        self.jobs = []

    def __call__(self, job):
        self.jobs.append(job)

    def run_all(self):
        while self.jobs:
            self.jobs.pop(0)()
