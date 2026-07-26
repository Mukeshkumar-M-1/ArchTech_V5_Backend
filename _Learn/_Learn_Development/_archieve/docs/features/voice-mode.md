# VOICE_MODE — Voice Input

> Feature Flag: `FEATURE_VOICE_MODE=1`
> Implementation Status: Fully operational (Dual backends: Anthropic STT and Doubao ASR).
> Reference Count: 46

## I. Feature Overview

`VOICE_MODE` implements "Push-to-Talk" voice input. Users hold the spacebar to record, and the audio is streamed to an STT (Speech-to-Text) backend, with real-time transcriptions displayed in the terminal. Two backends are supported:

- **Anthropic STT (Default)**: Streams audio via WebSocket to the Nova 3 endpoint; requires Anthropic OAuth.
- **Doubao ASR**: Uses the `doubaoime-asr` package via an AsyncGenerator protocol; requires an independent credentials file but does not require Anthropic OAuth.

### Core Features

- **Push-to-Talk**: Long-press spacebar to record; release to automatically send.
- **Streaming Transcription**: Displays interim transcription results in real-time during recording.
- **Seamless Integration**: Transcribed text is directly submitted as a user message.
- **Backend Switching**: Select the STT backend via `/voice` command parameters (persisted in `settings.json`).

## II. User Interaction

| Action | Behavior |
| :--- | :--- |
| **Long-press Space** | Starts recording; displays recording status. |
| **Release Space** | Stops recording; automatically submits the transcription. |
| **`/voice`** | Toggles voice mode (defaults to Anthropic backend). |
| **`/voice doubao`** | Enables voice mode using the Doubao ASR backend. |
| **`/voice anthropic`** | Switches back to the Anthropic STT backend. |

### UI Feedback

- **Recording Indicator**: Displays a red/pulsing animation during recording.
- **Interim Transcripts**: Shows real-time text recognition during the recording process.
- **Final Transcript**: Replaces interim results once recording stops.

## III. Implementation Architecture

### 3.1 Gating Logic

File: `src/voice/voiceModeEnabled.ts`

Two levels of check functions:
- `isVoiceModeEnabled()`: Requires `hasVoiceAuth()` and `isVoiceGrowthBookEnabled()` (for Anthropic backend).
- `isVoiceAvailable()`: General availability check (does not require OAuth, used for Doubao).

1.  **Feature Flag**: `feature('VOICE_MODE')` — Compile-time/runtime toggle.
2.  **GrowthBook Kill-Switch**: `tengu_amber_quartz_disabled` (defaults to `false`, meaning not disabled).
3.  **Auth Check (Anthropic only)**: Requires an Anthropic OAuth token (not just an API key).
4.  **Provider Check**: The `voiceProvider` setting determines the backend; the Doubao backend skips the OAuth check.

### 3.2 Core Modules

| Module | Responsibility |
| :--- | :--- |
| `src/voice/voiceModeEnabled.ts` | Three-layer gating logic (Feature flag, GrowthBook, and Auth). |
| `src/hooks/useVoice.ts` | React hook managing recording state and backend connections. |
| `src/services/voiceStreamSTT.ts` | Anthropic WebSocket streaming STT implementation. |
| `src/services/doubaoSTT.ts` | Doubao ASR adapter (AsyncGenerator → `VoiceStreamConnection`). |
| `src/commands/voice/voice.ts` | `/voice` command implementation for backend selection and persistence. |
| `src/hooks/useVoiceEnabled.ts` | State hook that determines whether to skip OAuth checks based on the provider. |

### 3.3 Data Flow

#### Anthropic Backend
```
User presses Spacebar
      │
      ▼
useVoice hook activated
      │
      ▼
Native macOS Audio / SoX starts recording
      │
      ▼
WebSocket connects to Anthropic STT endpoint
      │
      ├──→ Interim transcription → Real-time display
      │
      ▼
User releases Spacebar
      │
      ▼
Stop recording; wait for final transcription
      │
      ▼
Transcript → Inserted into input box → Auto-submit
```

#### Doubao ASR Backend
```
User presses Spacebar
      │
      ▼
useVoice hook activated (voiceProvider === 'doubao')
      │
      ▼
Native macOS Audio / SoX starts recording
      │
      ▼
connectDoubaoStream() creates AudioChunkQueue + VoiceStreamConnection
      │
      ├──→ onReady triggers immediately (no handshake wait)
      │
      ▼
Audio data passed via AudioChunkQueue to transcribeRealtime()
      │
      ├──→ INTERIM_RESULT → Real-time interim display
      ├──→ FINAL_RESULT   → Final transcription display
      │
      ▼
User releases Spacebar
      │
      ▼
finalize() returns immediately (Doubao results already received)
      │
      ▼
Transcript → Inserted into input box → Auto-submit
```

