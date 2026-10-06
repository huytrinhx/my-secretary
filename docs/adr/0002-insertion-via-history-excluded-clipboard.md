# Insertion uses a clipboard paste that is excluded from history, then puts the old clipboard back

Typing the Transcript character by character with `SendInput(KEYEVENTF_UNICODE)` never touches the clipboard. However, it is slow on long text, and some apps (IDEs, terminals) trigger autocomplete or auto-indent on each keystroke. A plain Ctrl+V is fast and faithful, but Windows Clipboard History (Win+V) and Cloud Clipboard would keep a copy, which goes against ADR-0001.

The decision is to paste through the clipboard as follows:
1. Snapshot the current clipboard.
2. Put the Transcript on the clipboard together with the registered formats `ExcludeClipboardContentFromMonitorProcessing`, `CanIncludeInClipboardHistory` (DWORD 0) and `CanUploadToCloudClipboard` (DWORD 0).
3. Send Ctrl+V.
4. After about 150 ms, restore the snapshot.

Unicode typing stays as a second Inserter adapter that you can switch to in settings for apps where paste misbehaves.
