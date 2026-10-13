"""
Guardian Knowledge — Document Loader
======================================
Loads documents from the filesystem into plain text for chunking.

Supported formats:
  .txt  .md  .rst  .log  — read directly as UTF-8
  .py   .js  .ts  .yaml .json .toml .cfg  — source code / config
  .pdf  — extracted via pypdf (BSD-3 license) ✅
  Other binary formats — skipped with a warning

Authority: Level 0 — read-only.
License: pypdf (BSD-3) ✅.  NOT pymupdf (GPL v3) — do not use.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from guardian.logging.logger import get_logger

log = get_logger(__name__)

# Text-based extensions — read directly
_TEXT_EXTENSIONS = {
    ".txt", ".md", ".rst", ".log", ".csv",
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".yaml", ".yml", ".json", ".toml", ".cfg", ".ini",
    ".html", ".css", ".sql", ".sh", ".bat", ".ps1",
    ".c", ".cpp", ".h", ".java", ".go", ".rs",
    ".xml", ".env.example", ".gitignore",
}

_SKIP_DIRS = {
    ".git", "__pycache__", "venv", ".venv", "node_modules",
    ".pytest_cache", "dist", "build", ".mypy_cache",
}


@dataclass
class Document:
    """A loaded document ready for chunking."""
    path: Path
    content: str
    source_label: str   # relative path string for storage metadata
    extension: str
    size_bytes: int


class DocumentLoader:
    """
    Loads files into Documents.

    Usage:
        loader = DocumentLoader(workspace_root)
        doc = loader.load(Path("guardian/GUARDIAN_CONSTITUTION_v0.1.md"))
        docs = list(loader.load_directory(Path("docs/")))
    """

    def __init__(self, workspace_root: Path) -> None:
        self.root = workspace_root.resolve()

    def load(self, path: Path) -> Document | None:
        """
        Load a single file. Returns None if the file cannot be loaded
        (binary, unsupported format, too large, unreadable).
        """
        resolved = path if path.is_absolute() else (self.root / path)
        resolved = resolved.resolve()

        if not resolved.exists():
            log.warning(f"DocumentLoader: file not found: {resolved}")
            return None
        if not resolved.is_file():
            log.warning(f"DocumentLoader: not a file: {resolved}")
            return None

        # Compute relative label for metadata
        try:
            rel = str(resolved.relative_to(self.root))
        except ValueError:
            rel = str(resolved)

        ext = resolved.suffix.lower()
        size = resolved.stat().st_size

        if size == 0:
            log.debug(f"DocumentLoader: skipping empty file: {rel}")
            return None

        if ext == ".pdf":
            content = self._load_pdf(resolved, rel)
        elif ext in _TEXT_EXTENSIONS or resolved.name.startswith("."):
            content = self._load_text(resolved, rel)
        else:
            log.debug(f"DocumentLoader: skipping unsupported extension {ext!r}: {rel}")
            return None

        if not content or not content.strip():
            log.debug(f"DocumentLoader: skipping empty content: {rel}")
            return None

        return Document(
            path=resolved,
            content=content,
            source_label=rel,
            extension=ext,
            size_bytes=size,
        )

    def load_directory(
        self,
        directory: Path,
        recursive: bool = True,
    ) -> Iterator[Document]:
        """
        Yield Documents from all loadable files in a directory.
        Skips hidden dirs, caches, venv, etc.
        """
        resolved = directory if directory.is_absolute() else (self.root / directory)
        resolved = resolved.resolve()

        if not resolved.is_dir():
            log.warning(f"DocumentLoader: not a directory: {resolved}")
            return

        glob = "**/*" if recursive else "*"
        for path in sorted(resolved.glob(glob)):
            if not path.is_file():
                continue
            if any(skip in path.parts for skip in _SKIP_DIRS):
                continue
            doc = self.load(path)
            if doc is not None:
                yield doc

    def _load_text(self, path: Path, label: str) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            log.warning(f"DocumentLoader: read error {label}: {exc}")
            return ""

    def _load_pdf(self, path: Path, label: str) -> str:
        try:
            from pypdf import PdfReader
        except ImportError:
            log.warning("pypdf not installed — PDF loading disabled. Run: pip install pypdf")
            return ""
        try:
            reader = PdfReader(str(path))
            pages: list[str] = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(f"[Page {i+1}]\n{text}")
            return "\n\n".join(pages)
        except Exception as exc:
            log.warning(f"DocumentLoader: PDF read error {label}: {exc}")
            return ""
