"""
Guardian Knowledge — 25 World Knowledge Domains & Ontological Layers
====================================================================
Implements the Universal Knowledge Taxonomy from the Universal Intelligence Blueprint.

Architecture:
  - 6 Ontological Layers (Foundations -> Integrated Intelligence)
  - 25 Master Academic, Scientific & Practical Knowledge Domains
  - 15 Study Dimensions per domain
  - Automatic Domain Classification & Metadata Tagging
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class KnowledgeLayerEnum(str, Enum):
    """The 6 ontological knowledge layers organizing world understanding."""
    FOUNDATIONS = "Layer 1: Foundations"
    NATURAL_WORLD = "Layer 2: Natural World"
    HUMAN_BEINGS = "Layer 3: Human Beings"
    HUMAN_SOCIETIES = "Layer 4: Human Societies"
    BUILT_AND_DIGITAL = "Layer 5: Built and Digital World"
    INTEGRATED_INTELLIGENCE = "Layer 6: Integrated Intelligence"


STUDY_DIMENSIONS: list[str] = [
    "Fundamentals",
    "Concepts",
    "Principles",
    "Evidence",
    "Methods",
    "Mathematics",
    "Causality",
    "Applications",
    "Tools",
    "History",
    "Limitations",
    "Ethics",
    "Connections",
    "Evaluation",
    "Updates",
]


@dataclass(frozen=True)
class KnowledgeDomain:
    """A master knowledge domain within the universal taxonomy."""
    code: str
    name: str
    layer: KnowledgeLayerEnum
    description: str
    subdomains: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# The 25 Master Knowledge Domains
# ---------------------------------------------------------------------------

DOMAINS: dict[str, KnowledgeDomain] = {
    # Layer 1 — Foundations
    "math_formal": KnowledgeDomain(
        code="math_formal",
        name="Mathematics and Formal Sciences",
        layer=KnowledgeLayerEnum.FOUNDATIONS,
        description="The foundations of quantitative reasoning, abstraction, logic, and proof.",
        subdomains=["logic", "set_theory", "algebra", "geometry", "calculus", "probability", "statistics", "optimization", "graph_theory", "formal_methods"],
        keywords=["math", "proof", "matrix", "vector", "algebra", "calculus", "theorem", "topology", "statistics", "probability"],
    ),
    "research_methods": KnowledgeDomain(
        code="research_methods",
        name="Research Methods and Scientific Practice",
        layer=KnowledgeLayerEnum.FOUNDATIONS,
        description="How to establish reliable knowledge, experimental design, and causal inference.",
        subdomains=["scientific_method", "experimental_design", "causal_inference", "bayesian_methods", "reproducibility", "meta_analysis"],
        keywords=["hypothesis", "experiment", "causal", "bayesian", "p-value", "meta-analysis", "reproducibility", "falsifiable"],
    ),
    "philosophy_ethics": KnowledgeDomain(
        code="philosophy_ethics",
        name="Philosophy, Ethics, and Epistemology",
        layer=KnowledgeLayerEnum.FOUNDATIONS,
        description="Knowledge, reality, reasoning, moral values, and human decision theory.",
        subdomains=["epistemology", "ethics", "metaphysics", "philosophy_of_science", "decision_theory", "ai_ethics"],
        keywords=["ethics", "moral", "epistemology", "metaphysics", "justice", "utilitarianism", "deontology", "duty", "virtue"],
    ),

    # Layer 2 — Natural World
    "physics_astronomy": KnowledgeDomain(
        code="physics_astronomy",
        name="Physics and Astronomy",
        layer=KnowledgeLayerEnum.NATURAL_WORLD,
        description="Matter, energy, space, time, and the physical universe.",
        subdomains=["mechanics", "electromagnetism", "thermodynamics", "quantum_physics", "relativity", "astrophysics", "cosmology"],
        keywords=["physics", "quantum", "gravity", "energy", "force", "photon", "particle", "relativity", "cosmology", "astronomy"],
    ),
    "chemistry_materials": KnowledgeDomain(
        code="chemistry_materials",
        name="Chemistry and Materials Science",
        layer=KnowledgeLayerEnum.NATURAL_WORLD,
        description="Atoms, molecules, chemical reactions, and engineered materials.",
        subdomains=["organic_chemistry", "inorganic_chemistry", "biochemistry", "nanotechnology", "polymers", "metallurgy", "semiconductors"],
        keywords=["molecule", "atom", "reaction", "catalyst", "polymer", "crystal", "chemical", "nanomaterial", "alloy"],
    ),
    "biology_life": KnowledgeDomain(
        code="biology_life",
        name="Biology and Life Sciences",
        layer=KnowledgeLayerEnum.NATURAL_WORLD,
        description="Living systems, evolution, cellular biology, and ecosystems.",
        subdomains=["molecular_biology", "genetics", "evolution", "ecology", "microbiology", "neuroscience", "bioinformatics"],
        keywords=["cell", "dna", "rna", "gene", "protein", "organism", "evolution", "ecology", "ecosystem", "bacteria", "virus"],
    ),
    "earth_environmental": KnowledgeDomain(
        code="earth_environmental",
        name="Earth and Environmental Sciences",
        layer=KnowledgeLayerEnum.NATURAL_WORLD,
        description="The planet, geology, atmosphere, climate, and environmental resources.",
        subdomains=["geology", "meteorology", "climatology", "oceanography", "hydrology", "gis", "sustainability"],
        keywords=["climate", "geology", "atmosphere", "ocean", "weather", "seismic", "environment", "biodiversity", "sustainability"],
    ),

    # Layer 3 — Human Beings
    "medicine_health": KnowledgeDomain(
        code="medicine_health",
        name="Medicine and Health Sciences",
        layer=KnowledgeLayerEnum.HUMAN_BEINGS,
        description="Human health, disease, clinical diagnostics, treatment, and public health.",
        subdomains=["anatomy", "pharmacology", "clinical_medicine", "epidemiology", "public_health", "oncology", "neurology"],
        keywords=["patient", "disease", "clinical", "drug", "symptom", "diagnosis", "health", "therapy", "surgery", "pathology"],
    ),
    "psychology_cognitive": KnowledgeDomain(
        code="psychology_cognitive",
        name="Psychology and Cognitive Science",
        layer=KnowledgeLayerEnum.HUMAN_BEINGS,
        description="Mind, behavior, cognition, learning, attention, and decision-making.",
        subdomains=["cognitive_psychology", "behavioral_science", "neuroscience", "perception", "memory", "decision_making"],
        keywords=["cognition", "memory", "perception", "psychology", "behavior", "bias", "emotion", "mental", "stimulus"],
    ),
    "language_linguistics": KnowledgeDomain(
        code="language_linguistics",
        name="Language and Linguistics",
        layer=KnowledgeLayerEnum.HUMAN_BEINGS,
        description="How humans communicate, represent meaning, grammar, and structure language.",
        subdomains=["syntax", "semantics", "pragmatics", "phonetics", "computational_linguistics", "translation"],
        keywords=["grammar", "syntax", "semantics", "linguistics", "phonetics", "morpheme", "lexicon", "translation"],
    ),

    # Layer 4 — Human Societies
    "economics_finance": KnowledgeDomain(
        code="economics_finance",
        name="Economics and Finance",
        layer=KnowledgeLayerEnum.HUMAN_SOCIETIES,
        description="Markets, resources, monetary systems, investment, and economic incentives.",
        subdomains=["microeconomics", "macroeconomics", "econometrics", "corporate_finance", "banking", "asset_pricing", "fintech"],
        keywords=["market", "inflation", "gdp", "interest", "capital", "investment", "finance", "fiscal", "liquidity", "portfolio"],
    ),
    "political_law": KnowledgeDomain(
        code="political_law",
        name="Political Science, Law, and Governance",
        layer=KnowledgeLayerEnum.HUMAN_SOCIETIES,
        description="Power, legal systems, rights, jurisprudence, policy, and public institutions.",
        subdomains=["constitutional_law", "international_law", "comparative_politics", "public_policy", "diplomacy", "ai_governance"],
        keywords=["law", "constitution", "statute", "court", "rights", "governance", "treaty", "policy", "sovereignty", "regulation"],
    ),
    "sociology_social": KnowledgeDomain(
        code="sociology_social",
        name="Sociology and Social Sciences",
        layer=KnowledgeLayerEnum.HUMAN_SOCIETIES,
        description="People, institutions, social groups, demography, and cultural structures.",
        subdomains=["sociology", "anthropology", "demography", "criminology", "social_networks", "migration"],
        keywords=["social", "culture", "demographic", "society", "community", "institution", "inequality", "population"],
    ),
    "history_archaeology": KnowledgeDomain(
        code="history_archaeology",
        name="History and Archaeology",
        layer=KnowledgeLayerEnum.HUMAN_SOCIETIES,
        description="Humanity's past, civilizations, primary sources, and historical developments.",
        subdomains=["world_history", "archaeology", "historiography", "intellectual_history", "military_history"],
        keywords=["history", "century", "ancient", "civilization", "archaeology", "artifact", "medieval", "chronology"],
    ),
    "religion_theology": KnowledgeDomain(
        code="religion_theology",
        name="Religion and Theology",
        layer=KnowledgeLayerEnum.HUMAN_SOCIETIES,
        description="Religious traditions, texts, practices, institutions, and comparative studies.",
        subdomains=["comparative_religion", "theology", "scriptural_studies", "religious_history"],
        keywords=["religion", "theology", "scripture", "faith", "ritual", "spiritual", "tradition"],
    ),
    "international_studies": KnowledgeDomain(
        code="international_studies",
        name="International and Area Studies",
        layer=KnowledgeLayerEnum.HUMAN_SOCIETIES,
        description="Geopolitics, regional security, cultures, and relations between nations.",
        subdomains=["geopolitics", "regional_security", "international_development", "cross_cultural_communication"],
        keywords=["geopolitics", "international", "global", "diplomacy", "alliance", "regional", "treaty"],
    ),

    # Layer 5 — Built & Digital World
    "cs_ai": KnowledgeDomain(
        code="cs_ai",
        name="Computer Science and Artificial Intelligence",
        layer=KnowledgeLayerEnum.BUILT_AND_DIGITAL,
        description="Algorithms, software engineering, intelligent systems, cybersecurity, and data systems.",
        subdomains=["algorithms", "operating_systems", "machine_learning", "deep_learning", "nlp", "cybersecurity", "databases"],
        keywords=["algorithm", "software", "python", "neural", "compiler", "database", "security", "encryption", "agent", "llm"],
    ),
    "engineering_tech": KnowledgeDomain(
        code="engineering_tech",
        name="Engineering and Technology",
        layer=KnowledgeLayerEnum.BUILT_AND_DIGITAL,
        description="Applying scientific principles to build and operate physical and digital systems.",
        subdomains=["mechanical", "electrical", "civil", "aerospace", "robotics", "systems_engineering"],
        keywords=["engineering", "voltage", "circuit", "mechanical", "structure", "robotics", "hardware", "design", "turbines"],
    ),
    "business_management": KnowledgeDomain(
        code="business_management",
        name="Business and Management",
        layer=KnowledgeLayerEnum.BUILT_AND_DIGITAL,
        description="Organizations, business strategy, supply chains, product, and value creation.",
        subdomains=["strategy", "operations", "marketing", "supply_chain", "project_management", "entrepreneurship"],
        keywords=["business", "strategy", "management", "supply", "revenue", "product", "agile", "marketing", "customer"],
    ),
    "arts_design": KnowledgeDomain(
        code="arts_design",
        name="Arts, Design, and Architecture",
        layer=KnowledgeLayerEnum.BUILT_AND_DIGITAL,
        description="Creative visual expression, UI/UX, typography, architecture, and aesthetic environments.",
        subdomains=["fine_art", "graphic_design", "ux_ui", "architecture", "industrial_design", "composition"],
        keywords=["art", "design", "architecture", "aesthetic", "visual", "composition", "drawing", "typography"],
    ),
    "education_learning": KnowledgeDomain(
        code="education_learning",
        name="Education and Learning Sciences",
        layer=KnowledgeLayerEnum.BUILT_AND_DIGITAL,
        description="How humans learn, pedagogical methods, curriculum design, and assessment.",
        subdomains=["pedagogy", "instructional_design", "educational_psychology", "edtech", "curriculum"],
        keywords=["education", "learning", "pedagogy", "curriculum", "teaching", "student", "classroom", "assessment"],
    ),
    "agriculture_food": KnowledgeDomain(
        code="agriculture_food",
        name="Agriculture, Food, and Veterinary Sciences",
        layer=KnowledgeLayerEnum.BUILT_AND_DIGITAL,
        description="Food production, animal health, agronomy, aquaculture, and food safety.",
        subdomains=["agronomy", "veterinary", "crop_science", "food_safety", "soil_management"],
        keywords=["agriculture", "crop", "farming", "soil", "harvest", "veterinary", "livestock", "food"],
    ),
    "urban_infrastructure": KnowledgeDomain(
        code="urban_infrastructure",
        name="Urban Planning, Transport, and Infrastructure",
        layer=KnowledgeLayerEnum.BUILT_AND_DIGITAL,
        description="Cities, transport networks, energy systems, water, and civil infrastructure.",
        subdomains=["urban_planning", "transport_engineering", "smart_cities", "civil_infrastructure"],
        keywords=["urban", "transit", "infrastructure", "traffic", "city", "transport", "housing", "power_grid"],
    ),
    "practical_knowledge": KnowledgeDomain(
        code="practical_knowledge",
        name="Practical and Professional Knowledge",
        layer=KnowledgeLayerEnum.BUILT_AND_DIGITAL,
        description="Everyday trade skills, workplace safety, personal finance, and practical execution.",
        subdomains=["workplace_safety", "personal_finance", "construction_trades", "troubleshooting", "first_aid"],
        keywords=["safety", "maintenance", "troubleshooting", "repair", "plumbing", "electrical", "first_aid"],
    ),

    # Layer 6 — Integrated Intelligence
    "emerging_interdisciplinary": KnowledgeDomain(
        code="emerging_interdisciplinary",
        name="Emerging Interdisciplinary Fields",
        layer=KnowledgeLayerEnum.INTEGRATED_INTELLIGENCE,
        description="Novel fields at the frontier: AI safety, AGI, quantum information, climate tech, and digital twins.",
        subdomains=["ai_safety", "agi_research", "quantum_computing", "computational_biology", "climate_tech", "digital_twins"],
        keywords=["agi", "ai_safety", "alignment", "quantum_information", "synthetic_biology", "digital_twin", "interdisciplinary"],
    ),
}


def get_all_domains() -> list[KnowledgeDomain]:
    """Return all 25 registered knowledge domains."""
    return list(DOMAINS.values())


def get_domain(code: str) -> KnowledgeDomain | None:
    """Retrieve a domain by its code."""
    return DOMAINS.get(code)


def classify_domain_context(text: str, top_k: int = 3) -> list[KnowledgeDomain]:
    """
    Classify a piece of text or user query into relevant knowledge domains
    based on keyword frequency and semantic matching.
    """
    scores: dict[str, int] = {code: 0 for code in DOMAINS}
    lower_text = text.lower()

    for code, domain in DOMAINS.items():
        # Score by keywords
        for kw in domain.keywords:
            if kw in lower_text:
                scores[code] += 2
        # Score by subdomains
        for sub in domain.subdomains:
            if sub.replace("_", " ") in lower_text:
                scores[code] += 3

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    results = [DOMAINS[code] for code, score in ranked if score > 0][:top_k]

    # Default to cs_ai and math_formal if no explicit keywords found
    if not results:
        results = [DOMAINS["cs_ai"]]
    return results
