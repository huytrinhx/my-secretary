# Utterances and Transcripts are never persisted

The app is a privacy tool, so no Utterance or Transcript is ever written anywhere the app controls. Audio is captured into memory, encoded to FLAC in a `BytesIO`, sent to OpenRouter, and dropped. The Transcript is sent to OpenRouter once more for Cleanup, and then dropped as well. No temp files are written, the app keeps no history, and logs record only events and timings, never audio or text. The clipboard is the one place the text passes through, so ADR-0002 deals with it. The OpenRouter API key goes in Windows Credential Manager (`keyring`), because it is a secret and not message content.

## Consequences

- When a request fails, the Utterance is lost and you have to say it again. A "retry last" feature would break this rule.
- The rule stops at our process. OpenRouter and the upstream providers (for both the Transcription Model and the Cleanup Model) fall under their own retention policies. To get as close as possible, turn off prompt logging in the OpenRouter privacy settings and choose a Transcription Model whose provider offers zero data retention.
