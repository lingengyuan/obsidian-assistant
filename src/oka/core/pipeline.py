from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple
from uuid import uuid4

from oka.core.config import get_float, get_int, get_str, load_config
from oka.core.index import CacheRecord, IndexStore, decode_json, encode_json
from oka.core.i18n import t
from oka.core.scoring import (
    ScoringConfig,
    build_reason,
    compute_confidence,
    quantile_normalize,
)

LINK_PATTERN = re.compile(r"\[\[([^\[\]]+)\]\]")
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]{3,}")
DEFAULT_TOP_TERMS = 30
DEFAULT_FAST_PATH_AGE_SEC = 10


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
    downgrades: List[str]


@dataclass
class IncrementalStats:
    total: int
    unchanged: int
    updated: int
    removed: int


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


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def scan_vault(
    vault_path: Path,
    max_file_mb: int = 5,
    max_files_per_sec: int = 0,
    sleep_ms: int = 0,
) -> ScanResult:
    skipped = {"non_md": 0, "too_large": 0, "no_permission": 0}
    md_files: List[Path] = []
    max_bytes = max_file_mb * 1024 * 1024
    scan_start = time.monotonic()
    processed = 0

    for root, dirs, files in os.walk(vault_path):
        if ".obsidian" in dirs:
            dirs[:] = [d for d in dirs if d != ".obsidian"]
        root_path = Path(root)
        for name in files:
            processed += 1
            path = root_path / name
            try:
                size = path.stat().st_size
            except PermissionError:
                skipped["no_permission"] += 1
                if sleep_ms > 0:
                    time.sleep(sleep_ms / 1000)
                elif max_files_per_sec > 0:
                    expected = processed / max_files_per_sec
                    elapsed = time.monotonic() - scan_start
                    if elapsed < expected:
                        time.sleep(expected - elapsed)
                continue
            if not name.lower().endswith(".md"):
                skipped["non_md"] += 1
                if sleep_ms > 0:
                    time.sleep(sleep_ms / 1000)
                elif max_files_per_sec > 0:
                    expected = processed / max_files_per_sec
                    elapsed = time.monotonic() - scan_start
                    if elapsed < expected:
                        time.sleep(expected - elapsed)
                continue
            if size > max_bytes:
                skipped["too_large"] += 1
                if sleep_ms > 0:
                    time.sleep(sleep_ms / 1000)
                elif max_files_per_sec > 0:
                    expected = processed / max_files_per_sec
                    elapsed = time.monotonic() - scan_start
                    if elapsed < expected:
                        time.sleep(expected - elapsed)
                continue
            md_files.append(path)
            if sleep_ms > 0:
                time.sleep(sleep_ms / 1000)
            elif max_files_per_sec > 0:
                expected = processed / max_files_per_sec
                elapsed = time.monotonic() - scan_start
                if elapsed < expected:
                    time.sleep(expected - elapsed)

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


def _top_terms(tokens: List[str], limit: int) -> List[str]:
    counts: Dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [token for token, _ in ordered[:limit]]


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


def _decode_cached_list(value: Optional[str]) -> List[str]:
    decoded = decode_json(value, [])
    return decoded if isinstance(decoded, list) else []


def _decode_cached_dict(value: Optional[str]) -> Dict[str, List[str]]:
    decoded = decode_json(value, {})
    return decoded if isinstance(decoded, dict) else {}


