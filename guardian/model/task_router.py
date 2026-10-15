"""
Guardian Intelligent Task Router & Multi-Model Collaboration Engine
===================================================================
Implements Section 5 (Intelligent Task Routing), Section 6 (Multi-Model Collaboration),
Section 12 (Output Validation), and Section 17 (Standard Response Format)
of the Guardian Master System Prompt v1.0.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from guardian.model.catalog import CandidateModelCatalog, get_candidate_catalog


class TaskType(str, Enum):
    GENERAL_EXPLANATION = "general_explanation"
    COMPLEX_REASONING = "complex_reasoning"
    CODING = "coding"
    IMAGE_UNDERSTANDING = "image_understanding"
    IMAGE_CREATION = "image_creation"
    SPEECH_TRANSCRIPTION = "speech_transcription"
    SPEECH_SYNTHESIS = "speech_synthesis"
    OCR_DOCUMENT_EXTRACTION = "ocr_document_extraction"
    SCIENTIFIC_BIOMEDICAL = "scientific_biomedical"
    SECURITY_ALERT_ANALYSIS = "security_alert_analysis"
    SEMANTIC_RETRIEVAL = "semantic_retrieval"
    PASSAGE_RERANKING = "passage_reranking"


class CollaborationRole(str, Enum):
    PRIMARY_ANALYST = "primary_analyst"
    SPECIALIST = "specialist"
    EVIDENCE_CHECKER = "evidence_checker"
    SAFETY_REVIEWER = "safety_reviewer"
    SYNTHESIZER = "synthesizer"


@dataclass
class RoutingDecision:
    """
    Standard Model-Routing Operation Result (Section 17).
    """
    task_type: TaskType
    input_modalities: List[str]
    output_modalities: List[str]
    selected_model_or_tool: str
    selection_reason: str
    collaborators: List[Dict[str, str]] = field(default_factory=list)
    requires_external_evidence: bool = False
    requires_local_retrieval: bool = False
    execution_succeeded: bool = True
    relevant_evidence: List[str] = field(default_factory=list)
    fallbacks_or_limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_type": self.task_type.value,
            "input_modalities": self.input_modalities,
            "output_modalities": self.output_modalities,
            "selected_model_or_tool": self.selected_model_or_tool,
            "selection_reason": self.selection_reason,
            "collaborators": self.collaborators,
            "requires_external_evidence": self.requires_external_evidence,
            "requires_local_retrieval": self.requires_local_retrieval,
            "execution_succeeded": self.execution_succeeded,
            "relevant_evidence": self.relevant_evidence,
            "fallbacks_or_limitations": self.fallbacks_or_limitations,
        }

    def format_routing_report(self) -> str:
        """Format as specified in Section 17 of the Master System Prompt."""
        lines = [
            f"**Selected Model / Tool**: `{self.selected_model_or_tool}`",
            f"**Why Selected**: {self.selection_reason}",
            f"**Execution Status**: {'Succeeded' if self.execution_succeeded else 'Failed / Deferred'}",
        ]
        if self.relevant_evidence:
            lines.append(f"**Relevant Evidence**: {', '.join(self.relevant_evidence)}")
        if self.fallbacks_or_limitations:
            lines.append(f"**Fallbacks & Limitations**: {'; '.join(self.fallbacks_or_limitations)}")
        return "\n".join(lines)


class IntelligentTaskRouter:
    """
    Classifies requests and routes to the minimal suitable model/tool set
    without blindly calling all models.
    """

    def __init__(self, catalog: Optional[CandidateModelCatalog] = None) -> None:
        self.catalog = catalog or get_candidate_catalog()

    def classify_task(
        self,
        query: str,
        has_images: bool = False,
        has_audio: bool = False,
        has_pdf: bool = False,
    ) -> TaskType:
        """Classify requested task and detect required modalities."""
        text = query.lower()

        # Modality overrides
        if has_images or any(ext in text for ext in (".png", ".jpg", ".jpeg", ".webp", "screenshot", "image of")):
            if any(k in text for k in ("generate", "draw", "create image", "paint", "diffusion", "render image")):
                return TaskType.IMAGE_CREATION
            return TaskType.IMAGE_UNDERSTANDING

        if has_audio or any(k in text for k in ("transcribe", "listen to audio", "whisper", "speech-to-text", "voice recording")):
            return TaskType.SPEECH_TRANSCRIPTION

        if any(k in text for k in ("speak", "read aloud", "text-to-speech", "voice synthesis", "narrate")):
            return TaskType.SPEECH_SYNTHESIS

        if has_pdf or any(k in text for k in ("ocr", "extract text from scan", "scanned document", "extract table from pdf")):
            return TaskType.OCR_DOCUMENT_EXTRACTION

        # Domain classification
        if any(k in text for k in ("firewall", "cve-", "exploit", "soc alert", "malware", "securebert", "siem", "phishing", "nmap", "vulnerability scan")):
            return TaskType.SECURITY_ALERT_ANALYSIS

        if any(k in text for k in ("pubmed", "clinical", "biomedical", "genetics", "pathology", "biomistral", "pharmacology", "dosage")):
            return TaskType.SCIENTIFIC_BIOMEDICAL

        if any(k in text for k in ("def ", "class ", "function", "refactor", "bug in code", "unittest", "pytest", "python script", "sql query", "typescript", "debug")):
            return TaskType.CODING

        if any(k in text for k in ("prove that", "mathematical proof", "derive", "step-by-step logic", "game theory", "formal deduction", "solve theorem")):
            return TaskType.COMPLEX_REASONING

        return TaskType.GENERAL_EXPLANATION

    def route_request(
        self,
        query: str,
        has_images: bool = False,
        has_audio: bool = False,
        has_pdf: bool = False,
        require_local: bool = False,
    ) -> RoutingDecision:
        """
        Execute Section 5 Routing:
          1. Classify task
          2. Identify modalities
          3. Determine evidence requirements
          4. Select smallest suitable set of models
          5. Return routing decision
        """
        task = self.classify_task(query, has_images=has_images, has_audio=has_audio, has_pdf=has_pdf)

        if task == TaskType.IMAGE_CREATION:
            return RoutingDecision(
                task_type=task,
                input_modalities=["text"],
                output_modalities=["image"],
                selected_model_or_tool="Qwen/Qwen-Image-2.1-Turbo",
                selection_reason="Prompt requests visual image creation; routed to candidate diffusion pipeline.",
                fallbacks_or_limitations=["Diffusion model cannot perform general text reasoning; diffusion parameters bounded."],
            )

        if task == TaskType.IMAGE_UNDERSTANDING:
            return RoutingDecision(
                task_type=task,
                input_modalities=["image", "text"],
                output_modalities=["text"],
                selected_model_or_tool="google/gemma-4-26B-A4B",
                selection_reason="Visual question answering or screenshot inspection routed to multimodal vision-language candidate.",
                fallbacks_or_limitations=[
                    "Fallback to microsoft/Fara1.5-27B or Qwen/Qwen3.8-27B if Gemma-4 is unavailable or specialized UI navigation is needed."
                ],
            )

        if task == TaskType.SPEECH_TRANSCRIPTION:
            return RoutingDecision(
                task_type=task,
                input_modalities=["audio"],
                output_modalities=["text"],
                selected_model_or_tool="openai/whisper-large-v3",
                selection_reason="Audio stream transcription routed to Whisper ASR pipeline preserving timestamps and confidence.",
                fallbacks_or_limitations=["Preserves word timestamps; audio must be clear and within max duration."],
            )

        if task == TaskType.SPEECH_SYNTHESIS:
            return RoutingDecision(
                task_type=task,
                input_modalities=["text"],
                output_modalities=["audio"],
                selected_model_or_tool="hexgrad/Kokoro-82M",
                selection_reason="Text-to-speech request routed to Kokoro TTS client.",
                fallbacks_or_limitations=["Output is raw audio bytes; does not evaluate semantic validity."],
            )

        if task == TaskType.OCR_DOCUMENT_EXTRACTION:
            return RoutingDecision(
                task_type=task,
                input_modalities=["image", "pdf"],
                output_modalities=["structured_json", "markdown"],
                selected_model_or_tool="PaddleOCR-VL",
                selection_reason="Document text/table extraction routed to specialized PaddleOCR-VL pipeline.",
                fallbacks_or_limitations=["Preserves bounding boxes and table layouts; requires OCR-compatible runtime."],
            )

        if task == TaskType.SECURITY_ALERT_ANALYSIS:
            return RoutingDecision(
                task_type=task,
                input_modalities=["text"],
                output_modalities=["text"],
                selected_model_or_tool="cisco-ai/SecureBERT2.0-base + Guardian Defensive Engine",
                selection_reason="Security telemetry analysis; SecureBERT handles terminology/classification while primary model synthesizes remediation.",
                collaborators=[
                    {"role": CollaborationRole.SPECIALIST.value, "model": "cisco-ai/SecureBERT2.0-base"},
                    {"role": CollaborationRole.SAFETY_REVIEWER.value, "model": "Guardian Security Policy Engine"},
                ],
                requires_local_retrieval=True,
                fallbacks_or_limitations=[
                    "SecureBERT is an assistive masked-LM; not an intrusion prevention system or firewall authority. Advisory mode enforced."
                ],
            )

        if task == TaskType.SCIENTIFIC_BIOMEDICAL:
            return RoutingDecision(
                task_type=task,
                input_modalities=["text"],
                output_modalities=["text"],
                selected_model_or_tool="BioMistral/BioMistral-7B",
                selection_reason="Biomedical literature and terminology assistance routed to domain-specialist candidate with academic retrieval.",
                requires_external_evidence=True,
                collaborators=[
                    {"role": CollaborationRole.SPECIALIST.value, "model": "BioMistral/BioMistral-7B"},
                    {"role": CollaborationRole.EVIDENCE_CHECKER.value, "model": "AcademicResearchClient (OpenAlex/Crossref)"},
                ],
                fallbacks_or_limitations=[
                    "Assistive literature research only; NEVER a substitute for qualified professional clinical judgment."
                ],
            )

        if task == TaskType.COMPLEX_REASONING:
            return RoutingDecision(
                task_type=task,
                input_modalities=["text"],
                output_modalities=["text"],
                selected_model_or_tool="deepseek-ai/DeepSeek-R1",
                selection_reason="Complex multi-step formal reasoning routed to reasoning-specialist candidate.",
                collaborators=[
                    {"role": CollaborationRole.PRIMARY_ANALYST.value, "model": "deepseek-ai/DeepSeek-R1"},
                    {"role": CollaborationRole.EVIDENCE_CHECKER.value, "model": "Code Execution / Verifier Sandbox"},
                ],
                fallbacks_or_limitations=[
                    "Remote code sandbox required for DeepSeek-R1. Bounded computation applied."
                ],
            )

        if task == TaskType.CODING:
            return RoutingDecision(
                task_type=task,
                input_modalities=["text"],
                output_modalities=["text"],
                selected_model_or_tool="openai/gpt-oss-120b",
                selection_reason="Code generation and repository analysis routed to coding-capable primary candidate.",
                collaborators=[
                    {"role": CollaborationRole.PRIMARY_ANALYST.value, "model": "openai/gpt-oss-120b"},
                    {"role": CollaborationRole.EVIDENCE_CHECKER.value, "model": "Static Analysis / Test Verifier"},
                ],
                fallbacks_or_limitations=[
                    "Fallback to deepseek-ai/DeepSeek-V4-Pro or local Ollama if offline. Code must be verified via unit tests."
                ],
            )

        # General explanation
        return RoutingDecision(
            task_type=task,
            input_modalities=["text"],
            output_modalities=["text"],
            selected_model_or_tool="openai/gpt-oss-120b",
            selection_reason="Standard conversational knowledge question routed to primary language model.",
            fallbacks_or_limitations=[
                "Fallback to deepseek-ai/DeepSeek-V4-Pro or active default backend (Groq/Ollama/Gemini)."
            ],
        )


# Singleton router
_global_router: Optional[IntelligentTaskRouter] = None


def get_task_router() -> IntelligentTaskRouter:
    global _global_router
    if _global_router is None:
        _global_router = IntelligentTaskRouter()
    return _global_router
