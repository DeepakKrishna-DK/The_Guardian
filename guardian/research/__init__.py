"""
Guardian Academic Research System — Public API
==============================================
Usage:
    from guardian.research import (
        AcademicPaper,
        AcademicResearchClient,
        AcademicResearchPipeline,
    )

    client = AcademicResearchClient()
    papers = client.search("quantum error correction")
    for p in papers:
        print(p.citation_str())
"""

from __future__ import annotations

from guardian.research.academic import (
    AcademicPaper,
    AcademicResearchClient,
    reconstruct_abstract,
)
from guardian.research.pipeline import (
    SCIENTIFIC_RESEARCH_SYSTEM_PROMPT,
    AcademicResearchPipeline,
    ResearchSynthesisResult,
)

__all__ = [
    "AcademicPaper",
    "AcademicResearchClient",
    "AcademicResearchPipeline",
    "ResearchSynthesisResult",
    "SCIENTIFIC_RESEARCH_SYSTEM_PROMPT",
    "reconstruct_abstract",
]
