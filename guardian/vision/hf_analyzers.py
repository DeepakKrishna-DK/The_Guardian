import base64
import time
import io
import logging
from PIL import Image

from guardian.vision.analyzer import VisionAnalyzer, VisionRequest, VisionResult

log = logging.getLogger(__name__)

class SmolVLMAnalyzer(VisionAnalyzer):
    """
    Vision analyzer using SmolVLM-256M-Instruct via HuggingFace transformers.
    Optimized for small local instances (256M parameters).
    Requires: pip install transformers timm einops
    """
    def __init__(self, model_id: str = "HuggingFaceTB/SmolVLM-256M-Instruct"):
        self.model_id = model_id
        self.processor = None
        self.model = None

    def _load(self) -> None:
        if self.model is not None:
            return
            
        from transformers import AutoProcessor, AutoModelForImageTextToText
        log.info(f"Loading SmolVLM processor ({self.model_id})...")
        self.processor = AutoProcessor.from_pretrained(self.model_id)
        
        log.info(f"Loading SmolVLM model ({self.model_id}) on CPU...")
        self.model = AutoModelForImageTextToText.from_pretrained(self.model_id)
        log.info("SmolVLM model loaded successfully.")

    def analyze(self, request: VisionRequest) -> VisionResult:
        self._load()
        t0 = time.monotonic()
        
        # Load image
        if request.image_path:
            img = Image.open(request.image_path).convert("RGB")
        elif request.image_bytes:
            img = Image.open(io.BytesIO(request.image_bytes)).convert("RGB")
        elif request.image_base64:
            b = base64.b64decode(request.image_base64)
            img = Image.open(io.BytesIO(b)).convert("RGB")
        else:
            raise ValueError("VisionRequest must include image_path, image_bytes, or image_base64")
            
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": request.prompt}
                ]
            }
        ]
        
        prompt = self.processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = self.processor(text=prompt, images=[img], return_tensors="pt")
        
        max_t = getattr(request, 'max_tokens', getattr(request, 'max_new_tokens', 1024))
        generated_ids = self.model.generate(**inputs, max_new_tokens=max_t)
        
        generated_texts = self.processor.batch_decode(
            generated_ids,
            skip_special_tokens=True,
        )
        
        result_text = generated_texts[0].split("Assistant:")[-1].strip() if "Assistant:" in generated_texts[0] else generated_texts[0]
        
        return VisionResult(
            raw_output=result_text,
            structured_data={},
            processing_time_ms=(time.monotonic() - t0) * 1000
        )

class Qwen2VLVisionAnalyzer(VisionAnalyzer):
    """
    Qwen2.5-VL Analyzer (optimized for UI grounding and bounding boxes).
    """
    def __init__(self, model_id: str = "Qwen/Qwen2.5-VL-3B-Instruct"):
        self.model_id = model_id
        
    def analyze(self, request: VisionRequest) -> VisionResult:
        raise NotImplementedError("Qwen2-VL requires qwen-vl-utils and GPU acceleration to run smoothly.")

class Florence2VisionAnalyzer(VisionAnalyzer):
    """
    Florence-2 Analyzer (optimized for OCR and dense region captioning).
    """
    def __init__(self, model_id: str = "microsoft/Florence-2-base"):
        self.model_id = model_id
        
    def analyze(self, request: VisionRequest) -> VisionResult:
        raise NotImplementedError("Florence-2 requires transformers <4.45 or specific workarounds in this environment.")
