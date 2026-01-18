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
from oka.core.i18n import t
from oka.core.doctor import run_doctor
from oka.core.pipeline import run_pipeline, write_json, write_report
from oka.core.storage import prune_run_logs
from oka.core.watch import watch_loop


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
    lang = args.lang or "en"
    vault_path = _resolve_vault_path(args.vault)
    if vault_path is None:
        print(t(lang, "error_vault_required"), file=sys.stderr)
        return 2
    if not vault_path.exists():
        print(t(lang, "error_vault_missing", vault=vault_path), file=sys.stderr)
        return 2

    base_dir = Path.cwd()
    _ensure_layout(base_dir)
    output_dir = base_dir / "reports"
    config_data = load_config(vault_path, base_dir)
    lang = args.lang or get_str(config_data, "i18n", "language", "en")
    try:
        max_file_mb = int(os.environ.get("OKA_MAX_FILE_MB", "5"))
    except ValueError:
        max_file_mb = 5

    pipeline_output = run_pipeline(
        vault_path=vault_path,
        base_dir=base_dir,
        profile=args.profile,
        max_file_mb=max_file_mb,
        lang=lang,
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
        _print_summary(pipeline_output.run_summary, file=sys.stderr, lang=lang)
    else:
        _print_summary(pipeline_output.run_summary, file=sys.stdout, lang=lang)

    if args.apply:
        run_id = pipeline_output.run_summary.get("run_id", "unknown")
        max_wait_sec = get_int(config_data, "apply", "max_wait_sec", 30)
        offline_marker = get_str(config_data, "apply", "offline_lock_marker", ".nosync")
        offline_cleanup = get_bool(
            config_data, "apply", "offline_lock_cleanup", True
        )
        git_policy = get_str(config_data, "apply.git", "policy", "require_clean")
        git_auto_commit = get_bool(config_data, "apply.git", "auto_commit", False)
        git_auto_stash = git_policy == "auto_stash"
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
            git_policy=git_policy,
            git_auto_stash=git_auto_stash,
            git_auto_commit=git_auto_commit,
            lang=lang,
        )
        apply_info["waited_sec"] = result.waited_sec
        apply_info["starvation"] = result.starvation
        apply_info["fallback"] = result.fallback
        apply_info["offline_lock"] = result.offline_lock
        apply_info["git"] = result.git_info
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
        lang = args.lang or "en"
        return _init_config(target_dir, lang)

    vault_path = _resolve_vault_path(args.vault)
    if vault_path is None:
        lang = args.lang or "en"
        print(t(lang, "error_vault_required"), file=sys.stderr)
        return 2
    if not vault_path.exists():
        lang = args.lang or "en"
        print(t(lang, "error_vault_missing", vault=vault_path), file=sys.stderr)
        return 2

    try:
        max_file_mb = int(os.environ.get("OKA_MAX_FILE_MB", "5"))
    except ValueError:
        max_file_mb = 5

    config_data = load_config(vault_path, base_dir)
    lang = args.lang or get_str(config_data, "i18n", "language", "en")
    report = run_doctor(
        vault_path=vault_path, base_dir=base_dir, max_file_mb=max_file_mb, lang=lang
    )
    _print_doctor_report(report, lang=lang)
    return 0


def _watch_command(args: argparse.Namespace) -> int:
    vault_path = _resolve_vault_path(args.vault)
    if vault_path is None:
        lang = args.lang or "en"
        print(t(lang, "error_vault_required"), file=sys.stderr)
        return 2
    if not vault_path.exists():
        lang = args.lang or "en"
        print(t(lang, "error_vault_missing", vault=vault_path), file=sys.stderr)
        return 2

    base_dir = Path.cwd()
    _ensure_layout(base_dir)
    config_data = load_config(vault_path, base_dir)
    lang = args.lang or get_str(config_data, "i18n", "language", "en")

    watch_loop(
        vault_path=vault_path,
        base_dir=base_dir,
        max_file_mb=get_int(config_data, "scan", "max_file_mb", 5),
        max_files_per_sec=(
            args.max_files_per_sec
            if args.max_files_per_sec is not None
            else get_int(config_data, "scan", "max_files_per_sec", 0)
        ),
        sleep_ms=(
            args.sleep_ms
            if args.sleep_ms is not None
            else get_int(config_data, "scan", "sleep_ms", 0)
        ),
        top_terms_limit=get_int(config_data, "performance", "top_terms", 30),
        interval_sec=args.interval,
        once=args.once,
        low_priority=not args.no_low_priority,
        lang=lang,
    )
    return 0


def _init_config(target_dir: Path, lang: str) -> int:
    target_dir = target_dir.resolve()
    config_path = target_dir / "oka.toml"
    if config_path.exists():
        print(t(lang, "config_exists", path=config_path), file=sys.stderr)
        return 0

    config_path.write_text(_default_config_text(), encoding="utf-8")
    print(t(lang, "config_created", path=config_path))
    return 0


