"""Automated verification of the strict ZERO-EMOJI rule across all documentation."""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent

# Regex matching emoji character ranges (Emoticons, Misc Symbols, Transport, Dingbats, Supplemental)
EMOJI_PATTERN = re.compile(
    r"["
    r"\U0001F600-\U0001F64F"  # emoticons
    r"\U0001F300-\U0001F5FF"  # symbols & pictographs
    r"\U0001F680-\U0001F6FF"  # transport & map
    r"\U0001F1E0-\U0001F1FF"  # flags
    r"\U0001F900-\U0001F9FF"  # supplemental symbols
    r"\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-a
    r"\u2600-\u26FF"          # misc symbols (including ⚡, ❌, etc.)
    r"\u2700-\u27BF"          # dingbats (including ✅)
    r"]",
    flags=re.UNICODE,
)


def get_all_markdown_files():
    """Find all markdown documentation files in the repository."""
    md_files = list(REPO_ROOT.glob("*.md")) + list((REPO_ROOT / "docs").glob("*.md"))
    # Exclude internal prompt/playbook if present
    return [f for f in md_files if f.name != "ENGINEERING_PLAYBOOK_PROMPT.md"]


@pytest.mark.parametrize("md_path", get_all_markdown_files(), ids=lambda p: p.name)
def test_markdown_file_has_zero_emojis(md_path: Path):
    """Enforce non-negotiable zero emoji standard in documentation."""
    content = md_path.read_text(encoding="utf-8")
    matches = EMOJI_PATTERN.findall(content)
    assert len(matches) == 0, (
        f"Strict Zero-Emoji Rule Violated in '{md_path.name}': "
        f"Found forbidden emojis: {matches}"
    )