def _parse_note_file(
    path: Path,
    vault_path: Path,
    top_terms_limit: int,
) -> Tuple[ParsedNote, CacheRecord]:
    data = path.read_bytes()
    sha256 = _sha256_bytes(data)
    content = data.decode("utf-8", errors="replace")

    has_frontmatter, frontmatter_block, body = _split_frontmatter(content)
    frontmatter = _parse_frontmatter(frontmatter_block) if has_frontmatter else {}
    links = _extract_links(body)
    tokens = _tokenize(body)
    top_terms = _top_terms(tokens, top_terms_limit)

    rel_path = str(path)
    try:
        rel_path = path.relative_to(vault_path).as_posix()
    except ValueError:
        rel_path = str(path)

    note = ParsedNote(
        path=path,
        title=path.stem,
        has_frontmatter=has_frontmatter,
        frontmatter=frontmatter,
        links=links,
        content_tokens=top_terms,
        title_tokens=_title_tokens(path.stem),
        link_set=set(links),
        rel_path=rel_path,
    )

    stat = path.stat()
    record = CacheRecord(
        path=rel_path,
        mtime=stat.st_mtime,
        size=stat.st_size,
        sha256=sha256,
        frontmatter=encode_json(frontmatter),
        frontmatter_keys=encode_json(list(frontmatter.keys())),
        links=encode_json(links),
        top_terms=encode_json(top_terms),
    )
    return note, record


def _note_from_cache(
    path: Path,
    rel_path: str,
    record: Dict[str, object],
) -> ParsedNote:
    links = _decode_cached_list(record.get("links"))
    frontmatter = _decode_cached_dict(record.get("frontmatter"))
    frontmatter_keys = _decode_cached_list(record.get("frontmatter_keys"))
    top_terms = _decode_cached_list(record.get("top_terms"))
    return ParsedNote(
        path=path,
        title=path.stem,
        has_frontmatter=bool(frontmatter_keys),
        frontmatter=frontmatter,
        links=links,
        content_tokens=top_terms,
        title_tokens=_title_tokens(path.stem),
        link_set=set(links),
        rel_path=rel_path,
    )


def _load_notes_with_cache(
    md_files: Iterable[Path],
    vault_path: Path,
    index: IndexStore,
    top_terms_limit: int,
) -> Tuple[ParseResult, IncrementalStats]:
    notes: List[ParsedNote] = []
    unchanged = 0
    updated = 0
    paths: List[str] = []

    for path in md_files:
        rel_path = str(path)
        try:
            rel_path = path.relative_to(vault_path).as_posix()
        except ValueError:
            rel_path = str(path)
        paths.append(rel_path)

        stat = path.stat()
        cached = index.get(rel_path)
        if (
            cached
            and cached.get("mtime") == stat.st_mtime
            and cached.get("size") == stat.st_size
        ):
            notes.append(_note_from_cache(path, rel_path, cached))
            unchanged += 1
            continue

        note, record = _parse_note_file(path, vault_path, top_terms_limit)
        index.upsert(record)
        notes.append(note)
        updated += 1

    removed = index.remove_missing(paths)
    index.commit()

    total_files = len(md_files) if isinstance(md_files, list) else len(notes)
    stats = IncrementalStats(
        total=total_files,
        unchanged=unchanged,
        updated=updated,
        removed=removed,
    )
    return ParseResult(notes=notes), stats


def _load_notes_from_index(
    index: IndexStore,
    vault_path: Path,
) -> Tuple[ParseResult, IncrementalStats]:
    records = index.list_all()
    notes: List[ParsedNote] = []
    for record in records:
        rel_path = str(record.get("path", ""))
        note_path = vault_path / rel_path
        notes.append(_note_from_cache(note_path, rel_path, record))
    stats = IncrementalStats(
        total=len(notes),
        unchanged=len(notes),
        updated=0,
        removed=0,
    )
    return ParseResult(notes=notes), stats


def _cache_is_fresh(
    index: IndexStore,
    max_age_sec: int,
) -> bool:
    if max_age_sec <= 0:
        return False
    last_updated = index.get_meta("last_updated")
    pending = index.get_meta("pending")
    try:
        last_value = float(last_updated) if last_updated is not None else None
    except ValueError:
        last_value = None
    if last_value is None:
        return False
    if pending not in (None, "0", 0):
        return False
    age = time.time() - last_value
    return age <= max_age_sec


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
        top_terms = _top_terms(content_tokens, DEFAULT_TOP_TERMS)
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
                content_tokens=top_terms,
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
    note: ParsedNote, suggestions: List[Dict[str, object]], lang: str
) -> Dict[str, object]:
    anchor = "oka_related_v1"
    lines = [t(lang, "related_heading"), f"<!-- {anchor} -->"]
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


def _pair_stats_range(
    notes: List[ParsedNote],
    start: int,
    end: int,
) -> Tuple[List[Dict[str, object]], List[float]]:
    stats: List[Dict[str, object]] = []
    raw_values: List[float] = []
    for i in range(start, end):
        left = notes[i]
        for j in range(i + 1, len(notes)):
            right = notes[j]
            content_sim = _jaccard(set(left.content_tokens), set(right.content_tokens))
            title_sim = _jaccard(left.title_tokens, right.title_tokens)
            link_overlap = _jaccard(left.link_set, right.link_set)
            stats.append(
                {
                    "left": i,
                    "right": j,
                    "content_sim_raw": content_sim,
                    "title_sim": title_sim,
                    "link_overlap": link_overlap,
                }
            )
            raw_values.append(content_sim)
    return stats, raw_values


def recommend_notes(
    parse_result: ParseResult,
    vault_path: Path,
    config: ScoringConfig,
    max_workers: int,
    timeout_sec: int,
    max_mem_mb: int,
    lang: str = "en",
) -> RecommendationResult:
    notes = parse_result.notes
    downgrades: List[str] = []

    if max_mem_mb > 0:
        estimated_tokens = sum(len(note.content_tokens) for note in notes)
        estimated_mem_mb = (estimated_tokens * 16) / (1024 * 1024)
        if estimated_mem_mb > max_mem_mb:
            downgrades.append("recommend_skipped_mem_limit")
            return RecommendationResult([], [], [], 0, downgrades)

    pair_stats: List[Dict[str, object]] = []
    raw_content_values: List[float] = []
    start_time = time.monotonic()

    if max_workers > 1 and timeout_sec <= 0 and len(notes) > 2:
        from concurrent.futures import ThreadPoolExecutor

        chunk_size = max(1, len(notes) // max_workers)
        ranges = [
            (idx, min(idx + chunk_size, len(notes)))
            for idx in range(0, len(notes), chunk_size)
        ]
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for stats, raw in executor.map(
                lambda r: _pair_stats_range(notes, r[0], r[1]), ranges
            ):
                pair_stats.extend(stats)
                raw_content_values.extend(raw)
    else:
        timed_out = False
        for i in range(len(notes)):
            if timeout_sec > 0 and time.monotonic() - start_time >= timeout_sec:
                timed_out = True
                break
            left = notes[i]
            for j in range(i + 1, len(notes)):
                right = notes[j]
                content_sim = _jaccard(
                    set(left.content_tokens), set(right.content_tokens)
                )
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
        if timed_out:
            downgrades.append("recommend_timeout")

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
            related_blocks.append(_build_related_block(note, suggestions, lang))

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
        downgrades=downgrades,
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
    lang: str = "en",
) -> PlanResult:
    items: List[Dict[str, object]] = []
    for idx, target in enumerate(sorted(analysis.broken_links)[:5], start=1):
        target_path = target
        if not target_path.lower().endswith(".md"):
            target_path = f"{target_path}.md"
        reason = build_reason(0.0, 0.0, 0.0, [], config)
        reason["kind"] = "broken_link_candidate"
        reason["details"] = t(lang, "reason_broken_link", target=target)
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


def build_action_items(
    plan: PlanResult, vault_path: Path, profile: str
) -> Dict[str, object]:
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
    lang: str = "en",
) -> str:
    low_confidence = recommendations.low_confidence_count
    action_items_total = len(plan.items)
    lines = [
        f"# {t(lang, 'report_title')}",
        "",
        t(lang, "report_generated_at", timestamp=_now_iso()),
        t(lang, "report_vault", vault=vault_path),
        "",
        t(lang, "report_summary"),
        "",
        f"- {t(lang, 'report_metric_total_notes')}: {analysis.total_notes}",
        f"- {t(lang, 'report_metric_frontmatter')}: {analysis.frontmatter_notes}",
        f"- {t(lang, 'report_metric_total_links')}: {analysis.total_links}",
        f"- {t(lang, 'report_metric_broken')}: {len(analysis.broken_links)}",
        f"- {t(lang, 'report_metric_orphan')}: {len(analysis.orphan_notes)}",
        f"- {t(lang, 'report_metric_actions')}: {action_items_total}",
        "",
        t(lang, "report_metrics"),
        "",
        t(lang, "report_metric_header"),
        t(lang, "report_metric_sep"),
        f"| {t(lang, 'report_metric_total_notes')} | {analysis.total_notes} |",
        f"| {t(lang, 'report_metric_frontmatter')} | {analysis.frontmatter_notes} |",
        f"| {t(lang, 'report_metric_total_links')} | {analysis.total_links} |",
        f"| {t(lang, 'report_metric_broken')} | {len(analysis.broken_links)} |",
        f"| {t(lang, 'report_metric_orphan')} | {len(analysis.orphan_notes)} |",
        f"| {t(lang, 'report_metric_actions')} | {action_items_total} |",
        "",
        t(lang, "report_next_steps"),
        "",
        t(lang, "report_next_orphan"),
        t(lang, "report_next_broken"),
    ]
    if recommendations.merge_previews:
        lines.extend(["", t(lang, "report_merge_preview"), ""])
        for preview in recommendations.merge_previews:
            candidates = ", ".join(preview["candidates"])
            lines.append(
                t(
                    lang,
                    "report_merge_item",
                    candidates=candidates,
                    confidence=preview["average_confidence"],
                )
            )

    if low_confidence > 0:
        lines.extend(
            [
                "",
                t(lang, "report_tuning"),
                "",
                t(
                    lang,
                    "report_tuning_low",
                    count=low_confidence,
                    threshold=config.low_confidence,
                ),
                t(lang, "report_tuning_adjust"),
                t(lang, "report_tuning_filters"),
            ]
        )
    return "\n".join(lines)


def build_run_summary(
    run_id: str,
    timing_ms: Dict[str, int],
    scan_result: ScanResult,
    cache_present: bool,
    incremental: IncrementalStats,
    skipped_by_reason: Dict[str, int],
    downgrades: List[str],
    fast_path: bool,
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
    hit_rate = incremental.unchanged / incremental.total if incremental.total else 0.0
    return {
        "version": "1",
        "run_id": run_id,
        "fast_path": fast_path,
        "timing": {"total_ms": total_ms, "stages": stages},
        "io": {
            "scanned_files": len(scan_result.md_files),
            "skipped": scan_result.skipped,
            "skipped_by_reason": skipped_by_reason,
        },
        "cache": {
            "present": cache_present,
            "hit_rate": round(hit_rate, 3),
            "incremental_updated": incremental.updated,
        },
        "incremental": {
            "hit_rate": round(hit_rate, 3),
            "incremental_updated": incremental.updated,
            "removed": incremental.removed,
            "skipped_by_reason": skipped_by_reason,
        },
        "downgrades": downgrades,
    }


def write_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def run_pipeline(
    vault_path: Path,
    base_dir: Path,
    profile: str,
    max_file_mb: int = 5,
    lang: str = "en",
) -> PipelineOutput:
    run_id = _run_id()
    timings: Dict[str, int] = {}

    config_data = load_config(vault_path, base_dir)
    max_file_mb = get_int(config_data, "scan", "max_file_mb", max_file_mb)
    max_mem_mb = get_int(config_data, "performance", "max_mem_mb", 0)
    timeout_sec = get_int(config_data, "performance", "timeout_sec", 0)
    max_workers = get_int(config_data, "performance", "max_workers", 0)
    top_terms_limit = get_int(
        config_data, "performance", "top_terms", DEFAULT_TOP_TERMS
    )
    scoring_config = ScoringConfig(
        w_content=get_float(config_data, "scoring", "w_content", 0.6),
        w_title=get_float(config_data, "scoring", "w_title", 0.3),
        w_link=get_float(config_data, "scoring", "w_link", 0.1),
        clamp_min=get_float(config_data, "scoring", "clamp_min", 0.0),
        clamp_max=get_float(config_data, "scoring", "clamp_max", 1.0),
        path_penalty=get_float(config_data, "filters", "path_penalty", 0.9),
        min_related_confidence=get_float(
            config_data, "scoring", "min_related_confidence", 0.3
        ),
        merge_confidence=get_float(config_data, "scoring", "merge_confidence", 0.85),
        low_confidence=get_float(config_data, "scoring", "low_confidence", 0.45),
        norm_method=get_str(config_data, "scoring", "model", "quantile"),
    )

    cache_path = base_dir / "cache" / "index.sqlite"
    cache_present = cache_path.exists()
    fast_path_max_age = get_int(
        config_data, "performance", "fast_path_max_age_sec", DEFAULT_FAST_PATH_AGE_SEC
    )
    fast_path = False

    if cache_present:
        index = IndexStore(cache_path)
        fast_path = _cache_is_fresh(index, fast_path_max_age)
        index.close()

    start = time.perf_counter()
    if fast_path:
        scan_start = time.perf_counter()
        index = IndexStore(cache_path)
        parse_result, incremental_stats = _load_notes_from_index(index, vault_path)
        index.close()
        scan_result = ScanResult(
            md_files=[vault_path / note.rel_path for note in parse_result.notes],
            skipped={"non_md": 0, "too_large": 0, "no_permission": 0},
        )
        timings["scan_ms"] = int((time.perf_counter() - scan_start) * 1000)
        timings["parse_ms"] = 0
    else:
        scan_start = time.perf_counter()
        scan_result = scan_vault(
            vault_path,
            max_file_mb=max_file_mb,
            max_files_per_sec=get_int(config_data, "scan", "max_files_per_sec", 0),
            sleep_ms=get_int(config_data, "scan", "sleep_ms", 0),
        )
        timings["scan_ms"] = int((time.perf_counter() - scan_start) * 1000)

        parse_start = time.perf_counter()
        index = IndexStore(cache_path)
        parse_result, incremental_stats = _load_notes_with_cache(
            scan_result.md_files, vault_path, index, top_terms_limit
        )
        index.set_meta("last_updated", str(time.time()))
        index.set_meta("pending", "0")
        index.commit()
        index.close()
        timings["parse_ms"] = int((time.perf_counter() - parse_start) * 1000)

    analyze_start = time.perf_counter()
    analysis = analyze_notes(parse_result)
    timings["analyze_ms"] = int((time.perf_counter() - analyze_start) * 1000)

    recommend_start = time.perf_counter()
    recommendations = recommend_notes(
        parse_result,
        vault_path,
        scoring_config,
        max_workers=max_workers,
        timeout_sec=timeout_sec,
        max_mem_mb=max_mem_mb,
        lang=lang,
    )
    timings["recommend_ms"] = int((time.perf_counter() - recommend_start) * 1000)

    plan_start = time.perf_counter()
    plan = build_plan(analysis, recommendations, scoring_config, lang=lang)
    timings["plan_ms"] = int((time.perf_counter() - plan_start) * 1000)

    report_start = time.perf_counter()
    report_markdown = build_report(
        analysis,
        vault_path,
        recommendations,
        plan,
        scoring_config,
        lang=lang,
    )
    timings["report_ms"] = int((time.perf_counter() - report_start) * 1000)

    timings["total_ms"] = int((time.perf_counter() - start) * 1000)

    health = build_health(analysis, vault_path)
    action_items = build_action_items(plan, vault_path, profile)
    skipped_by_reason = dict(scan_result.skipped)
    skipped_by_reason["unchanged"] = incremental_stats.unchanged
    run_summary = build_run_summary(
        run_id,
        timings,
        scan_result,
        cache_present,
        incremental_stats,
        skipped_by_reason,
        recommendations.downgrades,
        fast_path,
    )

    return PipelineOutput(
        health=health,
        action_items=action_items,
        run_summary=run_summary,
        report_markdown=report_markdown,
    )
