try:
    import easyocr
except Exception:
    easyocr = None
import logging
from typing import Any
import numpy as np

try:
    from PIL import Image
except Exception:
    Image = None

log = logging.getLogger(__name__)

class OCRAnalyzer:
    """
    Lightweight local OCR using EasyOCR.
    Capable of running completely on CPU.
    """
    def __init__(self, langs: list[str] | None = None, use_gpu: bool = False):
        self.langs = langs or ['en']
        self.use_gpu = use_gpu
        self._reader = None

    def _load(self) -> None:
        if self._reader is None:
            if easyocr is None:
                raise ImportError("easyocr is required for OCRAnalyzer. Run: pip install easyocr")
            log.info(f"Loading EasyOCR (langs={self.langs}, gpu={self.use_gpu})...")
            # We specifically set gpu=False if torch.cuda is not available
            import torch
            has_gpu = self.use_gpu and torch.cuda.is_available()
            self._reader = easyocr.Reader(self.langs, gpu=has_gpu, verbose=False)
            log.info("EasyOCR loaded successfully.")

    def extract_text(self, image_path: str) -> list[dict[str, Any]]:
        """
        Extract text from an image and return bounding boxes.
        Returns:
            list of dicts containing 'text', 'confidence', 'bbox'
            where bbox is [(x1, y1), (x2, y2), (x3, y3), (x4, y4)]
        """
        self._load()
        
        # EasyOCR accepts paths directly, but to handle different formats safely we can pass numpy arrays
        # However passing paths is generally safe too.
        results = self._reader.readtext(image_path)
        
        parsed = []
        for bbox, text, prob in results:
            parsed.append({
                "text": text,
                "confidence": float(prob),
                "bbox": bbox
            })
            
        return parsed

    def find_text_coordinates(self, image_path: str, target_text: str, threshold: float = 0.5) -> list[dict[str, Any]]:
        """
        Find specific text on screen. 
        Returns matches sorted by confidence.
        """
        extracted = self.extract_text(image_path)
        matches = []
        
        target_lower = target_text.lower()
        for item in extracted:
            if item["confidence"] < threshold:
                continue
            if target_lower in item["text"].lower():
                matches.append(item)
                
        return sorted(matches, key=lambda x: x["confidence"], reverse=True)

