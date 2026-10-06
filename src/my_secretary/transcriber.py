import logging

import httpx

from my_secretary.errors import DictationError
from my_secretary.net import OPENROUTER_URL, transport_error_kind
from my_secretary.recorder import Utterance

log = logging.getLogger(__name__)


class TranscriptionError(DictationError):
    """kind is one of: auth, credits, rate_limit, too_large, tls, network, server."""


class OpenRouterTranscriber:
    """Turns an Utterance into an English Transcript via OpenRouter /audio/transcriptions."""

    def __init__(self, client: httpx.Client, api_key: str, model: str, timeout: float = 30.0):
        self._client = client
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def transcribe(self, utterance: Utterance) -> str:
        try:
            return self._attempt(utterance)
        except TranscriptionError as error:
            if error.kind not in ("network", "server"):
                raise
        return self._attempt(utterance)

    def _attempt(self, utterance: Utterance) -> str:
        try:
            response = self._client.post(
                f"{OPENROUTER_URL}/audio/transcriptions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                data={"model": self._model, "language": "en"},
                files={"file": ("utterance.flac", utterance.audio, utterance.mime)},
                timeout=self._timeout,
            )
        except httpx.TransportError as error:
            log.warning("transcription transport error: %s", type(error).__name__)
            raise TranscriptionError(transport_error_kind(error)) from None
        if response.status_code != 200:
            raise TranscriptionError(_kind_for_status(response.status_code))
        return response.json()["text"]


def _kind_for_status(status: int) -> str:
    if status in (401, 403):
        return "auth"
    if status == 402:
        return "credits"
    if status == 413:
        return "too_large"
    if status == 429:
        return "rate_limit"
    return "server"
