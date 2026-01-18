from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[0]
VAULT_DIR = ROOT / "fixtures" / "test_vault"
MANIFEST_PATH = VAULT_DIR / "manifest.json"

ANCHOR = "<!-- oka:related:v1 -->"
DELETED_MARKER = "<!-- oka:related:deleted -->"


def _load_manifest() -> dict[str, dict[str, object]]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    parts = text.split("\n", 1)
    if len(parts) < 2:
        return text
    remainder = parts[1]
    end_idx = remainder.find("\n---\n")
    if end_idx == -1:
        return text
    return remainder[end_idx + 5 :]


def _nonempty_lines_after_heading(lines: list[str], heading_idx: int) -> int:
    count = 0
    for line in lines[heading_idx + 1 :]:
        if line.strip() == "":
            continue
        if line.strip() == ANCHOR:
            return count
        count += 1
    return count


def test_manifest_distribution_and_patterns() -> None:
    assert MANIFEST_PATH.exists()
    manifest = _load_manifest()
    assert len(manifest) == 50

    md_files = sorted(VAULT_DIR.rglob("*.md"))
    assert len(md_files) == 50

    for rel_path, meta in manifest.items():
        path = VAULT_DIR / Path(rel_path)
        assert path.exists()

        content = path.read_text(encoding="utf-8")
        body = _strip_frontmatter(content)

        if meta.get("has_frontmatter"):
            assert content.startswith("---\n")
            assert "\n---\n" in content

        if meta.get("has_related_heading"):
            assert "## Related" in content

        if meta.get("has_anchor"):
            assert ANCHOR in content
        else:
            if meta.get("expected_conflict") in {
                "missing_anchor",
                "user_deleted_block",
            }:
                assert ANCHOR not in content

        if meta.get("title_special_chars"):
            title_line = next(
                (line for line in content.splitlines() if line.startswith("# ")), ""
            )
            assert any(ch in title_line for ch in ("[", "]", "#", "|"))

        if meta.get("is_chinese_only"):
            assert body.strip()
            assert re.search(r"[A-Za-z0-9]", body) is None

        if meta.get("has_code_block"):
            assert "```" in content

        if meta.get("is_large_file"):
            assert path.stat().st_size > 1_000_000

        if meta.get("is_empty_or_short"):
            assert len(content.strip()) <= 20

        expected_conflict = meta.get("expected_conflict")
        if expected_conflict == "multiple_related_headings":
            assert content.count("## Related") >= 2
        elif expected_conflict == "missing_anchor":
            assert "## Related" in content
            assert ANCHOR not in content
        elif expected_conflict == "anchor_too_far":
            lines = content.splitlines()
            heading_idx = lines.index("## Related")
            assert _nonempty_lines_after_heading(lines, heading_idx) > 3
            assert ANCHOR in content
        elif expected_conflict == "user_deleted_block":
            assert DELETED_MARKER in content
        elif expected_conflict == "hash_mismatch":
            assert ANCHOR in content
            assert "Manual edit" in content

    def count_flag(flag: str) -> int:
        return sum(1 for meta in manifest.values() if meta.get(flag))

    def count_conflict(value: str) -> int:
        return sum(
            1 for meta in manifest.values() if meta.get("expected_conflict") == value
        )

    assert count_flag("is_normal_rich") >= 10
    assert count_flag("is_daily") >= 5
    assert count_conflict("multiple_related_headings") >= 3
    assert count_conflict("missing_anchor") >= 2
    assert count_conflict("anchor_too_far") >= 2
    assert count_conflict("user_deleted_block") >= 2
    assert count_conflict("hash_mismatch") >= 2
    assert count_flag("title_special_chars") >= 5
    assert count_flag("is_chinese_only") >= 3
    assert count_flag("has_code_block") >= 5
    assert count_flag("is_large_file") >= 2
    assert count_flag("is_empty_or_short") >= 2
