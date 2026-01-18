from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional


ROOT = Path(__file__).resolve().parents[1]
VAULT_DIR = ROOT / "tests" / "fixtures" / "test_vault"

CHINESE_TITLE = "\u7eaf\u4e2d\u6587\u7b14\u8bb0"
CHINESE_BODY = (
    "\u8fd9\u662f\u4e00\u4efd\u7eaf\u4e2d\u6587\u7684\u7b14\u8bb0\u5185\u5bb9\uff0c"
    "\u7528\u4e8e\u6d4b\u8bd5\u7f16\u7801\u4e0e\u8bcd\u6c47\u7279\u5f81\u3002"
)


@dataclass
class NoteDef:
    path: str
    title: str
    has_frontmatter: bool = False
    is_normal_rich: bool = False
    is_daily: bool = False
    related_heading_count: int = 0
    anchor_placement: str = "normal"  # normal|missing|too_far
    user_deleted_marker: bool = False
    hash_mismatch_marker: bool = False
    title_special_chars: bool = False
    is_chinese_only: bool = False
    has_code_block: bool = False
    is_large_file: bool = False
    is_empty_or_short: bool = False
    expected_conflict: Optional[str] = None

    def has_related_heading(self) -> bool:
        return self.related_heading_count > 0

    def has_anchor(self) -> bool:
        if self.related_heading_count <= 0:
            return False
        return self.anchor_placement in {"normal", "too_far"}


def _frontmatter(title: str) -> str:
    lines = [
        "---",
        f'title: "{title}"',
        "tags:",
        "  - project",
        "  - notes",
        "aliases:",
        f"  - {title} alias",
        "keywords:",
        "  - knowledge",
        "  - vault",
        "---",
        "",
    ]
    return "\n".join(lines)


def _rich_body() -> str:
    return "\n".join(
        [
            "This note contains a few paragraphs with structured content.",
            "",
            "- Key point one",
            "- Key point two",
            "- Key point three",
            "",
            "Another paragraph expands on the idea with more details.",
        ]
    )


def _code_block() -> str:
    return "\n".join(
        [
            "```python",
            "def add(a: int, b: int) -> int:",
            "    return a + b",
            "```",
        ]
    )


def _related_block(note: NoteDef) -> Iterable[str]:
    lines: list[str] = []
    for idx in range(note.related_heading_count):
        lines.append("## Related")
        if note.anchor_placement == "too_far" and idx == 0:
            lines.extend(
                [
                    "Line one after heading.",
                    "Line two after heading.",
                    "Line three after heading.",
                    "Line four after heading.",
                    "<!-- oka:related:v1 -->",
                ]
            )
        elif note.anchor_placement == "missing":
            lines.append("- [[MissingAnchorNote]]")
        else:
            lines.append("<!-- oka:related:v1 -->")
            if note.hash_mismatch_marker:
                lines.append("Manual edit: adjusted related list.")
            lines.append("- [[RelatedNote]]")
        if idx < note.related_heading_count - 1:
            lines.append("")
    return lines


def _build_content(note: NoteDef) -> str:
    if note.is_empty_or_short:
        return "" if note.title.endswith("01") else "x\n"

    lines: list[str] = []
    if note.has_frontmatter:
        lines.append(_frontmatter(note.title))
    lines.append(f"# {note.title}")
    lines.append("")

    if note.is_chinese_only:
        lines.append(CHINESE_BODY)
    else:
        lines.append(_rich_body() if note.is_normal_rich else "Short descriptive text.")

    if note.has_code_block:
        lines.append("")
        lines.append(_code_block())

    if note.user_deleted_marker:
        lines.append("")
        lines.append("<!-- oka:related:deleted -->")

    if note.related_heading_count > 0:
        lines.append("")
        lines.extend(_related_block(note))

    content = "\n".join(lines) + "\n"
    if note.is_large_file:
        filler = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
        target_size = 1_100_000
        while len(content.encode("utf-8")) < target_size:
            content += filler
    return content


