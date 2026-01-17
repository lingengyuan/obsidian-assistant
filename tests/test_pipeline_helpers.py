from __future__ import annotations

from pathlib import Path

from oka.core.pipeline import (
    ParsedNote,
    ParseResult,
    _extract_links,
    _parse_frontmatter,
    _split_frontmatter,
    _title_tokens,
    recommend_notes,
    scan_vault,
)
from oka.core.scoring import ScoringConfig


def test_split_and_parse_frontmatter() -> None:
    content = "---\nkeywords: [alpha, beta]\nrelated:\n  - gamma\n---\nBody\n"
    has_fm, block, body = _split_frontmatter(content)
    assert has_fm is True
    assert "keywords" in block
    assert "Body" in body

    parsed = _parse_frontmatter(block)
    assert parsed["keywords"] == ["alpha", "beta"]
    assert parsed["related"] == ["gamma"]


def test_extract_links() -> None:
    content = "Links: [[note]] [[note|alias]] [[note#section]] [[note.md]]"
    links = _extract_links(content)
    assert links == ["note", "note", "note", "note"]


def test_scan_vault_skips_non_md_and_large(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("ok", encoding="utf-8")
    (vault / "large.md").write_text("x" * (1024 * 1024 + 1), encoding="utf-8")
    (vault / "note.txt").write_text("skip", encoding="utf-8")
    obsidian = vault / ".obsidian"
    obsidian.mkdir()
    (obsidian / "config.json").write_text("{}", encoding="utf-8")

    result = scan_vault(vault, max_file_mb=1)
    assert len(result.md_files) == 1
    assert result.skipped["non_md"] == 1
    assert result.skipped["too_large"] == 1


def test_recommend_notes_parallel() -> None:
    base = Path(".").resolve()
    note_a = ParsedNote(
        path=base / "a" / "alpha.md",
        title="alpha",
        has_frontmatter=False,
        frontmatter={},
        links=["beta"],
        content_tokens=["alpha", "beta", "gamma"],
        title_tokens=_title_tokens("alpha"),
        link_set={"beta"},
        rel_path="a/alpha.md",
    )
    note_b = ParsedNote(
        path=base / "b" / "beta-note.md",
        title="beta-note",
        has_frontmatter=False,
        frontmatter={},
        links=["alpha"],
        content_tokens=["alpha", "beta", "delta"],
        title_tokens=_title_tokens("beta-note"),
        link_set={"alpha"},
        rel_path="b/beta-note.md",
    )
    note_c = ParsedNote(
        path=base / "a" / "gamma.md",
        title="gamma",
        has_frontmatter=False,
        frontmatter={},
        links=["alpha"],
        content_tokens=["alpha", "gamma", "delta"],
        title_tokens=_title_tokens("gamma"),
        link_set={"alpha"},
        rel_path="a/gamma.md",
    )

    parse_result = ParseResult(notes=[note_a, note_b, note_c])
    config = ScoringConfig(min_related_confidence=0.0, merge_confidence=0.0)

    result = recommend_notes(
        parse_result=parse_result,
        vault_path=base,
        config=config,
        max_workers=2,
        timeout_sec=0,
        max_mem_mb=0,
    )

    assert result.related_blocks
    assert result.metadata_suggestions
    assert result.merge_previews
