from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple
from uuid import uuid4

from oka.core.scoring import (
    ScoringConfig,
    build_reason,
    compute_confidence,
    quantile_normalize,
)

LINK_PATTERN = re.compile(r"\[\[([^\[\]]+)\]\]")
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]{3,}")


@dataclass
class ScanResult:
    md_files: List[Path]
    skipped: Dict[str, int]


@dataclass
class ParsedNote:
    path: Path
    title: str
    has_frontmatter: bool
    frontmatter: Dict[str, List[str]]
    links: List[str]
    content_tokens: List[str]
    title_tokens: Set[str]
    link_set: Set[str]
    rel_path: str


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
class RecommendationResult:
    related_blocks: List[Dict[str, object]]
    metadata_suggestions: List[Dict[str, object]]
    merge_previews: List[Dict[str, object]]
    low_confidence_count: int


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


def _split_frontmatter(content: str) -> Tuple[bool, str, str]:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return False, "", content
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            frontmatter_block = "\n".join(lines[1:idx])
            remainder = "\n".join(lines[idx + 1 :])
            return True, frontmatter_block, remainder
    return False, "", content


def _clean_frontmatter_value(value: str) -> str:
    value = value.strip().strip('"').strip("'")
    return value


def _parse_frontmatter(block: str) -> Dict[str, List[str]]:
    fields = {"keywords": [], "aliases": [], "related": []}
    current_key: Optional[str] = None
    for line in block.splitlines():
        raw = line.rstrip()
        if not raw.strip():
            continue
        if ":" in raw and not raw.lstrip().startswith("-"):
            key, value = raw.split(":", 1)
            key = key.strip()
            current_key = key if key in fields else None
            if not current_key:
                continue
            value = value.strip()
            if not value:
                continue
            if value.startswith("[") and value.endswith("]"):
                items = [v.strip() for v in value[1:-1].split(",")]
                fields[current_key].extend(
                    _clean_frontmatter_value(item) for item in items if item
                )
            else:
                fields[current_key].append(_clean_frontmatter_value(value))
            continue
        if current_key and raw.lstrip().startswith("-"):
            item = raw.lstrip()[1:].strip()
            if item:
                fields[current_key].append(_clean_frontmatter_value(item))

    normalized = {}
    for key, values in fields.items():
        deduped = list(dict.fromkeys(v for v in values if v))
        if deduped:
            normalized[key] = deduped
    return normalized


def _tokenize(text: str) -> List[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]


def _title_tokens(title: str) -> Set[str]:
    tokens = [token.lower() for token in re.split(r"[\s\-_]+", title) if token]
    return set(tokens)


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


