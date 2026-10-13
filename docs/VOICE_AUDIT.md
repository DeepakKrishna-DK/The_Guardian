# VOICE PIPELINE AUDIT REPORT

## Context
This audit verifies the state of the voice pipeline (Phase 11) against the project expectations before starting the voice-focused extension pass.

## Discoveries vs Expectations

### 1. STT Engine
- **Configured Engine:** `WhisperTranscriber` (wrapper for `faster-whisper`).
- **Model Size:** Defaults to `base`.
- **Compute Type:** Defaults to `int8`.
- **Constraint Check:** A `base` model in `int8` uses <1GB VRAM, comfortably fitting the 4GB RTX 3050 Laptop constraint.
- **Missing Features:** No streaming/partial transcription logic is visible in the base implementation; it transcribes chunks synchronously.

### 2. TTS Engine
- **Configured Engine:** The factory defaults to `EdgeTTSSynthesizer` (cloud) unless `piper_model` is explicitly provided, falling back to `MockSynthesizer`.
- **Local Fallback:** `PiperSynthesizer` exists and uses the external `piper` subprocess.
- **Observation:** The default relies on cloud, which violates the strict offline-capable goal unless explicitly configured with a Piper model.

### 3. Wake-Word Engine
- **Configured Engine:** `OpenWakeWordDetector` (`openwakeword`).
- **Model:** `hey_mycroft`.
- **Sensitivity:** Threshold is `0.5`.
- **Observation:** The engine is correctly wired but requires `openwakeword` to be installed (which was removed from CI requirements for Linux/Python 3.13 compatibility but works locally).

### 4. Presence Frontend
- **Location:** Found at `../Guardian/presence/` (inside the Guardian repository root, not as a sibling directory, contrary to expectations).
- **Implementation (P1):** It is a Vite/Three.js application (`package.json` depends on `three`).
- **Features Found:**
  - Loads a `half-body.glb` GLTF model.
  - Replaces materials with holographic shaders.
  - Connects to a WebSocket at `ws://localhost:8000/ws/presence`.
  - Receives `{"event": "speaking", "audio_b64": "..."}` messages.
  - Uses the Web Audio API `AnalyserNode` to compute RMS volume.
  - Drives a `mouthOpen` morph target on the mesh using the calculated volume (amplitude envelope).
- **Status:** The presence frontend already has an animation rigging foundation built-in for basic jaw-flap lip-sync.

### 5. Existing Tests
- There are tests for the pipeline (currently skipped in CI due to missing wheels for Python 3.13 on Linux, but present in the repo). 

## Next Steps
Proceeding to M1 to tune STT/Wake-word.
