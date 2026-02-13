# Design & Architecture

Technical deep-dive into Wyoming Voice Match internals. For setup and usage, see [README.md](README.md).

## Pipeline Overview

```
                    Home Assistant Voice Pipeline
                              │
                    Transcribe + AudioStart
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Wyoming Voice Match                          │
│                                                                 │
│  AudioChunk ──▶ Buffer ──▶ 5s buffered? ──▶ Background task:   │
│       │                         │            ┌───────────────┐  │
│       │                         │            │ RMS energy    │  │
│       │                         │            │ analysis      │  │
│       │                         │            │      │        │  │
│       │                         │            │ ECAPA-TDNN    │  │
│       │                         │            │ embedding     │  │
│       │                         │            │      │        │  │
│       │                         │            │ Cosine sim    │  │
│       │                         │            │ vs enrolled   │  │
│       │                         │            └───────┬───────┘  │
│       │                         │                    │          │
│       │                         │              Match? ──Yes──▶ Forward to ASR ──▶ Transcript
│       │                         │                │              │
│       ▼                         │               No              │
│  (keep buffering)               │                │              │
│                                 │         Empty transcript      │
│  AudioStop ──▶ Already responded? ──Yes──▶ (discard)           │
│                      │                                          │
│                     No ──▶ Verify full audio (fallback)         │
└─────────────────────────────────────────────────────────────────┘
```

The service implements the Wyoming ASR protocol (`Transcribe`, `AudioStart`, `AudioChunk`, `AudioStop`, `Transcript`) and presents itself as a standard ASR service to Home Assistant.

## Audio Buffering

Raw PCM audio arrives as small chunks (~100ms each) at 16kHz, 16-bit mono — 32,000 bytes per second. Each chunk is appended to an in-memory byte buffer. The buffer grows until either early verification is triggered or `AudioStop` is received.

## Early Verification

Once the buffer reaches `MAX_VERIFY_SECONDS` (default 5.0s), we snapshot the buffer and start speaker verification immediately in a background task — without waiting for the audio stream to end.

This is critical because background noise (like a TV) prevents Home Assistant's VAD (voice activity detection) from detecting silence, keeping the stream open for 15+ seconds. By starting verification at 5 seconds, we cut response time by 10+ seconds in noisy environments.

If the audio stream ends before reaching 5 seconds (quiet room, fast VAD), verification runs synchronously at `AudioStop` with no additional delay.

Once verification passes, the transcript is sent back to Home Assistant immediately. The `_responded` flag is set, and any remaining `AudioChunk` events are silently consumed until `AudioStop` arrives.

## RMS Energy Analysis (Speech Detection)

The 5-second buffer contains the voice command mixed with background noise. Before verifying speaker identity, we isolate the portion most likely to be the user's voice.

**How it works:**

1. Split the audio into 50ms frames (800 samples each at 16kHz)
2. Compute the RMS (root mean square) energy of each frame — `sqrt(mean(samples²))`
3. Find the frame with the highest energy (the peak) — this is almost certainly within the voice command, since the user is closer to the mic than the TV
4. Expand outward from the peak in both directions, including any frame with at least 15% of the peak's energy
5. When energy drops below that threshold, stop expanding

This typically yields a 1–2 second segment centered on the voice command. The segment is used for speaker verification (Pass 1), while the full buffer is trimmed for ASR forwarding.

**Internal parameters (not exposed as config):**
- Frame size: 50ms
- Energy threshold: 15% of peak
- Minimum segment length: 1.0s
- Near-silence cutoff: RMS < 100

## Speaker Verification (ECAPA-TDNN)

The isolated speech segment is fed through [SpeechBrain's ECAPA-TDNN](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb) neural network, which produces a 192-dimensional **embedding** — a compact numerical fingerprint of the speaker's voice. This captures characteristics like vocal tract shape, pitch patterns, and speaking rhythm.

During enrollment, the same model generates an embedding from the user's voice samples, which is saved to disk as a `.npy` file. At verification time, we compute the **cosine similarity** between the live embedding and each enrolled embedding:

```
similarity = dot(live, enrolled) / (norm(live) * norm(enrolled))
```

Cosine similarity ranges from -1 to 1, where higher means more similar. If any enrolled speaker exceeds `VERIFY_THRESHOLD`, the audio is accepted.

## Three-Pass Verification Strategy

If the energy-detected speech segment doesn't match, we don't give up immediately:

- **Pass 1 (speech):** Verify the energy-detected speech segment. Most accurate because it filters out background noise. This is where most verifications succeed.
- **Pass 2 (first-N):** Verify the first `MAX_VERIFY_SECONDS` of raw audio. Fallback in case energy detection missed the voice (e.g., the user spoke very quietly).
- **Pass 3 (sliding window):** Slide a `VERIFY_WINDOW_SECONDS` window across the full audio in `VERIFY_STEP_SECONDS` steps, checking each segment. Last resort for unusual audio patterns where the voice isn't at the start or the loudest part.

The best similarity score across all passes is tracked. If any pass exceeds the threshold, that result is returned immediately without running remaining passes.

## Audio Trimming for ASR

Only the first `ASR_MAX_SECONDS` (default 3.0s) of the audio buffer is forwarded to the upstream ASR service. This serves two purposes:

1. **Noise reduction:** Cuts off TV dialogue, music, and other background audio that accumulated after the voice command
2. **Transcript quality:** Prevents the ASR from transcribing background noise as part of the command

The voice command is always at the start of the buffer (immediately after the wake word), so trimming from the end preserves the command while removing noise.

## Concurrency & Model Lock

The ECAPA-TDNN model is loaded once at startup and shared across all connections. A single `asyncio.Lock` prevents concurrent inference, ensuring thread-safe GPU/CPU access. Verification runs in a thread pool executor (`run_in_executor`) to avoid blocking the async event loop.

Each connection gets its own `SpeakerVerifyHandler` instance with independent state (buffer, session ID, verify task). The lock only serializes the model inference step — buffering and protocol handling remain concurrent.

## Session Tracking

Each handler instance generates an 8-character UUID session ID at creation time. All log messages are prefixed with `[session_id]` to distinguish concurrent connections. This is generated per-handler rather than per-`AudioStart` because each Wyoming TCP connection maps to exactly one handler instance.

## Development Mode

To iterate on code without rebuilding the Docker image, mount the source code as a volume in `docker-compose.yml`:

```yaml
    volumes:
      - ./data:/data
      - ./wyoming_voice_match:/app/wyoming_voice_match
      - ./scripts:/app/scripts
```

Then restart after changes:

```bash
docker compose restart voice-match
```