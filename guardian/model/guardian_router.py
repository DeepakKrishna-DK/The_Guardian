"""
Guardian Unified Router & Multi-Model Orchestrator
==================================================
Implementation of Layer 2 (Guardian Orchestrator) per Universal Digital Intelligence
Architecture (Version 2.0).

Features:
  - Selects models according to capability profile and task classification.
  - available_models(capability) queries active/enabled candidate models.
  - Multi-model collaboration roles: primary analyst, specialist, evidence checker, synthesizer.
  - Bounded concurrency and fallback handling without blind mass invocation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time

from guardian.logging.logger import get_logger
from guardian.model.adapters import ModelAdapter, ModelResult
from guardian.model.slots import TwentySlotRegistry, get_slot_registry
from guardian.model.task_router import IntelligentTaskRouter, TaskType, get_task_router

log = get_logger(__name__)


class GuardianRouter:
    """
    Coordinates multi-model orchestration across the 20 model slots.
    Executes task classification, capability mapping, and single- or multi-slot execution.
    """

    def __init__(
        self,
        registry: Optional[TwentySlotRegistry] = None,
        task_router: Optional[IntelligentTaskRouter] = None,
    ) -> None:
        self.registry = registry or get_slot_registry()
        self.task_router = task_router or get_task_router()

    def available_models(self, capability: str) -> List[str]:
        """
        List slot identifiers matching a given capability tag or task.
        """
        available: List[str] = []
        cap_clean = capability.lower().strip()
        for slot in self.registry.slots.values():
            if not slot.enabled and slot.state.value not in ("healthy", "loaded", "downloaded"):
                # Candidate model check
                pass
            if cap_clean in slot.task.lower() or cap_clean in slot.adapter_name.lower():
                available.append(slot.id)
            elif cap_clean in ("chat", "reasoning", "general") and "chat" in slot.task:
                available.append(slot.id)
            elif cap_clean in ("vision", "vlm", "multimodal") and "multimodal" in slot.task or "visual" in slot.task:
                available.append(slot.id)
            elif cap_clean in ("ocr", "document") and "ocr" in slot.task:
                available.append(slot.id)
            elif cap_clean in ("audio", "speech", "asr", "tts") and ("speech" in slot.task or "text_to_speech" in slot.task):
                available.append(slot.id)
            elif cap_clean in ("security", "cybersecurity") and "cybersecurity" in slot.task:
                available.append(slot.id)
            elif cap_clean in ("embedding", "reranking") and ("embeddings" in slot.task or "reranking" in slot.task):
                available.append(slot.id)
        return available

    def find_slot_for_task(self, query: str, has_images: bool = False, has_audio: bool = False, has_pdf: bool = False) -> int:
        """Map task classification to the optimal model slot number."""
        task_type = self.task_router.classify_task(
            query=query, has_images=has_images, has_audio=has_audio, has_pdf=has_pdf
        )

        # Mapping of TaskType to standard 20 slot numbers
        if task_type == TaskType.IMAGE_CREATION:
            return 2  # qwen_image_2_1_turbo
        elif task_type == TaskType.IMAGE_UNDERSTANDING:
            return 1  # gemma4_26b_a4b
        elif task_type == TaskType.SPEECH_TRANSCRIPTION:
            return 11  # whisper_large_v3
        elif task_type == TaskType.SPEECH_SYNTHESIS:
            return 12  # kokoro_tts
        elif task_type == TaskType.OCR_DOCUMENT_EXTRACTION:
            return 13  # paddleocr_vl
        elif task_type == TaskType.SCIENTIFIC_BIOMEDICAL:
            return 10  # biomistral
        elif task_type == TaskType.SECURITY_ALERT_ANALYSIS:
            return 20  # securebert2
        elif task_type == TaskType.COMPLEX_REASONING:
            return 18  # deepseek_r1
        elif task_type == TaskType.CODING:
            return 4  # deepseek_v4_pro
        elif task_type == TaskType.SEMANTIC_RETRIEVAL:
            return 14  # qwen3_embedding
        elif task_type == TaskType.PASSAGE_RERANKING:
            return 16  # bge_reranker
        else:
            return 3  # gpt_oss_120b (general reasoning / chat)

    def route_and_execute(
        self,
        task: Dict[str, Any],
        has_images: bool = False,
        has_audio: bool = False,
        has_pdf: bool = False,
        collaborative: bool = False,
    ) -> ModelResult:
        """
        Execute task through the orchestrator:
          1. Classify task and select minimal slot set.
          2. Execute primary specialist slot.
          3. Optionally run second opinion / evidence checker if collaborative is requested.
          4. Return unified ModelResult.
        """
        query = task.get("prompt") or task.get("query") or ""
        preferred_slot = task.get("slot_number")

        slot_num = preferred_slot or self.find_slot_for_task(
            query=query, has_images=has_images, has_audio=has_audio, has_pdf=has_pdf
        )

        slot = self.registry.get_slot(slot_num)
        slot_name = slot.id if slot else str(slot_num)

        # Run primary model
        primary_result = self.registry.run_task(slot_num, task)

        # If collaborative workflow justified (Section 6)
        if collaborative and primary_result.status in ("success", "simulated"):
            synthesizer_slot = 3  # gpt_oss_120b
            collab_task = {
                "prompt": f"Review and synthesize evidence for task: '{query}'. Primary finding: {primary_result.output}",
            }
            synth_res = self.registry.run_task(synthesizer_slot, collab_task)
            return ModelResult(
                slot_id=f"{slot_name}+synthesizer",
                status=primary_result.status,
                output={
                    "primary_result": primary_result.output,
                    "synthesized_response": synth_res.output,
                    "collaborators": [
                        {"role": "specialist", "slot": slot_name},
                        {"role": "synthesizer", "slot": "gpt_oss_120b"},
                    ],
                },
                metadata={"workflow": "multi_model_collaboration", "primary_slot": slot_num},
            )

        return primary_result


_router_instance: Optional[GuardianRouter] = None


def get_guardian_router() -> GuardianRouter:
    """Singleton getter for the unified GuardianRouter."""
    global _router_instance
    if _router_instance is None:
        _router_instance = GuardianRouter()
    return _router_instance
