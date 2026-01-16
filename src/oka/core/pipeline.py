from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Set
from uuid import uuid4

LINK_PATTERN = re.compile(r"\[\[([^\[\]]+)\]\]")


@dataclass
class ScanResult:
    md_files: List[Path]
    skipped: Dict[str, int]


@dataclass
class ParsedNote:
    path: Path
    title: str
    has_frontmatter: bool
    links: List[str]


@dataclass
class ParseResult:
    notes: List[ParsedNote]


@dataclass
class AnalysisResult:
    total_notes: int
    frontmatter_notes: int
    total_links: int
    broken_links: Set[str]
    orphan_notes: List[ParsedNote]


@dataclass
class PlanResult:
    items: List[Dict[str, object]]


@dataclass
class PipelineOutput:
    health: Dict[str, object]
    action_items: Dict[str, object]
    run_summary: Dict[str, object]
    report_markdown: str


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _run_id() -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{uuid4().hex[:6]}"


def scan_vault(vault_path: Path, max_file_mb: int = 5) -> ScanResult:
    skipped = {"non_md": 0, "too_large": 0, "no_permission": 0}
    md_files: List[Path] = []
    max_bytes = max_file_mb * 1024 * 1024

    for root, dirs, files in os.walk(vault_path):
        if ".obsidian" in dirs:
            dirs[:] = [d for d in dirs if d != ".obsidian"]
        root_path = Path(root)
        for name in files:
            path = root_path / name
            try:
                size = path.stat().st_size
            except PermissionError:
                skipped["no_permission"] += 1
                continue
            if not name.lower().endswith(".md"):
                skipped["non_md"] += 1
                continue
            if size > max_bytes:
                skipped["too_large"] += 1
                continue
            md_files.append(path)

    return ScanResult(md_files=md_files, skipped=skipped)


def _split_frontmatter(content: str) -> tuple[bool, str]:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return False, content
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            remainder = "\n".join(lines[idx + 1 :])
            return True, remainder
    return False, content


def _extract_links(content: str) -> List[str]:
    links: List[str] = []
    for match in LINK_PATTERN.finditer(content):
        raw = match.group(1).strip()
        if not raw:
            continue
        target = raw.split("|", 1)[0].split("#", 1)[0].strip()
        if not target:
            continue
        if target.lower().endswith(".md"):
            target = target[:-3]
        links.append(target)
    return links


def parse_notes(md_files: Iterable[Path]) -> ParseResult:
    notes: List[ParsedNote] = []
    for path in md_files:
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="utf-8", errors="replace")
        except PermissionError:
            continue
        has_frontmatter, body = _split_frontmatter(content)
        links = _extract_links(body)
        notes.append(
            ParsedNote(
                path=path,
                title=path.stem,
                has_frontmatter=has_frontmatter,
                links=links,
            )
        )
    return ParseResult(notes=notes)


def analyze_notes(parse_result: ParseResult) -> AnalysisResult:
    note_titles = {note.title for note in parse_result.notes}
    incoming: Dict[str, int] = {title: 0 for title in note_titles}
    broken_links: Set[str] = set()
    total_links = 0

    for note in parse_result.notes:
        for target in note.links:
            total_links += 1
            if target in incoming:
                incoming[target] += 1
            else:
                broken_links.add(target)

    orphan_notes = [
        note
        for note in parse_result.notes
        if not note.links and incoming.get(note.title, 0) == 0
    ]

    frontmatter_notes = sum(1 for note in parse_result.notes if note.has_frontmatter)

    return AnalysisResult(
        total_notes=len(parse_result.notes),
        frontmatter_notes=frontmatter_notes,
        total_links=total_links,
        broken_links=broken_links,
        orphan_notes=orphan_notes,
    )


def recommend_notes() -> List[Dict[str, object]]:
    return []


def build_plan(analysis: AnalysisResult) -> PlanResult:
    items: List[Dict[str, object]] = []
    for idx, target in enumerate(sorted(analysis.broken_links)[:5], start=1):
        target_path = target
        if not target_path.lower().endswith(".md"):
            target_path = f"{target_path}.md"
        items.append(
            {
                "id": f"act_{idx:04d}",
                "type": "create_stub_note",
                "risk_class": "A",
                "target_path": target_path,
                "confidence": 0.2,
                "reason": {
                    "kind": "broken_link_candidate",
                    "details": f"Link target '{target}' not found in vault.",
                    "filters": [],
                },
                "payload": {"title": target},
                "dependencies": [],
            }
        )
    return PlanResult(items=items)


