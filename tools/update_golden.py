from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.golden_utils import (  # noqa: E402
    build_reasoning_sample,
    extract_related_block,
    json_dumps,
    normalize_json,
    summarize_conflicts,
)

VAULT_SRC = ROOT / "tests" / "fixtures" / "test_vault"
GOLDEN_DIR = ROOT / "tests" / "golden"


def _run_cli(args: list[str], cwd: Path, env: dict[str, str]) -> None:
    cmd = [sys.executable, "-m", "oka", *args]
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="Overwrite golden outputs.")
    args = parser.parse_args()
    if not args.yes:
        print("Refusing to update golden outputs without --yes.")
        return 2

    if not VAULT_SRC.exists():
        print(f"Missing fixtures at {VAULT_SRC}")
        return 2

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        vault_dir = tmp_root / "vault"
        work_dir = tmp_root / "work"
        shutil.copytree(VAULT_SRC, vault_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")

        _run_cli(["run", "--vault", str(vault_dir)], work_dir, env)
        cold_summary = _load_json(work_dir / "reports" / "run-summary.json")
        action_items = _load_json(work_dir / "reports" / "action-items.json")

        _run_cli(["run", "--vault", str(vault_dir)], work_dir, env)
        incremental_summary = _load_json(work_dir / "reports" / "run-summary.json")

        _run_cli(["run", "--vault", str(vault_dir), "--apply", "--yes"], work_dir, env)
        apply_summary = _load_json(work_dir / "reports" / "run-summary.json")
        run_id = apply_summary.get("run_id")
        run_log = _load_json(
            work_dir / "reports" / "runs" / str(run_id) / "run-log.json"
        )

        normalized_cold = normalize_json(cold_summary, base_dir=work_dir, vault_dir=vault_dir)
        normalized_incremental = normalize_json(
            incremental_summary, base_dir=work_dir, vault_dir=vault_dir
        )
        normalized_run_log = normalize_json(run_log, base_dir=work_dir, vault_dir=vault_dir)

        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        _write(GOLDEN_DIR / "run-summary-cold-start.json", json_dumps(normalized_cold))
        _write(
            GOLDEN_DIR / "run-summary-incremental.json",
            json_dumps(normalized_incremental),
        )
        _write(GOLDEN_DIR / "run-log-sample.json", json_dumps(normalized_run_log))

        items = action_items.get("items", [])
        first_reason = next((item for item in items if item.get("reason")), None)
        if not first_reason:
            raise SystemExit("No action items with reason field found.")
        _write(
            GOLDEN_DIR / "reasoning-output-sample.txt",
            build_reasoning_sample(first_reason),
        )

        related_item = next(
            (item for item in items if item.get("type") == "append_related_links_section"),
            None,
        )
        if not related_item:
            raise SystemExit("No related-block action item found.")
        _write(
            GOLDEN_DIR / "related-block-normal.md",
            related_item.get("payload", {}).get("markdown_block", ""),
        )

        missing_anchor_path = None
        manifest = _load_json(VAULT_SRC / "manifest.json")
        for path, meta in manifest.items():
            if meta.get("expected_conflict") == "missing_anchor":
                missing_anchor_path = vault_dir / path
                break
        if missing_anchor_path:
            missing_block = extract_related_block(missing_anchor_path.read_text(encoding="utf-8"))
            _write(GOLDEN_DIR / "related-block-missing-anchor.md", missing_block)

        conflicts_summary = summarize_conflicts(run_log.get("conflicts", []))
        _write(
            GOLDEN_DIR / "conflicts-summary.json",
            json_dumps(normalize_json(conflicts_summary, base_dir=work_dir, vault_dir=vault_dir)),
        )

    print("Golden outputs updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
