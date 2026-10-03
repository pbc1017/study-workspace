#!/usr/bin/env python3
"""Portable package checks, without adding runtime dependencies."""
import json
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parent.parent
portable = json.loads((root / "plugin.json").read_text())
claude = json.loads((root / ".claude-plugin/plugin.json").read_text())
assert portable["name"] == claude["name"] == "study-workspace"
assert portable["version"] == claude["version"] == "0.1.0"
for path in [
    root / ".claude-plugin/marketplace.json",
    root / ".agents/plugins/marketplace.json",
]:
    market = json.loads(path.read_text())
    assert market["plugins"][0]["name"] == portable["name"]
skills = list((root / "skills").glob("*/SKILL.md"))
assert len(skills) == 5
for skill in skills:
    content = skill.read_text()
    assert content.startswith("---\n")
    front = content.split("---", 2)[1]
    assert re.search(r"^name: " + re.escape(skill.parent.name) + r"$", front, re.M)
    assert re.search(r"^description: .+", front, re.M)
    for ref in re.findall(r"\]\(([^)]+)\)", content):
        if not ref.startswith("https://"):
            assert (
                (skill.parent / ref).resolve().is_file()
            ), f"Missing skill reference: {ref}"
    assert "TODO" not in content and "[INSERT" not in content
for example in (root / "examples").glob("*.json"):
    sys.path.insert(0, str(root))
    from study_workspace.store import Store

    # The validator does not open a data home or create a user's DB.
    Store.validate_pack(None, json.loads(example.read_text()))
print(
    f"Validated portable/Claude manifests, both marketplaces, {len(skills)} skills and 3 example packs"
)