def build_health(analysis: AnalysisResult, vault_path: Path) -> Dict[str, object]:
    return {
        "version": "1",
        "vault": str(vault_path),
        "generated_at": _now_iso(),
        "stats": {
            "total_notes": analysis.total_notes,
            "frontmatter_notes": analysis.frontmatter_notes,
            "total_links": analysis.total_links,
            "broken_link_candidates": len(analysis.broken_links),
            "orphan_notes": len(analysis.orphan_notes),
        },
    }


def build_action_items(plan: PlanResult, vault_path: Path, profile: str) -> Dict[str, object]:
    return {
        "version": "1",
        "vault": str(vault_path),
        "generated_at": _now_iso(),
        "profile": profile,
        "items": plan.items,
    }


def build_report(analysis: AnalysisResult, vault_path: Path) -> str:
    lines = [
        "# Obsidian Assistant Report",
        "",
        f"Generated at: {_now_iso()}",
        f"Vault: {vault_path}",
        "",
        "## Summary",
        "",
        f"- Total notes: {analysis.total_notes}",
        f"- Notes with frontmatter: {analysis.frontmatter_notes}",
        f"- Total links: {analysis.total_links}",
        f"- Broken link candidates: {len(analysis.broken_links)}",
        f"- Orphan notes: {len(analysis.orphan_notes)}",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Total notes | {analysis.total_notes} |",
        f"| Notes with frontmatter | {analysis.frontmatter_notes} |",
        f"| Total links | {analysis.total_links} |",
        f"| Broken link candidates | {len(analysis.broken_links)} |",
        f"| Orphan notes | {len(analysis.orphan_notes)} |",
        "",
        "## Next steps",
        "",
        "- Review orphan notes and connect them to existing topics.",
        "- Investigate broken link candidates and fix or create targets.",
    ]
    return "\n".join(lines)


def build_run_summary(
    run_id: str,
    timing_ms: Dict[str, int],
    scan_result: ScanResult,
    cache_present: bool,
) -> Dict[str, object]:
    total_ms = timing_ms.get("total_ms", 0)
    stages = {
        "scan_ms": timing_ms.get("scan_ms", 0),
        "parse_ms": timing_ms.get("parse_ms", 0),
        "analyze_ms": timing_ms.get("analyze_ms", 0),
        "recommend_ms": timing_ms.get("recommend_ms", 0),
        "plan_ms": timing_ms.get("plan_ms", 0),
        "report_ms": timing_ms.get("report_ms", 0),
    }
    return {
        "version": "1",
        "run_id": run_id,
        "timing": {"total_ms": total_ms, "stages": stages},
        "io": {
            "scanned_files": len(scan_result.md_files),
            "skipped": scan_result.skipped,
        },
        "cache": {
            "present": cache_present,
            "hit_rate": 0.0,
            "incremental_updated": 0,
        },
        "downgrades": [],
    }


def write_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_pipeline(
    vault_path: Path,
    base_dir: Path,
    profile: str,
    max_file_mb: int = 5,
) -> PipelineOutput:
    run_id = _run_id()
    timings: Dict[str, int] = {}

    start = time.perf_counter()
    scan_start = time.perf_counter()
    scan_result = scan_vault(vault_path, max_file_mb=max_file_mb)
    timings["scan_ms"] = int((time.perf_counter() - scan_start) * 1000)

    parse_start = time.perf_counter()
    parse_result = parse_notes(scan_result.md_files)
    timings["parse_ms"] = int((time.perf_counter() - parse_start) * 1000)

    analyze_start = time.perf_counter()
    analysis = analyze_notes(parse_result)
    timings["analyze_ms"] = int((time.perf_counter() - analyze_start) * 1000)

    recommend_start = time.perf_counter()
    _ = recommend_notes()
    timings["recommend_ms"] = int((time.perf_counter() - recommend_start) * 1000)

    plan_start = time.perf_counter()
    plan = build_plan(analysis)
    timings["plan_ms"] = int((time.perf_counter() - plan_start) * 1000)

    report_start = time.perf_counter()
    report_markdown = build_report(analysis, vault_path)
    timings["report_ms"] = int((time.perf_counter() - report_start) * 1000)

    timings["total_ms"] = int((time.perf_counter() - start) * 1000)

    health = build_health(analysis, vault_path)
    action_items = build_action_items(plan, vault_path, profile)
    cache_present = (base_dir / "cache" / "index.sqlite").exists()
    run_summary = build_run_summary(run_id, timings, scan_result, cache_present)

    return PipelineOutput(
        health=health,
        action_items=action_items,
        run_summary=run_summary,
        report_markdown=report_markdown,
    )
