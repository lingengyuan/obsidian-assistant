from __future__ import annotations

from pathlib import Path

from oka.core.pipeline import ParsedNote, ParseResult, _title_tokens, recommend_notes
from oka.core.scoring import ScoringConfig


def test_recommend_notes_respects_mem_limit() -> None:
    tokens = ["a"] * 70000
    base = Path(".").resolve()
    note = ParsedNote(
        path=base / "note.md",
        title="note",
        has_frontmatter=False,
        frontmatter={},
        links=[],
        content_tokens=tokens,
        title_tokens=_title_tokens("note"),
        link_set=set(),
        rel_path="note.md",
    )
    parse_result = ParseResult(notes=[note])
    config = ScoringConfig()

    result = recommend_notes(
        parse_result=parse_result,
        vault_path=base,
        config=config,
        max_workers=0,
        timeout_sec=0,
        max_mem_mb=1,
    )

    assert result.downgrades == ["recommend_skipped_mem_limit"]
