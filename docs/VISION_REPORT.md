# Vision Layer Report: Migration to Ollama

## Selected Model
**Model:** `moondream` (1.8B parameters)
**Why:** Initial attempts to pull `minicpm-v` (4.4 GB) projected a download time of over 36 minutes at current speeds (~2MB/s), which exceeded realistic bounds for a swift implementation cycle. `moondream` (828 MB) was pulled as the lightweight, functional fallback.

## Implementation Changes
1. **`guardian/model/interface.py`**: Added an `images: list[str] | None` field to the `Message` dataclass. This allows base64-encoded images to cleanly pipe through the standard `ModelRequest` payload.
2. **`guardian/model/backends/ollama_backend.py`**: Modified `complete()` to explicitly inject the `images` list into the Ollama JSON payload when present.
3. **`guardian/vision/analyzer.py`**: Replaced the unworkable `TransformersVisionAnalyzer` with `OllamaVisionAnalyzer`. This new layer loads the target image, base64-encodes it, and passes it through the exact same `ModelRouter` interface using an `OllamaBackend` instance.
4. **`guardian/vision/__init__.py`**: Re-wired `get_vision_layer` to return `OllamaVisionAnalyzer` by default.
5. **`tests/test_vision.py`**: Refactored the test suite. Mock logic tests remain explicitly mocked, but a new `test_vision_integration_ollama` was added to run an actual image through the live `moondream` model (skipped cleanly if Ollama is unreachable).

## Live Test Metrics
End-to-end local testing with `check_vision.py` & `pytest` confirmed the following metrics for `moondream`:
- **Ollama Server Memory Footprint:** ~547 MB (Process footprint grew from 71.3 MB to 618.0 MB)
- **Cold Start Latency:** ~62.25 seconds (initial weight load into memory)
- **Warm Start Latency:** ~5.49 seconds (subsequent inference calls)

## Future Consideration: Gemini Multimodal
Gemini's multimodal input capabilities (e.g., passing image bytes directly to `gemini-3.8-flash`) were **deliberately excluded** from this pass. This ensures Guardian's vision layer remains strictly local and compliant with the Constitution's privacy directives. If local vision quality is later deemed insufficient, Gemini multimodal should be implemented strictly as an explicit, user-approved *opt-in* (never a default fallback).
