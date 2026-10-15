"""
Guardian Model Catalog and Capability Discovery
================================================
Implements Section 3 (Model Registry and Capability Discovery) and
Section 4 (Initial Model Catalog) of the Guardian Master System Prompt v1.0.

Treats every model as a CANDIDATE until verified via capability inspection,
hardware requirement checks, custom code audits, and smoke testing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ModelHealthStatus(str, Enum):
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class ModelDeployment(str, Enum):
    LOCAL = "local"
    HOSTED = "hosted"
    HYBRID = "hybrid"


class TrustLevel(str, Enum):
    STANDARD = "standard"
    CURATED = "curated"
    REMOTE_CODE_UNREVIEWED = "remote_code_unreviewed"
    SANDBOX_REQUIRED = "sandbox_required"


@dataclass
class HardwareRequirement:
    min_ram_gb: float
    min_vram_gb: float
    disk_gb: float
    context_window: int
    recommended_gpu: str = "NVIDIA CUDA / Tensor Core"


@dataclass
class ModelCandidateEntry:
    """
    Registry entry adhering to Section 3 of Guardian Master System Prompt.
    """
    model_id: str
    repo: str
    family: str
    capability_tags: List[str]
    input_modalities: List[str]
    output_modalities: List[str]
    required_runtime: str
    required_dependencies: List[str]
    estimated_hardware: HardwareRequirement
    license: str
    trust_level: TrustLevel
    deployment: ModelDeployment
    health_status: ModelHealthStatus = ModelHealthStatus.CANDIDATE
    quantization_precision: str = "bf16"
    tool_calling_support: bool = False
    structured_output_support: bool = False
    known_limitations: List[str] = field(default_factory=list)
    evaluation_scores: Dict[str, float] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)
    code_snippet: str = ""
    requires_custom_code: bool = False
    candidate_number: int = 0
    last_smoke_test: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "candidate_number": self.candidate_number,
            "repo": self.repo,
            "family": self.family,
            "capability_tags": self.capability_tags,
            "input_modalities": self.input_modalities,
            "output_modalities": self.output_modalities,
            "required_runtime": self.required_runtime,
            "required_dependencies": self.required_dependencies,
            "estimated_hardware": {
                "min_ram_gb": self.estimated_hardware.min_ram_gb,
                "min_vram_gb": self.estimated_hardware.min_vram_gb,
                "disk_gb": self.estimated_hardware.disk_gb,
                "context_window": self.estimated_hardware.context_window,
                "recommended_gpu": self.estimated_hardware.recommended_gpu,
            },
            "license": self.license,
            "trust_level": self.trust_level.value,
            "deployment": self.deployment.value,
            "health_status": self.health_status.value,
            "quantization_precision": self.quantization_precision,
            "tool_calling_support": self.tool_calling_support,
            "structured_output_support": self.structured_output_support,
            "known_limitations": self.known_limitations,
            "evaluation_scores": self.evaluation_scores,
            "aliases": self.aliases,
            "requires_custom_code": self.requires_custom_code,
            "code_snippet": self.code_snippet,
        }


# ---------------------------------------------------------------------------
# Initial Model Catalog (Section 4 + 20 Snippets)
# ---------------------------------------------------------------------------

_INITIAL_CATALOG_DATA = [
    ModelCandidateEntry(
        candidate_number=1,
        model_id="google/gemma-4-26B-A4B",
        repo="google/gemma-4-26B-A4B",
        family="Gemma 4",
        capability_tags=["multimodal", "visual-qa", "general-reasoning"],
        input_modalities=["image", "text"],
        output_modalities=["text"],
        required_runtime="transformers",
        required_dependencies=["transformers", "torch", "accelerate"],
        estimated_hardware=HardwareRequirement(min_ram_gb=32.0, min_vram_gb=24.0, disk_gb=52.0, context_window=131072),
        license="Gemma Terms of Use",
        trust_level=TrustLevel.CURATED,
        deployment=ModelDeployment.HYBRID,
        quantization_precision="bf16",
        tool_calling_support=True,
        structured_output_support=True,
        known_limitations=["High VRAM footprint for full precision; requires GPU acceleration"],
        code_snippet="""from transformers import pipeline\npipe = pipeline("image-text-to-text", model="google/gemma-4-26B-A4B")\nfrom transformers import AutoProcessor, AutoModelForMultimodalLM\nprocessor = AutoProcessor.from_pretrained("google/gemma-4-26B-A4B")\nmodel = AutoModelForMultimodalLM.from_pretrained("google/gemma-4-26B-A4B", device_map="auto")""",
    ),
    ModelCandidateEntry(
        candidate_number=2,
        model_id="Qwen/Qwen-Image-2.1-Turbo",
        repo="Qwen/Qwen-Image-2.1-Turbo",
        family="Qwen-Image",
        capability_tags=["image-generation", "diffusion", "creative-media"],
        input_modalities=["text"],
        output_modalities=["image"],
        required_runtime="diffusers",
        required_dependencies=["diffusers", "transformers", "accelerate", "torch"],
        estimated_hardware=HardwareRequirement(min_ram_gb=32.0, min_vram_gb=16.0, disk_gb=20.0, context_window=1024),
        license="Apache-2.0",
        trust_level=TrustLevel.STANDARD,
        deployment=ModelDeployment.HYBRID,
        quantization_precision="bf16",
        known_limitations=["Diffusion pipeline; cannot process conversational chat or code"],
        code_snippet="""import torch\nfrom diffusers import DiffusionPipeline\npipe = DiffusionPipeline.from_pretrained("Qwen/Qwen-Image-2.1-Turbo", dtype=torch.bfloat16, device_map="cuda")\nprompt = "Astronaut in a jungle, cold color palette, muted colors, detailed, 8k"\nimage = pipe(prompt).images[0]""",
    ),
    ModelCandidateEntry(
        candidate_number=3,
        model_id="openai/gpt-oss-120b",
        repo="openai/gpt-oss-120b",
        family="GPT-OSS",
        capability_tags=["general-reasoning", "complex-analysis", "coding", "planning", "synthesis"],
        input_modalities=["text"],
        output_modalities=["text"],
        required_runtime="transformers",
        required_dependencies=["transformers", "torch", "accelerate"],
        estimated_hardware=HardwareRequirement(min_ram_gb=128.0, min_vram_gb=80.0, disk_gb=240.0, context_window=131072),
        license="Open Weight Permissive",
        trust_level=TrustLevel.STANDARD,
        deployment=ModelDeployment.HOSTED,
        quantization_precision="bf16",
        tool_calling_support=True,
        structured_output_support=True,
        aliases=["#14", "openai/gpt-oss-120b-alias"],
        known_limitations=["120B parameter scale requires datacenter/cluster inference or multi-GPU setup"],
        code_snippet="""from transformers import pipeline\npipe = pipeline("text-generation", model="openai/gpt-oss-120b")\nmessages = [{"role": "user", "content": "Who are you?"}]\npipe(messages)\nfrom transformers import AutoTokenizer, AutoModelForCausalLM\ntokenizer = AutoTokenizer.from_pretrained("openai/gpt-oss-120b")\nmodel = AutoModelForCausalLM.from_pretrained("openai/gpt-oss-120b", device_map="auto")""",
    ),
    ModelCandidateEntry(
        candidate_number=4,
        model_id="deepseek-ai/DeepSeek-V4-Pro",
        repo="deepseek-ai/DeepSeek-V4-Pro",
        family="DeepSeek-V4",
        capability_tags=["general-reasoning", "complex-analysis", "coding", "planning"],
        input_modalities=["text"],
        output_modalities=["text"],
        required_runtime="transformers",
        required_dependencies=["transformers", "torch", "accelerate"],
        estimated_hardware=HardwareRequirement(min_ram_gb=128.0, min_vram_gb=80.0, disk_gb=240.0, context_window=131072),
        license="DeepSeek Open License",
        trust_level=TrustLevel.STANDARD,
        deployment=ModelDeployment.HOSTED,
        quantization_precision="bf16",
        tool_calling_support=True,
        structured_output_support=True,
        known_limitations=["Massive MoE/dense architecture requires cluster hosting"],
        code_snippet="""from transformers import pipeline\npipe = pipeline("text-generation", model="deepseek-ai/DeepSeek-V4-Pro")\nfrom transformers import AutoTokenizer, AutoModelForCausalLM\ntokenizer = AutoTokenizer.from_pretrained("deepseek-ai/DeepSeek-V4-Pro")\nmodel = AutoModelForCausalLM.from_pretrained("deepseek-ai/DeepSeek-V4-Pro", device_map="auto")""",
    ),
    ModelCandidateEntry(
        candidate_number=5,
        model_id="nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16",
        repo="nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16",
        family="Nemotron-3.5",
        capability_tags=["general-reasoning", "fast-inference", "coding", "tool-calling"],
        input_modalities=["text"],
        output_modalities=["text"],
        required_runtime="transformers",
        required_dependencies=["transformers", "torch", "accelerate"],
        estimated_hardware=HardwareRequirement(min_ram_gb=32.0, min_vram_gb=24.0, disk_gb=60.0, context_window=65536),
        license="NVIDIA Open Model License",
        trust_level=TrustLevel.STANDARD,
        deployment=ModelDeployment.HYBRID,
        quantization_precision="bf16",
        tool_calling_support=True,
        structured_output_support=True,
        known_limitations=["30B architecture requires at least 24GB VRAM for BF16 or quantization"],
        code_snippet="""from transformers import pipeline\npipe = pipeline("text-generation", model="nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16")\nfrom transformers import AutoTokenizer, AutoModelForCausalLM\ntokenizer = AutoTokenizer.from_pretrained("nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16")\nmodel = AutoModelForCausalLM.from_pretrained("nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16", device_map="auto")""",
    ),
    ModelCandidateEntry(
        candidate_number=6,
        model_id="nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4",
        repo="nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4",
        family="Nemotron-3.5-VL",
        capability_tags=["multimodal", "visual-qa", "nvfp4-quantized", "screenshot-analysis"],
        input_modalities=["image", "text"],
        output_modalities=["text"],
        required_runtime="transformers",
        required_dependencies=["transformers", "torch", "accelerate"],
        estimated_hardware=HardwareRequirement(min_ram_gb=64.0, min_vram_gb=40.0, disk_gb=80.0, context_window=65536),
        license="NVIDIA Open Model License",
        trust_level=TrustLevel.SANDBOX_REQUIRED,
        deployment=ModelDeployment.HOSTED,
        quantization_precision="nvfp4",
        requires_custom_code=True,
        known_limitations=["NVFP4 hardware support required (Blackwell/Ada Hopper); requires trust_remote_code=True"],
        code_snippet="""from transformers import pipeline\npipe = pipeline("image-text-to-text", model="nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4", trust_remote_code=True)\nfrom transformers import AutoModelForMultimodalLM\nmodel = AutoModelForMultimodalLM.from_pretrained("nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4", trust_remote_code=True, device_map="auto")""",
    ),
    ModelCandidateEntry(
        candidate_number=7,
        model_id="nvidia/Cosmos3-Super",
        repo="nvidia/Cosmos3-Super",
        family="Cosmos3",
        capability_tags=["video-generation", "generative-media", "diffusion"],
        input_modalities=["text", "image"],
        output_modalities=["video", "image"],
        required_runtime="diffusers",
        required_dependencies=["diffusers", "transformers", "accelerate", "torch"],
        estimated_hardware=HardwareRequirement(min_ram_gb=64.0, min_vram_gb=32.0, disk_gb=50.0, context_window=1024),
        license="NVIDIA Cosmos License",
        trust_level=TrustLevel.STANDARD,
        deployment=ModelDeployment.HOSTED,
        quantization_precision="bf16",
        known_limitations=["Generative media pipeline; unsuitable for text chat or analysis"],
        code_snippet="""import torch\nfrom diffusers import DiffusionPipeline\npipe = DiffusionPipeline.from_pretrained("nvidia/Cosmos3-Super", dtype=torch.bfloat16, device_map="cuda")\nprompt = "Astronaut in a jungle, cold color palette, muted colors, detailed, 8k"\nimage = pipe(prompt).images[0]""",
    ),
    ModelCandidateEntry(
        candidate_number=8,
        model_id="nvidia/NemotronLabs-AI-for-Media-Sports-Tennis",
        repo="nvidia/NemotronLabs-AI-for-Media-Sports-Tennis",
        family="NemotronLabs-Media",
        capability_tags=["specialized-media", "sports-analytics", "video-understanding"],
        input_modalities=["video", "image", "text"],
        output_modalities=["structured_json", "text"],
        required_runtime="transformers",
        required_dependencies=["transformers", "torch"],
        estimated_hardware=HardwareRequirement(min_ram_gb=32.0, min_vram_gb=16.0, disk_gb=25.0, context_window=8192),
        license="Research / Restricted Evaluation",
        trust_level=TrustLevel.SANDBOX_REQUIRED,
        deployment=ModelDeployment.HYBRID,
        requires_custom_code=True,
        known_limitations=["Domain-specific tennis media model; must not be used for general tasks"],
        code_snippet="""from transformers import AutoModel\nmodel = AutoModel.from_pretrained("nvidia/NVIDIA-NemotronLabs-AI-for-Media-Sports-Tennis", trust_remote_code=True, device_map="auto")""",
    ),
    ModelCandidateEntry(
        candidate_number=9,
        model_id="microsoft/Fara1.5-27B",
        repo="microsoft/Fara1.5-27B",
        family="Fara",
        capability_tags=["visual-document", "computer-use", "screenshot-interpretation", "multimodal"],
        input_modalities=["image", "text"],
        output_modalities=["text"],
        required_runtime="transformers",
        required_dependencies=["transformers", "torch", "accelerate"],
        estimated_hardware=HardwareRequirement(min_ram_gb=32.0, min_vram_gb=24.0, disk_gb=54.0, context_window=32768),
        license="MIT",
        trust_level=TrustLevel.STANDARD,
        deployment=ModelDeployment.HYBRID,
        quantization_precision="bf16",
        tool_calling_support=True,
        structured_output_support=True,
        known_limitations=["For computer-use workflows, requires sandboxed desktop/browser session"],
        code_snippet="""from transformers import pipeline\npipe = pipeline("image-text-to-text", model="microsoft/Fara1.5-27B")\nfrom transformers import AutoProcessor, AutoModelForMultimodalLM\nprocessor = AutoProcessor.from_pretrained("microsoft/Fara1.5-27B")\nmodel = AutoModelForMultimodalLM.from_pretrained("microsoft/Fara1.5-27B", device_map="auto")""",
    ),
    ModelCandidateEntry(
        candidate_number=10,
        model_id="BioMistral/BioMistral-7B",
        repo="BioMistral/BioMistral-7B",
        family="Mistral / BioMistral",
        capability_tags=["scientific", "biomedical", "research-summarization", "medical-nlp"],
        input_modalities=["text"],
        output_modalities=["text"],
        required_runtime="transformers",
        required_dependencies=["transformers", "torch"],
        estimated_hardware=HardwareRequirement(min_ram_gb=16.0, min_vram_gb=8.0, disk_gb=15.0, context_window=8192),
        license="Apache-2.0",
        trust_level=TrustLevel.STANDARD,
        deployment=ModelDeployment.HYBRID,
        quantization_precision="bf16",
        known_limitations=["Assistive research only; never a substitute for qualified professional medical judgment"],
        code_snippet="""from transformers import pipeline\npipe = pipeline("text-generation", model="BioMistral/BioMistral-7B")\nfrom transformers import AutoTokenizer, AutoModelForCausalLM\ntokenizer = AutoTokenizer.from_pretrained("BioMistral/BioMistral-7B")\nmodel = AutoModelForCausalLM.from_pretrained("BioMistral/BioMistral-7B", device_map="auto")""",
    ),
    ModelCandidateEntry(
        candidate_number=11,
        model_id="openai/whisper-large-v3",
        repo="openai/whisper-large-v3",
        family="Whisper",
        capability_tags=["speech-to-text", "asr", "audio-transcription", "timestamps"],
        input_modalities=["audio"],
        output_modalities=["text"],
        required_runtime="transformers",
        required_dependencies=["transformers", "torch"],
        estimated_hardware=HardwareRequirement(min_ram_gb=8.0, min_vram_gb=6.0, disk_gb=6.0, context_window=448),
        license="MIT",
        trust_level=TrustLevel.STANDARD,
        deployment=ModelDeployment.LOCAL,
        quantization_precision="fp16",
        known_limitations=["Audio speech-to-text only; preserves timestamps when enabled"],
        code_snippet="""from transformers import pipeline\npipe = pipeline("automatic-speech-recognition", model="openai/whisper-large-v3")\nfrom transformers import AutoProcessor, AutoModelForSpeechSeq2Seq\nprocessor = AutoProcessor.from_pretrained("openai/whisper-large-v3")\nmodel = AutoModelForSpeechSeq2Seq.from_pretrained("openai/whisper-large-v3", device_map="auto")""",
    ),
    ModelCandidateEntry(
        candidate_number=12,
        model_id="hexgrad/Kokoro-82M",
        repo="hexgrad/Kokoro-82M",
        family="Kokoro",
        capability_tags=["text-to-speech", "tts", "voice-synthesis"],
        input_modalities=["text"],
        output_modalities=["audio"],
        required_runtime="huggingface_hub",
        required_dependencies=["huggingface_hub"],
        estimated_hardware=HardwareRequirement(min_ram_gb=4.0, min_vram_gb=2.0, disk_gb=1.0, context_window=512),
        license="Apache-2.0",
        trust_level=TrustLevel.STANDARD,
        deployment=ModelDeployment.HYBRID,
        quantization_precision="fp32",
        known_limitations=["TTS output only; does not generate text or reason"],
        code_snippet="""import os\nfrom huggingface_hub import InferenceClient\nclient = InferenceClient(provider="auto", api_key=os.environ.get("HF_TOKEN", ""))\naudio = client.text_to_speech("The answer to the universe is 42", model="hexgrad/Kokoro-82M:preferred")""",
    ),
    ModelCandidateEntry(
        candidate_number=13,
        model_id="PaddleOCR-VL",
        repo="PaddlePaddle/PaddleOCR",
        family="PaddleOCR",
        capability_tags=["ocr", "document-extraction", "table-extraction", "pdf-parsing"],
        input_modalities=["image", "pdf"],
        output_modalities=["structured_json", "markdown", "text"],
        required_runtime="paddleocr",
        required_dependencies=["paddleocr", "paddlepaddle"],
        estimated_hardware=HardwareRequirement(min_ram_gb=8.0, min_vram_gb=4.0, disk_gb=4.0, context_window=4096),
        license="Apache-2.0",
        trust_level=TrustLevel.STANDARD,
        deployment=ModelDeployment.LOCAL,
        quantization_precision="fp32",
        structured_output_support=True,
        known_limitations=["Visual document OCR pipeline; structured text extraction only"],
        code_snippet="""from paddleocr import PaddleOCRVL\npipeline = PaddleOCRVL(pipeline_version="v1.6")\noutput = pipeline.predict("path/to/document_image.png")\nfor res in output:\n    res.print()\n    res.save_to_json(save_path="output")\n    res.save_to_markdown(save_path="output")""",
    ),
    ModelCandidateEntry(
        candidate_number=15,
        model_id="Qwen/Qwen3.8-27B",
        repo="Qwen/Qwen3.8-27B",
        family="Qwen3.8",
        capability_tags=["multimodal", "visual-qa", "general-reasoning", "coding"],
        input_modalities=["image", "text"],
        output_modalities=["text"],
        required_runtime="transformers",
        required_dependencies=["transformers", "torch", "accelerate"],
        estimated_hardware=HardwareRequirement(min_ram_gb=32.0, min_vram_gb=24.0, disk_gb=55.0, context_window=131072),
        license="Apache-2.0",
        trust_level=TrustLevel.STANDARD,
        deployment=ModelDeployment.HYBRID,
        quantization_precision="bf16",
        tool_calling_support=True,
        structured_output_support=True,
        known_limitations=["Requires >= 24GB VRAM for unquantized weights"],
        code_snippet="""from transformers import pipeline\npipe = pipeline("image-text-to-text", model="Qwen/Qwen3.8-27B")\nfrom transformers import AutoProcessor, AutoModelForMultimodalLM\nprocessor = AutoProcessor.from_pretrained("Qwen/Qwen3.8-27B")\nmodel = AutoModelForMultimodalLM.from_pretrained("Qwen/Qwen3.8-27B", device_map="auto")""",
    ),
    ModelCandidateEntry(
        candidate_number=17,
        model_id="zai-org/GLM-5.2",
        repo="zai-org/GLM-5.2",
        family="GLM",
        capability_tags=["general-reasoning", "bilingual", "synthesis", "coding"],
        input_modalities=["text"],
        output_modalities=["text"],
        required_runtime="transformers",
        required_dependencies=["transformers", "torch", "accelerate"],
        estimated_hardware=HardwareRequirement(min_ram_gb=64.0, min_vram_gb=40.0, disk_gb=90.0, context_window=131072),
        license="Apache-2.0",
        trust_level=TrustLevel.STANDARD,
        deployment=ModelDeployment.HOSTED,
        quantization_precision="bf16",
        tool_calling_support=True,
        structured_output_support=True,
        known_limitations=["Large parameter count; hosted execution recommended"],
        code_snippet="""from transformers import pipeline\npipe = pipeline("text-generation", model="zai-org/GLM-5.2")\nfrom transformers import AutoTokenizer, AutoModelForCausalLM\ntokenizer = AutoTokenizer.from_pretrained("zai-org/GLM-5.2")\nmodel = AutoModelForCausalLM.from_pretrained("zai-org/GLM-5.2", device_map="auto")""",
    ),
    ModelCandidateEntry(
        candidate_number=18,
        model_id="deepseek-ai/DeepSeek-R1",
        repo="deepseek-ai/DeepSeek-R1",
        family="DeepSeek-R1",
        capability_tags=["complex-reasoning", "mathematical-reasoning", "coding", "planning"],
        input_modalities=["text"],
        output_modalities=["text"],
        required_runtime="transformers",
        required_dependencies=["transformers", "torch", "accelerate"],
        estimated_hardware=HardwareRequirement(min_ram_gb=128.0, min_vram_gb=80.0, disk_gb=250.0, context_window=131072),
        license="DeepSeek Open License",
        trust_level=TrustLevel.SANDBOX_REQUIRED,
        deployment=ModelDeployment.HOSTED,
        quantization_precision="bf16",
        requires_custom_code=True,
        tool_calling_support=True,
        structured_output_support=True,
        known_limitations=["Reasoning model; requires custom code execution sandbox and high compute capacity"],
        code_snippet="""from transformers import pipeline\npipe = pipeline("text-generation", model="deepseek-ai/DeepSeek-R1", trust_remote_code=True)\nfrom transformers import AutoTokenizer, AutoModelForCausalLM\ntokenizer = AutoTokenizer.from_pretrained("deepseek-ai/DeepSeek-R1", trust_remote_code=True)\nmodel = AutoModelForCausalLM.from_pretrained("deepseek-ai/DeepSeek-R1", trust_remote_code=True, device_map="auto")""",
    ),
    ModelCandidateEntry(
        candidate_number=19,
        model_id="google/gemma-4-31B-it",
        repo="google/gemma-4-31B-it",
        family="Gemma 4",
        capability_tags=["multimodal", "instruction-following", "visual-qa", "reasoning"],
        input_modalities=["image", "text"],
        output_modalities=["text"],
        required_runtime="transformers",
        required_dependencies=["transformers", "torch", "accelerate"],
        estimated_hardware=HardwareRequirement(min_ram_gb=40.0, min_vram_gb=28.0, disk_gb=62.0, context_window=131072),
        license="Gemma Terms of Use",
        trust_level=TrustLevel.CURATED,
        deployment=ModelDeployment.HYBRID,
        quantization_precision="bf16",
        tool_calling_support=True,
        structured_output_support=True,
        known_limitations=["31B parameter instruction model requires dedicated GPU or quantization"],
        code_snippet="""from transformers import pipeline\npipe = pipeline("image-text-to-text", model="google/gemma-4-31B-it")\nfrom transformers import AutoProcessor, AutoModelForMultimodalLM\nprocessor = AutoProcessor.from_pretrained("google/gemma-4-31B-it")\nmodel = AutoModelForMultimodalLM.from_pretrained("google/gemma-4-31B-it", device_map="auto")""",
    ),
    ModelCandidateEntry(
        candidate_number=20,
        model_id="cisco-ai/SecureBERT2.0-base",
        repo="cisco-ai/SecureBERT2.0-base",
        family="SecureBERT",
        capability_tags=["security", "cybersecurity-text", "masked-token-prediction", "terminology"],
        input_modalities=["text"],
        output_modalities=["masked_text", "embeddings"],
        required_runtime="transformers",
        required_dependencies=["transformers", "torch"],
        estimated_hardware=HardwareRequirement(min_ram_gb=8.0, min_vram_gb=4.0, disk_gb=2.0, context_window=512),
        license="Apache-2.0",
        trust_level=TrustLevel.STANDARD,
        deployment=ModelDeployment.LOCAL,
        quantization_precision="fp32",
        known_limitations=["Masked language model for security terminology; not a firewall, malware scanner, or general conversational agent"],
        code_snippet="""from transformers import pipeline\npipe = pipeline("fill-mask", model="cisco-ai/SecureBERT2.0-base")\nfrom transformers import AutoTokenizer, AutoModelForMaskedLM\ntokenizer = AutoTokenizer.from_pretrained("cisco-ai/SecureBERT2.0-base")\nmodel = AutoModelForMaskedLM.from_pretrained("cisco-ai/SecureBERT2.0-base", device_map="auto")""",
    ),
]


class CandidateModelCatalog:
    """
    Catalog manager for candidate models, handling alias resolution,
    hardware requirement verification, custom code inspection, and capability matching.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, ModelCandidateEntry] = {}
        self._aliases: Dict[str, str] = {}
        for entry in _INITIAL_CATALOG_DATA:
            self._entries[entry.model_id.lower()] = entry
            for alias in entry.aliases:
                self._aliases[alias.lower()] = entry.model_id.lower()

    def get(self, identifier: str) -> Optional[ModelCandidateEntry]:
        """Lookup by model_id or alias."""
        key = identifier.strip().lower()
        if key in self._aliases:
            key = self._aliases[key]
        return self._entries.get(key)

    def list_all(self) -> List[ModelCandidateEntry]:
        """Return all unique model candidates."""
        return list(self._entries.values())

    def filter(
        self,
        modality: Optional[str] = None,
        tag: Optional[str] = None,
        deployment: Optional[str] = None,
        requires_custom_code: Optional[bool] = None,
    ) -> List[ModelCandidateEntry]:
        """Filter candidates by capability, modality, or trust constraints."""
        results = []
        for entry in self._entries.values():
            if modality and modality.lower() not in [m.lower() for m in entry.input_modalities + entry.output_modalities]:
                continue
            if tag and tag.lower() not in [t.lower() for t in entry.capability_tags]:
                continue
            if deployment and entry.deployment.value.lower() != deployment.lower():
                continue
            if requires_custom_code is not None and entry.requires_custom_code != requires_custom_code:
                continue
            results.append(entry)
        return results

    def verify_candidate_eligibility(
        self,
        model_id: str,
        available_ram_gb: float = 16.0,
        available_vram_gb: float = 4.0,
        has_cuda: bool = False,
    ) -> Dict[str, Any]:
        """
        Verify candidate against Section 3 verification protocol:
          1. Check hardware/memory compatibility
          2. Check custom code / trust level
          3. Establish runtime and modality
          4. Return verification report
        """
        entry = self.get(model_id)
        if not entry:
            return {
                "eligible": False,
                "reason": f"Model identifier {model_id!r} not found in catalog.",
                "candidate_status": ModelHealthStatus.UNAVAILABLE.value,
            }

        issues: List[str] = []
        warnings: List[str] = []

        # Hardware check
        if entry.estimated_hardware.min_ram_gb > available_ram_gb:
            warnings.append(
                f"RAM requirement ({entry.estimated_hardware.min_ram_gb} GB) exceeds detected host RAM ({available_ram_gb} GB). Requires hosted or remote inference."
            )
        if entry.estimated_hardware.min_vram_gb > available_vram_gb:
            warnings.append(
                f"VRAM requirement ({entry.estimated_hardware.min_vram_gb} GB) exceeds local VRAM ({available_vram_gb} GB). Local offload impossible without hosted runtime or extreme quantization."
            )
        if not has_cuda and entry.estimated_hardware.min_vram_gb > 0:
            warnings.append("Local CUDA acceleration not enabled in PyTorch; local GPU execution unavailable.")

        # Remote code check (Section 3 security directive)
        if entry.requires_custom_code:
            warnings.append(
                "SECURITY WARNING: Model specifies trust_remote_code=True. Remote code execution sandboxing is required before activation."
            )

        is_hosted_viable = entry.deployment in (ModelDeployment.HOSTED, ModelDeployment.HYBRID)
        is_local_viable = len(issues) == 0 and (entry.estimated_hardware.min_ram_gb <= available_ram_gb)

        return {
            "model_id": entry.model_id,
            "candidate_number": entry.candidate_number,
            "eligible": len(issues) == 0,
            "local_executable": is_local_viable,
            "hosted_executable": is_hosted_viable,
            "warnings": warnings,
            "issues": issues,
            "recommended_deployment": "hosted" if not is_local_viable else "local",
            "trust_level": entry.trust_level.value,
            "security_sandbox_required": entry.requires_custom_code,
        }


# Singleton catalog instance
_global_catalog: Optional[CandidateModelCatalog] = None


def get_candidate_catalog() -> CandidateModelCatalog:
    global _global_catalog
    if _global_catalog is None:
        _global_catalog = CandidateModelCatalog()
    return _global_catalog
