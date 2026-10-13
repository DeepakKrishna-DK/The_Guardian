import os
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock
from guardian.skills.loader import load_skills_from_directory
from guardian.skills.base import Skill
from guardian.core.orchestrator import GuardianCore, Session
from guardian.model.backends.mock import MockBackend
from guardian.policy.engine import PolicyEngine, PolicyConfig

def test_metadata_loads(tmp_path):
    # Test 1: metadata loads
    skill_file = tmp_path / "test_skill.md"
    frontmatter = {
        "name": "test_skill",
        "title": "Test",
        "description": "Test",
        "keywords": ["test"],
        "icon": "[T]",
        "min_confidence": 1,
        "local_only": False,
        "risk_tier": 1,
        "requires_scope": True,
        "target_arg": "target",
        "dependencies": ["other"]
    }
    skill_file.write_text("---\n" + yaml.dump(frontmatter) + "---\nBody", encoding="utf-8")
    
    skills = load_skills_from_directory(tmp_path)
    assert len(skills) == 1
    s = skills[0]
    assert s.name == "test_skill"
    assert s.risk_tier == 1
    assert s.requires_scope is True
    assert s.dependencies == ["other"]

def test_risk_tier_requires_approval():
    # Test 2: risk_tier>=1 skill requires approval (PolicyEngine evaluates it)
    mock = MockBackend()
    core = GuardianCore(model=mock)
    session = Session()
    
    # We will mock the registry to return a high-risk skill
    from guardian.skills import get_skill_registry
    registry = get_skill_registry()
    
    high_risk_skill = Skill(
        name="high_risk",
        title="High Risk",
        description="High risk",
        prompt_addition="...",
        keywords=["high"],
        risk_tier=1,
    )
    
    with patch.object(registry, "get_or_default", return_value=high_risk_skill):
        resp = core.process("test", session, active_skill="high_risk")
        assert not resp.success
        assert "Skill Blocked" in resp.error
        
def test_scoped_skill_enforcement():
    # Test 3: a scoped skill enforces scope identically to a scoped tool
    mock = MockBackend()
    core = GuardianCore(model=mock)
    session = Session()
    
    from guardian.skills import get_skill_registry
    registry = get_skill_registry()
    
    scoped_skill = Skill(
        name="scoped",
        title="Scoped",
        description="Scoped",
        prompt_addition="...",
        keywords=["scope"],
        requires_scope=True,
    )
    
    with patch.object(registry, "get_or_default", return_value=scoped_skill):
        # Without a valid scope file, this should be denied (Skill Blocked / Denied)
        resp = core.process("test", session, active_skill="scoped")
        assert not resp.success
        assert "Skill Blocked" in resp.error or "Skill Denied" in resp.error

def test_dynamic_loading(tmp_path):
    # Test 4: dropping a new skill file into the directory makes it available
    skills = load_skills_from_directory(tmp_path)
    assert len(skills) == 0
    
    (tmp_path / "new_skill.md").write_text("---\nname: new_skill\ntitle: New\ndescription: D\n---\nBody", encoding="utf-8")
    skills2 = load_skills_from_directory(tmp_path)
    assert len(skills2) == 1
    assert skills2[0].name == "new_skill"
