from guardian.tools.base import Tool, ToolLevel, ToolResult
from guardian.logging.logger import get_logger

log = get_logger(__name__)

class VisionAnalyzeTool(Tool):
    """
    Tool to analyze an image on disk using the VisionLayer.
    """
    
    name = "vision_analyze"
    level = ToolLevel.READ
    description = (
        "Analyze an image file and return a text description. "
        "Useful for understanding charts, documents, or photos. "
        "Requires 'image_path' (absolute path) and optionally 'prompt' (specific question)."
    )
    
    def _execute(self, params: dict[str, str]) -> ToolResult:
        image_path = params.get("image_path")
        if not image_path:
            return ToolResult(success=False, output="Error: image_path is required.")
            
        prompt = params.get("prompt", "Describe this image in detail.")
        
        try:
            from guardian.vision import get_vision_layer
            
            # Use mock=True in testing environments, but for real usage we'd let it default
            # For this tool, we just use the singleton.
            layer = get_vision_layer()
            result = layer.analyze_image(image_path=image_path, prompt=prompt)
            
            output = f"Analysis of {image_path}:\n{result.text}"
            return ToolResult(success=True, output=output)
        except Exception as e:
            log.error(f"Vision tool failed: {e}")
            return ToolResult(success=False, output=f"Vision analysis failed: {e}")