def _note_defs() -> list[NoteDef]:
    notes: list[NoteDef] = []

    for day in range(1, 6):
        notes.append(
            NoteDef(
                path=f"Daily/2026-01-{day:02d}.md",
                title=f"Daily 2026-01-{day:02d}",
                is_daily=True,
            )
        )

    for idx in range(1, 11):
        notes.append(
            NoteDef(
                path=f"Notes/normal_{idx:02d}.md",
                title=f"Normal Note {idx:02d}",
                has_frontmatter=True,
                is_normal_rich=True,
                has_code_block=idx <= 3,
            )
        )

    for idx in range(1, 6):
        notes.append(
            NoteDef(
                path=f"Projects/project_{idx:02d}.md",
                title=f"Project Note {idx:02d}",
                has_frontmatter=True,
                has_code_block=idx <= 2,
            )
        )

    for idx in range(1, 6):
        notes.append(
            NoteDef(
                path=f"Archive/archive_{idx:02d}.md",
                title=f"Archive Note {idx:02d}",
                has_frontmatter=True,
                is_large_file=idx <= 2,
            )
        )

    for idx in range(1, 4):
        notes.append(
            NoteDef(
                path=f"Notes/edge_multi_related_{idx:02d}.md",
                title=f"Multi Related {idx:02d}",
                related_heading_count=2,
                expected_conflict="multiple_related_headings",
            )
        )

    for idx in range(1, 3):
        notes.append(
            NoteDef(
                path=f"Notes/edge_missing_anchor_{idx:02d}.md",
                title=f"Missing Anchor {idx:02d}",
                related_heading_count=1,
                anchor_placement="missing",
                expected_conflict="missing_anchor",
            )
        )

    for idx in range(1, 3):
        notes.append(
            NoteDef(
                path=f"Notes/edge_anchor_far_{idx:02d}.md",
                title=f"Anchor Too Far {idx:02d}",
                related_heading_count=1,
                anchor_placement="too_far",
                expected_conflict="anchor_too_far",
            )
        )

    for idx in range(1, 3):
        notes.append(
            NoteDef(
                path=f"Notes/edge_deleted_related_{idx:02d}.md",
                title=f"Deleted Related {idx:02d}",
                user_deleted_marker=True,
                expected_conflict="user_deleted_block",
            )
        )

    for idx in range(1, 3):
        notes.append(
            NoteDef(
                path=f"Notes/edge_hash_mismatch_{idx:02d}.md",
                title=f"Hash Mismatch {idx:02d}",
                related_heading_count=1,
                hash_mismatch_marker=True,
                expected_conflict="hash_mismatch",
            )
        )

    for idx in range(1, 3):
        notes.append(
            NoteDef(
                path=f"Notes/edge_empty_{idx:02d}.md",
                title=f"Empty Note {idx:02d}",
                is_empty_or_short=True,
            )
        )

    special_titles = [
        "Title with [brackets]",
        "Title with #hash",
        "Title with spaces #1",
        "Title with | pipe",
        "Title with [#] mix",
    ]
    for idx, title in enumerate(special_titles, start=1):
        notes.append(
            NoteDef(
                path=f"Notes/filler_special_{idx:02d}.md",
                title=title,
                title_special_chars=True,
            )
        )

    for idx in range(1, 4):
        notes.append(
            NoteDef(
                path=f"Notes/filler_cn_{idx:02d}.md",
                title=CHINESE_TITLE,
                is_chinese_only=True,
            )
        )

    for idx in range(1, 5):
        notes.append(
            NoteDef(
                path=f"Notes/filler_{idx:02d}.md",
                title=f"Filler Note {idx:02d}",
            )
        )

    return notes


def _write_manifest(entries: dict[str, dict[str, object]]) -> None:
    manifest_path = VAULT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def generate() -> None:
    VAULT_DIR.mkdir(parents=True, exist_ok=True)

    (VAULT_DIR / "Daily").mkdir(parents=True, exist_ok=True)
    (VAULT_DIR / "Notes").mkdir(parents=True, exist_ok=True)
    (VAULT_DIR / "Projects").mkdir(parents=True, exist_ok=True)
    (VAULT_DIR / "Archive").mkdir(parents=True, exist_ok=True)
    (VAULT_DIR / "Attachments").mkdir(parents=True, exist_ok=True)

    attachment_path = VAULT_DIR / "Attachments" / "sample.bin"
    attachment_path.write_bytes(b"fixture")

    notes = _note_defs()
    entries: dict[str, dict[str, object]] = {}

    for note in notes:
        target = VAULT_DIR / Path(note.path)
        content = _build_content(note)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")

        entries[note.path] = {
            "title": note.title,
            "has_frontmatter": note.has_frontmatter,
            "has_related_heading": note.has_related_heading(),
            "has_anchor": note.has_anchor(),
            "expected_conflict": note.expected_conflict,
            "title_special_chars": note.title_special_chars,
            "is_large_file": note.is_large_file,
            "is_daily": note.is_daily,
            "is_chinese_only": note.is_chinese_only,
            "has_code_block": note.has_code_block,
            "is_empty_or_short": note.is_empty_or_short,
            "is_normal_rich": note.is_normal_rich,
        }

    if len(entries) != 50:
        raise SystemExit(f"Expected 50 notes, got {len(entries)}")

    _write_manifest(entries)


if __name__ == "__main__":
    generate()
