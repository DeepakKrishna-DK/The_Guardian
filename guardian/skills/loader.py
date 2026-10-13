import os
import yaml
from pathlib import Path
from guardian.skills.base import Skill

def load_skills_from_directory(directory: str | Path) -> list[Skill]:
    skills = []
    dir_path = Path(directory)
    if not dir_path.exists() or not dir_path.is_dir():
        return skills
        
    for file_path in dir_path.glob("*.md"):
        content = file_path.read_text(encoding="utf-8")
        if not content.startswith("---\n"):
            continue
            
        parts = content.split("---\n", 2)
        if len(parts) < 3:
            continue
            
        frontmatter_str = parts[1]
        body = parts[2].strip()
        
        try:
            meta = yaml.safe_load(frontmatter_str)
            skill = Skill(
                name=meta["name"],
                title=meta["title"],
                description=meta["description"],
                prompt_addition=body,
                keywords=meta.get("keywords", []),
                icon=meta.get("icon", ""),
                min_confidence=meta.get("min_confidence", 1),
                local_only=meta.get("local_only", False),
                risk_tier=meta.get("risk_tier", 0),
                requires_scope=meta.get("requires_scope", False),
                target_arg=meta.get("target_arg"),
                dependencies=meta.get("dependencies", [])
            )
            skills.append(skill)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to load skill {file_path}: {e}")
            
    return skills
