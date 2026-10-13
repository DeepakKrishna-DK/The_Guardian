from typing import Any

from guardian.logging.logger import get_logger
from guardian.vision.analyzer import VisionAnalyzer, MockVisionAnalyzer, OllamaVisionAnalyzer
from guardian.vision.models import VisionRequest, VisionResult

log = get_logger(__name__)

class VisionLayer:
    """
    Unified vision facade.
    Safe to construct without GPU - only fails on first use.
    """

    def __init__(self, analyzer: VisionAnalyzer) -> None:
        self._analyzer = analyzer

    def analyze_image(
        self,
        image_path: str,
        prompt: str = "Describe this image in detail.",
        max_new_tokens: int = 512,
        temperature: float = 0.2
    ) -> VisionResult:
        """
        Analyze an image on disk and return the text description.
        """
        request = VisionRequest(
            image_path=image_path,
            prompt=prompt,
            max_new_tokens=max_new_tokens,
            temperature=temperature
        )
        log.debug(f"Vision analyzing {image_path} with prompt: {prompt}")
        result = self._analyzer.analyze(request)
        log.info(f"Vision analysis complete: {result.processing_time_ms:.1f}ms")
        return result


# ─── Singleton Factory ────────────────────────────────────────────────────────

_layer: VisionLayer | None = None

def get_vision_layer(
    model_id: str = "moondream",
    device: str = "auto",
    mock: bool = False
) -> VisionLayer:
    """
    Return the shared VisionLayer singleton.
    Model is lazy-loaded on first use.
    """
    global _layer
    if _layer is None:
        if mock:
            analyzer = MockVisionAnalyzer()
        else:
            if model_id == "moondream":
                from guardian.vision.analyzer import OllamaVisionAnalyzer
                analyzer = OllamaVisionAnalyzer(model_name=model_id)
            else:
                from guardian.vision.hf_analyzers import SmolVLMAnalyzer
                analyzer = SmolVLMAnalyzer(model_id=model_id)
            
        _layer = VisionLayer(analyzer=analyzer)
        log.info(f"VisionLayer ready: analyzer={model_id}")
    return _layer

def reset_vision_layer() -> None:
    """For tests."""
    global _layer
    _layer = None