### 3.4 Audio Recording

Two audio backends are supported (shared by both STT backends):
- **Native macOS Audio**: Preferred for low latency.
- **SoX (Sound eXchange)**: Cross-platform fallback.

### 3.5 Doubao ASR Adapter Design

File: `src/services/doubaoSTT.ts`

Uses the Adapter pattern to bridge the `doubaoime-asr` AsyncGenerator protocol to the `VoiceStreamConnection` interface.

- **`AudioChunkQueue`**: A push-based asynchronous queue implementing `AsyncIterable<Uint8Array>`. `push(chunk)` queues data, and `push(null)` signals the end of the stream.
- **`connectDoubaoStream()`**:
  - Dynamically imports `doubaoime-asr` (optional dependency).
  - Loads credentials from `~/.claude/tts/doubao/credentials.json`.
  - Triggers `onReady` immediately to avoid deadlocks with audio buffering.
  - `finalize()` returns immediately since results are processed during recording.

### 3.6 Backend Selection Logic

File: `src/hooks/useVoice.ts`

The `voiceProvider` setting determines whether to use `connectDoubaoStream` or `connectVoiceStream`.
- For Doubao, the system skips the `getVoiceKeyterms()` call and Focus Mode logic.

## IV. Key Design Decisions

1.  **Dual-Backend Coexistence**: Doubao is implemented as an independent adapter alongside the Anthropic backend, switched via the `voiceProvider` setting.
2.  **Settings Persistence**: `voiceProvider` is stored in `settings.json` and modified via `/voice`, ensuring it persists across sessions.
3.  **OAuth Exclusivity (Anthropic)**: The Anthropic backend uses the `voice_stream` endpoint and is only available to OAuth users.
4.  **No OAuth for Doubao**: Doubao uses an independent credentials file and is gated only by `isVoiceAvailable()`.
5.  **GrowthBook Gating**: `tengu_amber_quartz_disabled` defaults to `false`, making the feature available by default.
6.  **Immediate `onReady`**: Doubao triggers `onReady` immediately after connection to avoid timing deadlocks with `useVoice` buffering (unlike Anthropic, which waits for a WebSocket handshake).
7.  **Immediate `finalize()`**: Since Doubao returns results during recording, there is no processing wait time when the user releases the spacebar.
8.  **Optimistic Availability Check**: `isDoubaoAvailableSync()` returns `true` on the first call; actual import errors are handled during connection.
9.  **Optional Dependencies**: `doubaoime-asr` is an optional dependency; its absence does not affect the Anthropic backend.

## V. Usage

```bash
# Enable the feature
FEATURE_VOICE_MODE=1 bun run dev

# Using the Anthropic Backend
# 1. Ensure you are logged in via OAuth (claude.ai subscription).
# 2. Type /voice to enable.
# 3. Hold Spacebar to speak.
# 4. Release Spacebar to transcribe.

# Using the Doubao ASR Backend
# 1. Ensure doubaoime-asr is installed (bun add doubaoime-asr).
# 2. Configure credentials in ~/.claude/tts/doubao/credentials.json.
# 3. Type /voice doubao to enable.
# 4. Hold Spacebar to speak; results appear instantly upon release.

# Switching Backends
/voice doubao      # Switch to Doubao ASR
/voice anthropic   # Switch to Anthropic STT
/voice             # Disable Voice Mode
```

### Doubao Credentials Configuration

Path: `~/.claude/tts/doubao/credentials.json`
```json
{
  "deviceId": "...",
  "installId": "...",
  "cdid": "...",
  "openudid": "...",
  "clientudid": "...",
  "token": "..."
}
```

## VI. External Dependencies

| Dependency | Description | Backend |
| :--- | :--- | :--- |
| **Anthropic OAuth** | claude.ai subscription login (not API key). | Anthropic |
| **GrowthBook** | Emergency kill-switch. | General |
| **Native macOS Audio / SoX** | Audio recording. | General |
| **Nova 3 STT** | Anthropic speech-to-text model. | Anthropic |
| **doubaoime-asr** | Doubao ASR SDK (optionalDependency). | Doubao |

## VII. File Index

| File | Responsibility |
| :--- | :--- |
| `src/voice/voiceModeEnabled.ts` | Gating logic and `isVoiceAvailable()`. |
| `src/hooks/useVoice.ts` | React hook for recording state and backend management. |
| `src/hooks/useVoiceEnabled.ts` | State hook for determining OAuth requirements based on provider. |
| `src/services/voiceStreamSTT.ts` | Anthropic STT WebSocket streaming. |
| `src/services/doubaoSTT.ts` | Doubao ASR adapter. |
| `src/commands/voice/voice.ts` | `/voice` command for toggling and switching backends. |
| `src/commands/voice/index.ts` | Command registration. |
