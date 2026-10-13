"""
Guardian Knowledge — Embedder
================================
Converts text chunks into dense vector representations.

Embedders:
  SentenceTransformerEmbedder — real embeddings via sentence-transformers
      Model: all-MiniLM-L6-v2 (Apache 2.0, 80 MB, 384 dims)
      Downloaded once to ~/.cache/huggingface on first use.
      Works on CPU; uses GPU if available.

  MockEmbedder — deterministic fake embeddings for tests
      No model download, no network, no torch.
      Vectors are normalised but not semantically meaningful.

Constitution: Level 0 — read-only compute, no external API calls for embedding.
License: sentence-transformers (Apache 2.0) ✅, torch (BSD-3) ✅
"""

from __future__ import annotations

import hashlib
import math
import random
from abc import ABC, abstractmethod

DEFAULT_MODEL = "all-MiniLM-L6-v2"
DEFAULT_DIMS  = 384


class Embedder(ABC):
    """Abstract base for all embedding backends."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return L2-normalised float vectors for each text."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Vector dimensionality."""


class MockEmbedder(Embedder):
    """
    Deterministic embedder for tests — no model, no network.
    Vectors are deterministically derived from text content,
    normalised, and compatible with cosine similarity queries.
    """

    def __init__(self, dims: int = DEFAULT_DIMS) -> None:
        self._dims = dims

    def embed(self, texts: list[str]) -> list[list[float]]:
        result: list[list[float]] = []
        for text in texts:
            seed = int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**32)
            rng  = random.Random(seed)
            vec  = [rng.gauss(0, 1) for _ in range(self._dims)]
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            result.append([x / norm for x in vec])
        return result

    @property
    def dimensions(self) -> int:
        return self._dims


class SentenceTransformerEmbedder(Embedder):
    """
    Real embeddings using sentence-transformers (Apache 2.0).
    Model is lazy-loaded on first call — downloaded once to HF cache.

    Usage:
        embedder = SentenceTransformerEmbedder()
        vecs = embedder.embed(["What is a firewall?", "How does TLS work?"])
    """

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self._model_name = model_name
        self._model = None   # lazy init

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required for real embeddings. "
                    "Run: pip install sentence-transformers"
                )
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vecs]

    @property
    def dimensions(self) -> int:
        # all-MiniLM-L6-v2 → 384 dims; BGE-M3 → 1024; etc.
        if self._model is not None:
            return self._model.get_sentence_embedding_dimension()
        # Return default without loading
        return DEFAULT_DIMS

    @property
    def model_name(self) -> str:
        return self._model_name
