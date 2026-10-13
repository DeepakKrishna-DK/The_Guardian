import pytest
import os
import requests
from pathlib import Path
from guardian.vision import get_vision_layer, reset_vision_layer
from guardian.vision.models import VisionRequest
from guardian.tools.vision_analyze import VisionAnalyzeTool

@pytest.fixture
def mock_vision():
    reset_vision_layer()
    get_vision_layer(mock=True)
    yield
    reset_vision_layer()

def test_vision_layer_mock(mock_vision):
    layer = get_vision_layer()
    
    result = layer.analyze_image(
        image_path="dummy.jpg", 
        prompt="What is this?"
    )
    
    assert "MOCK VISION" in result.text
    assert "dummy.jpg" in result.text
    assert "What is this?" in result.text
    assert result.model_name == "mock-vision-v1"

def test_vision_tool(mock_vision):
    tool = VisionAnalyzeTool()
    
    res = tool._execute({"prompt": "Hello"})
    assert not res.success
    assert "image_path is required" in res.output
    
    res = tool._execute({"image_path": "test.png"})
    assert res.success
    assert "MOCK VISION" in res.output
    assert "test.png" in res.output

def _is_ollama_ready():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code == 200:
            models = r.json().get("models", [])
            for m in models:
                if m.get("name", "").startswith("moondream"):
                    return True
    except Exception:
        pass
    return False

@pytest.mark.skipif(not _is_ollama_ready(), reason="Ollama moondream model not available")
def test_vision_integration_ollama(tmp_path):
    reset_vision_layer()
    layer = get_vision_layer(model_id="moondream", mock=False)
    
    # Create test image
    from PIL import Image
    img_path = str(tmp_path / "test.png")
    img = Image.new('RGB', (10, 10), color='blue')
    img.save(img_path)
    
    res = layer.analyze_image(img_path, prompt="Is this image mostly blue?")
    assert res.model_name == "moondream"
    assert len(res.text) > 0
    
    reset_vision_layer()
