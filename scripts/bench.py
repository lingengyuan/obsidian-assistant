from __future__ import annotations

import argparse
import json
import random
import string
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

from oka.core.pipeline import run_pipeline


def _random_words(count: int) -> str:
    words = []
    for _ in range(count):
        word = "".join(random.choice(string.ascii_lowercase) for _ in range(6))
        words.append(word)
    return " ".join(words)


def _generate_vault(root: Path, note_count: int) -> Path:
    notes_dir = root / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    for idx in range(note_count):
        body = _random_words(80)
        link = f"[[note-{(idx + 1) % note_count}]]"
        content = f"# Note {idx}\\n\\n{body}\\n\\n{link}\\n"
        (notes_dir / f"note-{idx}.md").write_text(content, encoding="utf-8")
    return root


def _write_config(
    base_dir: Path,
    timeout_sec: int,
    max_mem_mb: int,
    max_workers: int,
    top_terms: int,
) -> None:
    config_lines = [
        "[performance]",
        f"timeout_sec = {timeout_sec}",
        f"max_mem_mb = {max_mem_mb}",
        f"max_workers = {max_workers}",
        f"top_terms = {top_terms}",
        "",
    ]
    (base_dir / "oka.toml").write_text("\n".join(config_lines), encoding="utf-8")


def _run_bench(
    note_count: int,
    timeout_sec: int,
    max_mem_mb: int,
    max_workers: int,
    top_terms: int,
) -> dict:
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_dir = Path(tmp_dir)
        vault_dir = base_dir / "vault"
        _generate_vault(vault_dir, note_count)
        _write_config(base_dir, timeout_sec, max_mem_mb, max_workers, top_terms)

        tracemalloc.start()
        start = time.perf_counter()
        output = run_pipeline(vault_path=vault_dir, base_dir=base_dir, profile="conservative")
        elapsed = time.perf_counter() - start
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        timing = output.run_summary.get("timing", {})
        stages = timing.get("stages", {})
        throughput = note_count / elapsed if elapsed > 0 else 0.0

        return {
            "notes": note_count,
            "total_ms": timing.get("total_ms", 0),
            "stages_ms": stages,
            "throughput_notes_per_sec": round(throughput, 2),
            "peak_mem_mb": round(peak / (1024 * 1024), 2),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark oka pipeline.")
    parser.add_argument(
        "--sizes",
        default="100,1000,10000",
        help="Comma-separated note counts to benchmark.",
    )
    parser.add_argument(
        "--notes",
        type=int,
        help="Single note count to benchmark (overrides --sizes).",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=2,
        help="Recommendation timeout in seconds (0 disables).",
    )
    parser.add_argument(
        "--max-mem-mb",
        type=int,
        default=0,
        help="Memory limit for recommendations (0 disables).",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=0,
        help="Thread workers for recommendations (0 disables).",
    )
    parser.add_argument(
        "--top-terms",
        type=int,
        default=30,
        help="Token limit stored per note in the cache.",
    )
    args = parser.parse_args()

    if args.notes is not None:
        sizes = [args.notes]
    else:
        sizes = [int(value) for value in args.sizes.split(",") if value.strip()]
    random.seed(42)

    results = {"runs": []}
    for size in sizes:
        print(f"Running benchmark for {size} notes...", file=sys.stderr)
        results["runs"].append(
            _run_bench(
                size,
                timeout_sec=args.timeout_sec,
                max_mem_mb=args.max_mem_mb,
                max_workers=args.max_workers,
                top_terms=args.top_terms,
            )
        )

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
