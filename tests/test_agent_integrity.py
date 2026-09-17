import json
from pathlib import Path

def test_agent_deer_model_documentation_sync():
    """
    Ensure the models documented in agent-deer/SKILL.md accurately
    reflect the active models defined in data/subagent_fleet.json (Single Source of Truth).
    """
    config_path = Path("data/subagent_fleet.json")
    skill_path = Path(".agents/skills/agent-deer/SKILL.md")
    
    assert config_path.exists(), "Fleet config missing"
    assert skill_path.exists(), "Agent Deer SKILL.md missing"
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
        
    with open(skill_path, "r", encoding="utf-8") as f:
        skill_content = f.read()
        
    primary = config["deer"]["primary_model"]
    lightweight = config["deer"]["lightweight_model"]
    
    assert primary in skill_content, f"Primary model '{primary}' not documented in SKILL.md"
    assert lightweight in skill_content, f"Lightweight model '{lightweight}' not documented in SKILL.md"
    
    # Anti-regression: ensure legacy models are strictly dead
    assert "llama3:latest" not in skill_content, "Found deprecated llama3:latest in SKILL.md"
    assert "llama3.2:latest" not in skill_content, "Found deprecated llama3.2:latest in SKILL.md"
