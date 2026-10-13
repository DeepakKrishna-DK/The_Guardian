from dataclasses import dataclass, field
from typing import Any

@dataclass
class VisionRequest:
    """A request to analyze an image with a specific prompt."""
    image_path: str
    prompt: str = "Describe this image in detail."
    max_new_tokens: int = 512
    temperature: float = 0.2

@dataclass
class VisionResult:
    """Result of a vision analysis."""
    text: str
    model_name: str
    processing_time_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)
