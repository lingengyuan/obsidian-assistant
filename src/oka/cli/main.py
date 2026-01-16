from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from oka import __version__
from oka.core.pipeline import run_pipeline, write_json, write_report


def _resolve_vault_path(cli_value: Optional[Path]) -> Optional[Path]:
    if cli_value is not None:
        return cli_value
    env_value = os.environ.get("VAULT_PATH")
    if env_value:
        return Path(env_value)
    return None


def _ensure_layout(base_dir: Path) -> None:
    for name in ("reports", "cache", "locks"):
        (base_dir / name).mkdir(parents=True, exist_ok=True)


def _run_command(args: argparse.Namespace) -> int:
    vault_path = _resolve_vault_path(args.vault)
    if vault_path is None:
        print("Error: --vault or VAULT_PATH is required.", file=sys.stderr)
        return 2
    if not vault_path.exists():
        print(f"Error: vault path does not exist: {vault_path}", file=sys.stderr)
        return 2

    base_dir = Path.cwd()
    _ensure_layout(base_dir)
    output_dir = base_dir / "reports"
    try:
        max_file_mb = int(os.environ.get("OKA_MAX_FILE_MB", "5"))
    except ValueError:
        max_file_mb = 5

    pipeline_output = run_pipeline(
        vault_path=vault_path,
        base_dir=base_dir,
        profile=args.profile,
        max_file_mb=max_file_mb,
    )

    write_json(output_dir / "health.json", pipeline_output.health)
    write_json(output_dir / "action-items.json", pipeline_output.action_items)
    write_json(output_dir / "run-summary.json", pipeline_output.run_summary)
    write_report(output_dir / "report.md", pipeline_output.report_markdown)

    if args.json:
        payload = {
            "version": "1",
            "health": pipeline_output.health,
            "action_items": pipeline_output.action_items,
            "run_summary": pipeline_output.run_summary,
        }
        json.dump(payload, sys.stdout)
        sys.stdout.write("\n")
        _print_summary(pipeline_output.run_summary, file=sys.stderr)
    else:
        _print_summary(pipeline_output.run_summary, file=sys.stdout)

    if args.apply:
        print("Warning: --apply is not implemented in v1.0.0 run.", file=sys.stderr)

    return 0


def _doctor_command(args: argparse.Namespace) -> int:
    vault_path = _resolve_vault_path(args.vault)
    if args.init_config:
        print("oka doctor scaffold: init-config not implemented.")
    else:
        print("oka doctor scaffold: checks not implemented.")
    if vault_path is not None:
        print(f"vault: {vault_path}")
    return 0


def _print_summary(summary: dict, file) -> None:
    timing = summary.get("timing", {})
    stages = timing.get("stages", {})
    io = summary.get("io", {})
    skipped = io.get("skipped", {})
    cache = summary.get("cache", {})

    print("", file=file)
    print("Performance Summary", file=file)
    print("-------------------", file=file)
    print(f"Total: {timing.get('total_ms', 0)} ms", file=file)
    print(
        "Stages: scan={scan}ms parse={parse}ms analyze={analyze}ms "
        "recommend={recommend}ms plan={plan}ms report={report}ms".format(
            scan=stages.get("scan_ms", 0),
            parse=stages.get("parse_ms", 0),
            analyze=stages.get("analyze_ms", 0),
            recommend=stages.get("recommend_ms", 0),
            plan=stages.get("plan_ms", 0),
            report=stages.get("report_ms", 0),
        ),
        file=file,
    )
    print(
        "I/O: scanned_files={scanned} skipped(non_md={non_md}, too_large={too_large}, "
        "no_permission={no_permission})".format(
            scanned=io.get("scanned_files", 0),
            non_md=skipped.get("non_md", 0),
            too_large=skipped.get("too_large", 0),
            no_permission=skipped.get("no_permission", 0),
        ),
        file=file,
    )
    print(
        "Cache: present={present} hit_rate={hit_rate} incremental_updated={updated}".format(
            present=cache.get("present", False),
            hit_rate=cache.get("hit_rate", 0.0),
            updated=cache.get("incremental_updated", 0),
        ),
        file=file,
    )

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oka",
        description="Obsidian Knowledge Assistant CLI (scaffold).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"oka {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser(
        "run",
        help="Scan a vault and generate reports.",
    )
    run_parser.add_argument(
        "--vault",
        type=Path,
        help="Path to the Obsidian vault.",
    )
    run_parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply actions (not implemented).",
    )
    run_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON to stdout (structured output).",
    )
    run_parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip prompts (not implemented).",
    )
    run_parser.add_argument(
        "--profile",
        default="conservative",
        help="Profile preset (placeholder).",
    )
    run_parser.set_defaults(func=_run_command)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check vault health and config (scaffold).",
    )
    doctor_parser.add_argument(
        "--vault",
        type=Path,
        help="Path to the Obsidian vault.",
    )
    doctor_parser.add_argument(
        "--init-config",
        action="store_true",
        help="Write oka.toml template (not implemented).",
    )
    doctor_parser.set_defaults(func=_doctor_command)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)
