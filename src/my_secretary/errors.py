class DictationError(Exception):
    """A failure the user should hear about, named by kind. Never carries Transcript text."""

    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind
