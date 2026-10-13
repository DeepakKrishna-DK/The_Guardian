import time
from abc import ABC, abstractmethod
from typing import Any

from guardian.logging.logger import get_logger
from guardian.vision.models import VisionRequest, VisionResult

log = get_logger(__name__)


class VisionAnalyzer(ABC):
    """Abstract base for vision models."""

    @abstractmethod
    def analyze(self, request: VisionRequest) -> VisionResult:
        """Analyze an image and return text output."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the name of the model being used."""


class MockVisionAnalyzer(VisionAnalyzer):
    """Deterministic mock analyzer for tests."""

    def __init__(self, model_name: str = "mock-vision-v1") -> None:
        self._model_name = model_name

    def analyze(self, request: VisionRequest) -> VisionResult:
        t0 = time.monotonic()
        
        if not request.image_path:
            text = "Error: No image provided."
        else:
            text = f"[MOCK VISION] Analyzed {request.image_path} with prompt: '{request.prompt}'"
            
        return VisionResult(
            text=text,
            model_name=self._model_name,
            processing_time_ms=(time.monotonic() - t0) * 1000,
        )

    @property
    def model_name(self) -> str:
        return self._model_name


class TransformersVisionAnalyzer(VisionAnalyzer):
    """
    HuggingFace Transformers based Vision Analyzer.
    Supports Qwen2.5-VL and MiniCPM-V out of the box.
    """

    def __init__(self, model_id: str = "Qwen/Qwen2.5-VL-3B-Instruct", device: str = "auto") -> None:
        self._model_id = model_id
        self._device = device
        self._processor = None
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
                from PIL import Image
            except ImportError:
                raise ImportError(
                    "transformers and pillow are required for local vision models. "
                    "Run: pip install transformers pillow"
                )
            
            log.info(f"Loading vision model {self._model_id}...")
            
            # Using Qwen2.5-VL specifics as requested by the prompt
            self._processor = AutoProcessor.from_pretrained(self._model_id)
            self._model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                self._model_id,
                device_map="auto" if self._device == "auto" else self._device,
                torch_dtype="auto"
            )
            log.info("Vision model loaded successfully.")

    def analyze(self, request: VisionRequest) -> VisionResult:
        t0 = time.monotonic()
        self._load()
        
        try:
            from PIL import Image
            image = Image.open(request.image_path).convert("RGB")
        except Exception as e:
            return VisionResult(
                text=f"Failed to load image: {e}",
                model_name=self._model_id,
                processing_time_ms=(time.monotonic() - t0) * 1000,
            )

        # Basic conversational format expected by Qwen VL
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": request.prompt},
                ],
            }
        ]
        
        text = self._processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        
        # Simplified standard transformers processor call
        try:
            inputs = self._processor(
                text=[text],
                images=[image],
                padding=True,
                return_tensors="pt"
            )
            inputs = inputs.to(self._model.device)

            generated_ids = self._model.generate(
                **inputs,
                max_new_tokens=request.max_tokens if hasattr(request, 'max_tokens') else request.max_new_tokens,
                temperature=request.temperature
            )
            
            generated_ids_trimmed = [
                out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids, strict=False)
            ]
            
            output_text = self._processor.batch_decode(
                generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
            )[0]
        except Exception as e:
            log.error(f"Vision inference failed: {e}")
            output_text = f"Inference error: {e}"

        return VisionResult(
            text=output_text,
            model_name=self._model_id,
            processing_time_ms=(time.monotonic() - t0) * 1000,
        )

    @property
    def model_name(self) -> str:
        return self._model_id


class OllamaVisionAnalyzer(VisionAnalyzer):
    """
    Vision Analyzer using Guardian's existing Ollama model backend.
    Sends base64 images via the standard ModelInterface.
    """

    def __init__(self, model_name: str = "moondream") -> None:
        self._model_name = model_name

    def analyze(self, request: VisionRequest) -> VisionResult:
        import base64
        import time
        import os
        from guardian.model.interface import ModelRequest, Message, Role
        from guardian.model.backends.ollama_backend import OllamaBackend
        
        t0 = time.monotonic()
        try:
            with open(request.image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            return VisionResult(
                text=f"Failed to load image: {e}",
                model_name=self._model_name,
                processing_time_ms=(time.monotonic() - t0) * 1000,
            )
            
        old_model = os.environ.get("GUARDIAN_OLLAMA_MODEL")
        try:
            os.environ["GUARDIAN_OLLAMA_MODEL"] = self._model_name
            backend = OllamaBackend()
        finally:
            if old_model is not None:
                os.environ["GUARDIAN_OLLAMA_MODEL"] = old_model
            else:
                del os.environ["GUARDIAN_OLLAMA_MODEL"]
        
        # Max tokens can be passed as max_tokens or max_new_tokens
        max_t = getattr(request, 'max_tokens', getattr(request, 'max_new_tokens', 1024))
        
        req = ModelRequest(
            messages=[Message(role=Role.USER, content=request.prompt, images=[img_b64])],
            max_tokens=max_t,
            temperature=request.temperature
        )
        
        try:
            resp = backend.complete(req)
            output_text = resp.content
        except Exception as e:
            log.error(f"Vision inference failed via Ollama: {e}")
            output_text = f"Inference error: {e}"

        return VisionResult(
            text=output_text,
            model_name=self._model_name,
            processing_time_ms=(time.monotonic() - t0) * 1000,
        )

    @property
    def model_name(self) -> str:
        return self._model_name
