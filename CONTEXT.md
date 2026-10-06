# My Secretary

A Windows tray app for push-to-talk dictation. You hold a hotkey and speak, and the transcribed text is inserted at the caret of whatever app has focus. Nothing you say is kept.

## Language

**Dictation**:
One full cycle of holding the hotkey, speaking, releasing, and getting text inserted.
_Avoid_: session, recording (when the whole cycle is meant)

**Utterance**:
The audio captured between the press and the release of the Push-to-talk Hotkey during one Dictation. It exists only in memory.
_Avoid_: recording, clip, file

**Transcript**:
The raw English text the Transcription Model produces from one Utterance. It is discarded once it has been inserted.
_Avoid_: message, note, result

**Cleanup**:
A rewrite pass over a Transcript that fixes punctuation, capitalisation and filler words without changing what was said. It never answers or acts on the content.
_Avoid_: polish, AI edit, summarise

**Cleaned Text**:
What Cleanup returns, and therefore what normally gets inserted. If Cleanup is off or fails, the Transcript is inserted instead.
_Avoid_: final text, output

**Push-to-talk Hotkey**:
The global key chord you hold down to capture an Utterance. If another key is pressed during the hold, the Dictation is cancelled: the Utterance is thrown away unheard.
_Avoid_: shortcut, trigger

**Target**:
The window and caret position that has keyboard focus at the moment of Insertion, even if that is a different window from the one focused while speaking.
_Avoid_: cursor (ambiguous with the mouse pointer), destination

**Insertion**:
The act of placing the Cleaned Text (or the Transcript, when there is no Cleaned Text) at the Target as if you had typed it.
_Avoid_: paste (that is only one way of doing an Insertion)

**Transcription Model**:
The speech-to-text model on OpenRouter that turns an Utterance into a Transcript, picked by its OpenRouter model id.
_Avoid_: engine, AI

**Cleanup Model**:
The OpenRouter chat model that performs Cleanup.
_Avoid_: LLM, assistant