def _default_config_text() -> str:
    return "\n".join(
        [
            "# Obsidian Assistant configuration",
            "",
            "[profile]",
            'name = "conservative"',
            "",
            "[i18n]",
            'language = "en"',
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
            "[apply.git]",
            'policy = "require_clean"',
            "auto_commit = false",
            "",
            "[performance]",
            "max_mem_mb = 0",
            "timeout_sec = 0",
            "max_workers = 0",
            "top_terms = 30",
            "fast_path_max_age_sec = 10",
            "",
            "[scan]",
            "max_file_mb = 5",
            "max_files_per_sec = 0",
            "sleep_ms = 0",
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


def _print_doctor_report(report: dict, lang: str) -> None:
    path_checks = report.get("path_checks", {})
    locks = report.get("locks", {})
    encoding = report.get("encoding", {})
    line_endings = report.get("line_endings", {})
    scan = report.get("scan", {})
    skipped = scan.get("skipped", {})

    print(t(lang, "doctor_report"))
    print("-------------")
    print(t(lang, "doctor_vault", vault=report.get("vault")))
    print(
        t(
            lang,
            "doctor_path_checks",
            exists=path_checks.get("exists"),
            is_dir=path_checks.get("is_dir"),
            readable=path_checks.get("readable"),
        )
    )
    write_lease = locks.get("write_lease", {})
    offline_lock = locks.get("offline_lock", {})
    print(
        t(
            lang,
            "doctor_locks",
            present=write_lease.get("present"),
            stale=write_lease.get("stale"),
            opresent=offline_lock.get("present"),
            ostale=offline_lock.get("stale"),
        )
    )
    print(
        t(
            lang,
            "doctor_encoding",
            bom=encoding.get("utf8_bom", 0),
            non_utf8=encoding.get("non_utf8", 0),
        )
    )
    print(
        t(
            lang,
            "doctor_line_endings",
            lf=line_endings.get("lf", 0),
            crlf=line_endings.get("crlf", 0),
            mixed=line_endings.get("mixed", 0),
            none=line_endings.get("none", 0),
        )
    )
    print(
        t(
            lang,
            "doctor_scan",
            scanned=scan.get("scanned_files", 0),
            non_md=skipped.get("non_md", 0),
            too_large=skipped.get("too_large", 0),
            no_permission=skipped.get("no_permission", 0),
        )
    )

    recommendations = report.get("recommendations", [])
    if recommendations:
        print(t(lang, "doctor_recommendations"))
        for item in recommendations:
            print(f"- {item}")


def _print_summary(summary: dict, file, lang: str) -> None:
    timing = summary.get("timing", {})
    stages = timing.get("stages", {})
    io = summary.get("io", {})
    skipped = io.get("skipped", {})
    cache = summary.get("cache", {})
    incremental = summary.get("incremental", {})
    skipped_by_reason = incremental.get("skipped_by_reason", {})

    print("", file=file)
    print(t(lang, "performance_summary"), file=file)
    print("-------------------", file=file)
    print(t(lang, "performance_total", total=timing.get("total_ms", 0)), file=file)
    print(
        t(
            lang,
            "performance_stages",
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
        t(
            lang,
            "performance_io",
            scanned=io.get("scanned_files", 0),
            non_md=skipped.get("non_md", 0),
            too_large=skipped.get("too_large", 0),
            no_permission=skipped.get("no_permission", 0),
        ),
        file=file,
    )
    print(
        t(
            lang,
            "performance_cache",
            present=cache.get("present", False),
            hit_rate=cache.get("hit_rate", 0.0),
            updated=cache.get("incremental_updated", 0),
        ),
        file=file,
    )
    if "fast_path" in summary:
        print(
            t(lang, "performance_fast_path", fast_path=summary.get("fast_path")),
            file=file,
        )
    if skipped_by_reason:
        print(t(lang, "performance_skipped_by_reason", reasons=skipped_by_reason), file=file)

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
    run_parser.add_argument(
        "--lang",
        help="Output language (en or zh).",
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
    doctor_parser.add_argument(
        "--lang",
        help="Output language (en or zh).",
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
    rollback_parser.add_argument(
        "--lang",
        help="Output language (en or zh).",
    )
    rollback_parser.set_defaults(func=_rollback_command)

    watch_parser = subparsers.add_parser(
        "watch",
        help="Watch a vault and keep the index up to date.",
    )
    watch_parser.add_argument(
        "--vault",
        type=Path,
        help="Path to the Obsidian vault.",
    )
    watch_parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Seconds between scans.",
    )
    watch_parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single scan and exit.",
    )
    watch_parser.add_argument(
        "--max-files-per-sec",
        type=int,
        help="Throttle scan rate (overrides config).",
    )
    watch_parser.add_argument(
        "--sleep-ms",
        type=int,
        help="Sleep per file during scan (overrides config).",
    )
    watch_parser.add_argument(
        "--no-low-priority",
        action="store_true",
        help="Disable low-priority scheduling attempt.",
    )
    watch_parser.add_argument(
        "--lang",
        help="Output language (en or zh).",
    )
    watch_parser.set_defaults(func=_watch_command)

    return parser


def _rollback_command(args: argparse.Namespace) -> int:
    base_dir = Path.cwd()
    lang = args.lang or "en"
    result = rollback_run(
        args.run_id,
        base_dir,
        item_id=args.item,
        target_path=args.file,
        lang=lang,
    )
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
