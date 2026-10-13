from dataclasses import dataclass, field
import json
from pathlib import Path
from datetime import datetime, timezone

@dataclass
class ComplianceReference:
    """
    Law/regulation citations relevant to authorized security testing.
    DISCLAIMER: This is reference material only, not legal advice, 
    and must be kept current by the owner. It does not constitute a legal determination.
    """
    id: str
    title: str
    description: str
    source_url: str
    last_verified: str
    
class ComplianceStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._cache: dict[str, ComplianceReference] = {}
        self.load()
        
    def load(self):
        if self.db_path.exists():
            try:
                data = json.loads(self.db_path.read_text(encoding="utf-8"))
                for k, v in data.items():
                    self._cache[k] = ComplianceReference(**v)
            except Exception:
                pass
                
    def save(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: {"id": v.id, "title": v.title, "description": v.description, "source_url": v.source_url, "last_verified": v.last_verified} for k, v in self._cache.items()}
        self.db_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        
    def get_all(self) -> list[ComplianceReference]:
        return list(self._cache.values())
        
    def get(self, ref_id: str) -> ComplianceReference | None:
        return self._cache.get(ref_id)
        
    def add_or_update(self, ref: ComplianceReference):
        self._cache[ref.id] = ref
        self.save()

    def delete(self, ref_id: str):
        if ref_id in self._cache:
            del self._cache[ref_id]
            self.save()
