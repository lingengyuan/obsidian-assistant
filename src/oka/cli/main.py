from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from oka import __version__
from oka.core.apply import apply_action_items, rollback_run, write_run_log
from oka.core.config import get_bool, get_int, get_str, load_config
from oka.core.doctor import run_doctor
from oka.core.pipeline import run_pipeline, write_json, write_report
from oka.core.storage import prune_run_logs


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
        run_id = pipeline_output.run_summary.get("run_id", "unknown")
        config_data = load_config(vault_path, base_dir)
        max_wait_sec = get_int(config_data, "apply", "max_wait_sec", 30)
        offline_marker = get_str(config_data, "apply", "offline_lock_marker", ".nosync")
        offline_cleanup = get_bool(
            config_data, "apply", "offline_lock_cleanup", True
        )
        apply_info = {
            "interactive": not args.yes,
            "ttl_sec": 60,
            "started_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }
        result = apply_action_items(
            vault_path=vault_path,
            base_dir=base_dir,
            run_id=run_id,
            action_items=pipeline_output.action_items,
            yes=args.yes,
            wait_sec=args.wait,
            force=args.force,
            max_wait_sec=max_wait_sec,
            offline_lock=args.offline_lock,
            offline_lock_marker=offline_marker,
            offline_lock_cleanup=offline_cleanup,
        )
        apply_info["waited_sec"] = result.waited_sec
        apply_info["starvation"] = result.starvation
        apply_info["fallback"] = result.fallback
        apply_info["offline_lock"] = result.offline_lock
        write_run_log(
            base_dir=base_dir,
            run_id=run_id,
            vault_path=vault_path,
            changes=result.changes,
            conflicts=result.conflicts,
            apply_info=apply_info,
        )
        _update_run_summary(
            output_dir,
            waited_sec=result.waited_sec,
            starvation=result.starvation,
            fallback=result.fallback,
            offline_lock=result.offline_lock,
        )
        prune_run_logs(base_dir, config_data)
        return result.return_code

    return 0


def _doctor_command(args: argparse.Namespace) -> int:
    base_dir = Path.cwd()
    _ensure_layout(base_dir)

    if args.init_config:
        target_dir = _resolve_vault_path(args.vault) or base_dir
        return _init_config(target_dir)

    vault_path = _resolve_vault_path(args.vault)
    if vault_path is None:
        print("Error: --vault or VAULT_PATH is required.", file=sys.stderr)
        return 2
    if not vault_path.exists():
        print(f"Error: vault path does not exist: {vault_path}", file=sys.stderr)
        return 2

    try:
        max_file_mb = int(os.environ.get("OKA_MAX_FILE_MB", "5"))
    except ValueError:
        max_file_mb = 5

    report = run_doctor(vault_path=vault_path, base_dir=base_dir, max_file_mb=max_file_mb)
    _print_doctor_report(report)
    return 0


def _init_config(target_dir: Path) -> int:
    target_dir = target_dir.resolve()
    config_path = target_dir / "oka.toml"
    if config_path.exists():
        print(f"oka.toml already exists at {config_path}.", file=sys.stderr)
        return 0

    config_path.write_text(_default_config_text(), encoding="utf-8")
    print(f"Created {config_path}")
    return 0


def _default_config_text() -> str:
    return "\n".join(
        [
            "# Obsidian Assistant configuration",
            "",
            "[profile]",
            'name = "conservative"',
            "",
            "[storage]",
            'reports_dir = "reports"',
            'cache_dir = "cache"',
            'locks_dir = "locks"',
            "max_run_logs = 50",
            "max_run_days = 30",
            "max_total_mb = 200",
            "compress_runs = false",
            "auto_prune = true",
            "",
            "[apply]",
            "interactive = true",
            "max_wait_sec = 30",
            'offline_lock_marker = ".nosync"',
            "offline_lock_cleanup = true",
            "",
            "[performance]",
            "max_mem_mb = 0",
            "timeout_sec = 0",
            "max_workers = 0",
            "top_terms = 30",
            "",
            "[scan]",
            "max_file_mb = 5",
            'exclude_dirs = [".obsidian"]',
            "",
            "[format]",
            "normalize_on_write = false",
            'encoding = "utf-8"',
            'line_ending = "lf"',
            "",
            "[scoring]",
            'model = "quantile"',
            "clamp_min = 0.0",
            "clamp_max = 1.0",
            "w_content = 0.5",
            "w_title = 0.3",
            "w_link = 0.2",
            "",
            "[filters]",
            "path_penalty = 0.9",
            "tag_conflict_penalty = 0.8",
            "",
        ]
    )


def _print_doctor_report(report: dict) -> None:
    path_checks = report.get("path_checks", {})
    locks = report.get("locks", {})
    encoding = report.get("encoding", {})
    line_endings = report.get("line_endings", {})
    scan = report.get("scan", {})
    skipped = scan.get("skipped", {})

    print("Doctor Report")
    print("-------------")
    print(f"Vault: {report.get('vault')}")
    print(
        "Path checks: exists={exists} is_dir={is_dir} readable={readable}".format(
            exists=path_checks.get("exists"),
            is_dir=path_checks.get("is_dir"),
            readable=path_checks.get("readable"),
        )
    )
    write_lease = locks.get("write_lease", {})
    offline_lock = locks.get("offline_lock", {})
    print(
        "Locks: write-lease present={present} stale={stale} | offline-lock present={opresent} stale={ostale}".format(
            present=write_lease.get("present"),
            stale=write_lease.get("stale"),
            opresent=offline_lock.get("present"),
            ostale=offline_lock.get("stale"),
        )
    )
    print(
        "Encoding: utf8_bom={bom} non_utf8={non_utf8}".format(
            bom=encoding.get("utf8_bom", 0),
            non_utf8=encoding.get("non_utf8", 0),
        )
    )
    print(
        "Line endings: lf={lf} crlf={crlf} mixed={mixed} none={none}".format(
            lf=line_endings.get("lf", 0),
            crlf=line_endings.get("crlf", 0),
            mixed=line_endings.get("mixed", 0),
            none=line_endings.get("none", 0),
        )
    )
    print(
        "Scan: scanned_files={scanned} skipped(non_md={non_md}, too_large={too_large}, "
        "no_permission={no_permission})".format(
            scanned=scan.get("scanned_files", 0),
            non_md=skipped.get("non_md", 0),
            too_large=skipped.get("too_large", 0),
            no_permission=skipped.get("no_permission", 0),
        )
    )

    recommendations = report.get("recommendations", [])
    if recommendations:
        print("Recommendations:")
        for item in recommendations:
            print(f"- {item}")


def _print_summary(summary: dict, file) -> None:
    timing = summary.get("timing", {})
    stages = timing.get("stages", {})
    io = summary.get("io", {})
    skipped = io.get("skipped", {})
    cache = summary.get("cache", {})
    incremental = summary.get("incremental", {})
    skipped_by_reason = incremental.get("skipped_by_reason", {})

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
    if skipped_by_reason:
        print(
            "Skipped by reason: {reasons}".format(reasons=skipped_by_reason),
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
        help="Apply Class A actions (write mode).",
    )
    run_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON to stdout (structured output).",
    )
    run_parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip interactive confirmation.",
    )
    run_parser.add_argument(
        "--wait",
        type=int,
        default=0,
        help="Wait up to N seconds for a quiet window before apply.",
    )
    run_parser.add_argument(
        "--force",
        action="store_true",
        help="Clear stale write lease before apply.",
    )
    run_parser.add_argument(
        "--offline-lock",
        action="store_true",
        help="Create an offline lock marker during apply.",
    )
    run_parser.add_argument(
        "--profile",
        default="conservative",
        help="Profile preset (placeholder).",
    )
    run_parser.set_defaults(func=_run_command)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check vault health and config.",
    )
    doctor_parser.add_argument(
        "--vault",
        type=Path,
        help="Path to the Obsidian vault.",
    )
    doctor_parser.add_argument(
        "--init-config",
        action="store_true",
        help="Write oka.toml template to vault root or cwd.",
    )
    doctor_parser.set_defaults(func=_doctor_command)

    rollback_parser = subparsers.add_parser(
        "rollback",
        help="Rollback a previous apply using run_id.",
    )
    rollback_parser.add_argument(
        "run_id",
        type=str,
        help="Run identifier from run-summary.json or reports/runs/<run_id>.",
    )
    rollback_parser.add_argument(
        "--item",
        type=str,
        help="Rollback a specific action_id (Class A only).",
    )
    rollback_parser.add_argument(
        "--file",
        type=str,
        help="Rollback Class A changes for a specific file path.",
    )
    rollback_parser.set_defaults(func=_rollback_command)

    return parser


def _rollback_command(args: argparse.Namespace) -> int:
    base_dir = Path.cwd()
    result = rollback_run(args.run_id, base_dir, item_id=args.item, target_path=args.file)
    return result.return_code


def _update_run_summary(
    output_dir: Path,
    waited_sec: int,
    starvation: bool,
    fallback: str,
    offline_lock: bool,
) -> None:
    summary_path = output_dir / "run-summary.json"
    if not summary_path.exists():
        return
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    apply_section = summary.get("apply", {})
    apply_section.update(
        {
            "waited_sec": waited_sec,
            "starvation": starvation,
            "fallback": fallback,
            "offline_lock": offline_lock,
        }
    )
    summary["apply"] = apply_section
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)
