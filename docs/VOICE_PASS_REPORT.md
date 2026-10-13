# Voice Pass Report

## Audit vs Reality
M0 revealed that `faster-whisper` (`base` model, `int8`) was already properly configured and safely fits the 4GB VRAM limit. However, TTS defaulted to `EdgeTTSSynthesizer` (cloud) rather than the local `PiperSynthesizer` due to the lack of a shipped model, violating the strict offline goal by default. Additionally, `openwakeword` could not be tuned or run easily because `tflite-runtime` is unavailable for Windows Python 3.12, and the fallback ONNX models were missing from the package resources.

## Latency
- **M1 (STT Latency):** Synthetic evaluation was blocked by missing ONNX models, but STT successfully transcribed a 4s synthetic audio chunk in ~7.7s (including model load time on CPU).
- **M2 (TTS TTFA):** By slicing responses sentence-by-sentence in the pipeline, Time-to-First-Audio (TTFA) was brought down to ~2.02s for the first sentence, instead of waiting for full generation.

## M5 (Presence Integration)
M5 ran successfully because the Presence repo (P1) was located at `../Guardian/presence`. P1 *already contained* a basic WebAudio API (`AnalyserNode`) implementation that computes RMS volume to drive the avatar's jaw flap (`mouthOpen` morph target). I augmented the UI to visually respond to `transcribing` and `thinking` states (changing holographic emission colors) alongside the existing `speaking` and `idle` handlers.

## Security & No-Bypass Test
The `test_pipeline_no_bypass` ensures `VoicePipeline` routes directly through `GuardianCore.process()` and triggers `PolicyEngine.evaluate_model_call` just like text. The test passes cleanly.

## Event Schema
We shipped event schema `guardian.voice.v1` which broadcasts via WebSocket (`127.0.0.1:8000/ws/presence`) to drive the frontend.

## Deferred Items
- **Visemes:** Deferred in favor of raw RMS amplitude matching, as it's computationally free and avoids new dependencies.
- **Wake-Word Tuning:** Deferred due to missing `tflite-runtime` wheels on Windows/Python 3.12 and missing ONNX models. Recommended leaving default threshold at `0.5`.
- **Real-Mic Validation:** Requires hardware environment.
- **Event Server Auth:** Assumed safe behind localhost binding.