def parse_notes(md_files: Iterable[Path], vault_path: Path) -> ParseResult:
    notes: List[ParsedNote] = []
    for path in md_files:
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="utf-8", errors="replace")
        except PermissionError:
            continue
        has_frontmatter, frontmatter_block, body = _split_frontmatter(content)
        frontmatter = _parse_frontmatter(frontmatter_block) if has_frontmatter else {}
        links = _extract_links(body)
        content_tokens = _tokenize(body)
        rel_path = str(path)
        try:
            rel_path = path.relative_to(vault_path).as_posix()
        except ValueError:
            rel_path = str(path)
        notes.append(
            ParsedNote(
                path=path,
                title=path.stem,
                has_frontmatter=has_frontmatter,
                frontmatter=frontmatter,
                links=links,
                content_tokens=content_tokens,
                title_tokens=_title_tokens(path.stem),
                link_set=set(links),
                rel_path=rel_path,
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


def _jaccard(left: Set[str], right: Set[str]) -> float:
    if not left and not right:
        return 0.0
    intersection = left.intersection(right)
    union = left.union(right)
    if not union:
        return 0.0
    return len(intersection) / len(union)


def _path_filter(
    note: ParsedNote, other: ParsedNote, vault_path: Path, config: ScoringConfig
) -> List[Tuple[str, float]]:
    try:
        left_parts = note.path.relative_to(vault_path).parts
        right_parts = other.path.relative_to(vault_path).parts
    except ValueError:
        return []
    if not left_parts or not right_parts:
        return []
    if left_parts[0] != right_parts[0]:
        return [("path_penalty", config.path_penalty)]
    return []


def _derive_keywords(tokens: List[str], limit: int = 3) -> List[str]:
    counts: Dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [token for token, _ in ordered[:limit]]


def _derive_aliases(title: str) -> List[str]:
    if "-" in title or "_" in title:
        alias = title.replace("-", " ").replace("_", " ").strip()
        if alias and alias != title:
            return [alias]
    return []


def _build_related_block(
    note: ParsedNote, suggestions: List[Dict[str, object]]
) -> Dict[str, object]:
    anchor = "oka_related_v1"
    lines = ["## Related", f"<!-- {anchor} -->"]
    for suggestion in suggestions:
        title = suggestion["title"]
        confidence = suggestion["confidence"]
        lines.append(f"- [[{title}]] ({confidence:.2f})")
    return {
        "note": note,
        "anchor": anchor,
        "markdown_block": "\n".join(lines) + "\n",
        "suggestions": suggestions,
    }


def recommend_notes(
    parse_result: ParseResult,
    vault_path: Path,
    config: ScoringConfig,
) -> RecommendationResult:
    notes = parse_result.notes
    pair_stats: List[Dict[str, object]] = []
    raw_content_values: List[float] = []

    for i in range(len(notes)):
        for j in range(i + 1, len(notes)):
            left = notes[i]
            right = notes[j]
            content_sim = _jaccard(set(left.content_tokens), set(right.content_tokens))
            title_sim = _jaccard(left.title_tokens, right.title_tokens)
            link_overlap = _jaccard(left.link_set, right.link_set)
            pair_stats.append(
                {
                    "left": i,
                    "right": j,
                    "content_sim_raw": content_sim,
                    "title_sim": title_sim,
                    "link_overlap": link_overlap,
                }
            )
            raw_content_values.append(content_sim)

    if config.norm_method == "quantile":
        normalized_content = quantile_normalize(raw_content_values)
    else:
        normalized_content = list(raw_content_values)
    for idx, pair in enumerate(pair_stats):
        pair["content_sim"] = normalized_content[idx] if normalized_content else 0.0

    related_map: Dict[int, List[Dict[str, object]]] = {
        idx: [] for idx in range(len(notes))
    }
    merge_candidates: List[Dict[str, object]] = []

    for pair in pair_stats:
        left = notes[pair["left"]]
        right = notes[pair["right"]]
        filters = _path_filter(left, right, vault_path, config)
        confidence, filter_entries = compute_confidence(
            pair["content_sim"],
            pair["title_sim"],
            pair["link_overlap"],
            filters,
            config,
        )
        reason = build_reason(
            pair["content_sim"],
            pair["title_sim"],
            pair["link_overlap"],
            filter_entries,
            config,
            raw_content_sim=pair["content_sim_raw"],
        )
        if confidence >= config.min_related_confidence:
            related_map[pair["left"]].append(
                {
                    "title": right.title,
                    "target_path": right.rel_path,
                    "confidence": confidence,
                    "reason": reason,
                }
            )
            related_map[pair["right"]].append(
                {
                    "title": left.title,
                    "target_path": left.rel_path,
                    "confidence": confidence,
                    "reason": reason,
                }
            )
        if confidence >= config.merge_confidence:
            merge_candidates.append(
                {
                    "left": pair["left"],
                    "right": pair["right"],
                    "confidence": confidence,
                }
            )

    related_blocks: List[Dict[str, object]] = []
    metadata_suggestions: List[Dict[str, object]] = []
    low_confidence_count = 0

    for idx, note in enumerate(notes):
        suggestions = sorted(
            related_map[idx], key=lambda item: item["confidence"], reverse=True
        )[:3]
        if suggestions:
            related_blocks.append(_build_related_block(note, suggestions))

        keywords = _derive_keywords(note.content_tokens)
        aliases = _derive_aliases(note.title)
        related = [item["title"] for item in suggestions]

        fields: Dict[str, List[str]] = {}
        existing = note.frontmatter
        if "keywords" not in existing and keywords:
            fields["keywords"] = keywords
        if "aliases" not in existing and aliases:
            fields["aliases"] = aliases
        if "related" not in existing and related:
            fields["related"] = related

        if fields:
            if suggestions:
                top_reason = suggestions[0]["reason"]
                confidence = suggestions[0]["confidence"]
            else:
                top_reason = build_reason(0.0, 0.0, 0.0, [], config)
                confidence = 0.25
            if confidence < config.low_confidence:
                low_confidence_count += 1
            metadata_suggestions.append(
                {
                    "note": note,
                    "fields": fields,
                    "confidence": confidence,
                    "reason": top_reason,
                }
            )

        for item in suggestions:
            if item["confidence"] < config.low_confidence:
                low_confidence_count += 1

    merge_previews = _cluster_merge_candidates(merge_candidates, notes)

    return RecommendationResult(
        related_blocks=related_blocks,
        metadata_suggestions=metadata_suggestions,
        merge_previews=merge_previews,
        low_confidence_count=low_confidence_count,
    )


def _cluster_merge_candidates(
    candidates: List[Dict[str, object]],
    notes: List[ParsedNote],
) -> List[Dict[str, object]]:
    if not candidates:
        return []

    parent = list(range(len(notes)))

    def find(idx: int) -> int:
        while parent[idx] != idx:
            parent[idx] = parent[parent[idx]]
            idx = parent[idx]
        return idx

    def union(left: int, right: int) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for candidate in candidates:
        union(candidate["left"], candidate["right"])

    clusters: Dict[int, List[int]] = {}
    scores: Dict[int, List[float]] = {}
    for candidate in candidates:
        root = find(candidate["left"])
        clusters.setdefault(root, [])
        scores.setdefault(root, [])
        for idx in (candidate["left"], candidate["right"]):
            if idx not in clusters[root]:
                clusters[root].append(idx)
        scores[root].append(candidate["confidence"])

    previews: List[Dict[str, object]] = []
    for root, cluster_indices in clusters.items():
        if len(cluster_indices) < 2:
            continue
        average_confidence = sum(scores[root]) / len(scores[root])
        previews.append(
            {
                "candidates": [notes[idx].rel_path for idx in cluster_indices],
                "average_confidence": round(average_confidence, 3),
            }
        )
    return previews


def build_plan(
    analysis: AnalysisResult,
    recommendations: RecommendationResult,
    config: ScoringConfig,
) -> PlanResult:
    items: List[Dict[str, object]] = []
    for idx, target in enumerate(sorted(analysis.broken_links)[:5], start=1):
        target_path = target
        if not target_path.lower().endswith(".md"):
            target_path = f"{target_path}.md"
        reason = build_reason(0.0, 0.0, 0.0, [], config)
        reason["kind"] = "broken_link_candidate"
        reason["details"] = f"Link target '{target}' not found in vault."
        items.append(
            {
                "id": f"act_{idx:04d}",
                "type": "create_stub_note",
                "risk_class": "A",
                "target_path": target_path,
                "confidence": 0.2,
                "reason": reason,
                "payload": {"title": target},
                "dependencies": [],
            }
        )

    next_id = len(items) + 1
    for block in recommendations.related_blocks:
        note = block["note"]
        suggestions = block["suggestions"]
        if not suggestions:
            continue
        items.append(
            {
                "id": f"act_{next_id:04d}",
                "type": "append_related_links_section",
                "risk_class": "A",
                "target_path": note.rel_path,
                "confidence": suggestions[0]["confidence"],
                "reason": suggestions[0]["reason"],
                "payload": {
                    "anchor": block["anchor"],
                    "markdown_block": block["markdown_block"],
                    "items": [
                        {
                            "title": item["title"],
                            "confidence": item["confidence"],
                            "target_path": item["target_path"],
                        }
                        for item in suggestions
                    ],
                },
                "dependencies": [],
            }
        )
        next_id += 1

    for suggestion in recommendations.metadata_suggestions:
        note = suggestion["note"]
        items.append(
            {
                "id": f"act_{next_id:04d}",
                "type": "add_frontmatter_fields",
                "risk_class": "read-only",
                "target_path": note.rel_path,
                "confidence": suggestion["confidence"],
                "reason": suggestion["reason"],
                "payload": {"fields": suggestion["fields"]},
                "dependencies": [],
            }
        )
        next_id += 1

    for preview in recommendations.merge_previews:
        items.append(
            {
                "id": f"act_{next_id:04d}",
                "type": "merge_preview",
                "risk_class": "read-only",
                "target_path": "merge-preview",
                "confidence": preview["average_confidence"],
                "reason": build_reason(0.0, 0.0, 0.0, [], config),
                "payload": preview,
                "dependencies": [],
            }
        )
        next_id += 1
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


def build_report(
    analysis: AnalysisResult,
    vault_path: Path,
    recommendations: RecommendationResult,
    plan: PlanResult,
    config: ScoringConfig,
) -> str:
    low_confidence = recommendations.low_confidence_count
    action_items_total = len(plan.items)
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
        f"- Action items: {action_items_total}",
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
        f"| Action items | {action_items_total} |",
        "",
        "## Next steps",
        "",
        "- Review orphan notes and connect them to existing topics.",
        "- Investigate broken link candidates and fix or create targets.",
    ]
    if recommendations.merge_previews:
        lines.extend(
            [
                "",
                "## Merge preview (read-only)",
                "",
            ]
        )
        for preview in recommendations.merge_previews:
            candidates = ", ".join(preview["candidates"])
            lines.append(
                f"- {candidates} (avg confidence {preview['average_confidence']})"
            )

    if low_confidence > 0:
        lines.extend(
            [
                "",
                "## Tuning tips",
                "",
                f"- {low_confidence} suggestions are below confidence {config.low_confidence:.2f}.",
                "- Adjust `scoring.w_content`, `scoring.w_title`, and `scoring.w_link` in oka.toml.",
                "- Increase `filters.path_penalty` or switch `profile` to conservative to reduce noise.",
            ]
        )
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
    parse_result = parse_notes(scan_result.md_files, vault_path)
    timings["parse_ms"] = int((time.perf_counter() - parse_start) * 1000)

    analyze_start = time.perf_counter()
    analysis = analyze_notes(parse_result)
    timings["analyze_ms"] = int((time.perf_counter() - analyze_start) * 1000)

    scoring_config = ScoringConfig()
    recommend_start = time.perf_counter()
    recommendations = recommend_notes(parse_result, vault_path, scoring_config)
    timings["recommend_ms"] = int((time.perf_counter() - recommend_start) * 1000)

    plan_start = time.perf_counter()
    plan = build_plan(analysis, recommendations, scoring_config)
    timings["plan_ms"] = int((time.perf_counter() - plan_start) * 1000)

    report_start = time.perf_counter()
    report_markdown = build_report(
        analysis,
        vault_path,
        recommendations,
        plan,
        scoring_config,
    )
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
