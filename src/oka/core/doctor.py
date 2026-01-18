from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from oka.core.i18n import t
from oka.core.pipeline import scan_vault


@dataclass
class LockCheck:
    name: str
    path: Path
    present: bool
    stale: Optional[bool]
    details: str

    def as_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "path": str(self.path),
            "present": self.present,
            "stale": self.stale,
            "details": self.details,
        }


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str) -> Optional[datetime]:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _check_lock(path: Path) -> LockCheck:
    if not path.exists():
        return LockCheck(
            name=path.name, path=path, present=False, stale=None, details="missing"
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return LockCheck(
            name=path.name, path=path, present=True, stale=None, details="unreadable"
        )

    created_at = None
    if isinstance(data, dict):
        created_at = data.get("created_at") or data.get("createdAt")
        expires_at = data.get("expires_at") or data.get("expiresAt")
        ttl_sec = data.get("ttl_sec") or data.get("ttlSec")
    else:
        created_at = None
        expires_at = None
        ttl_sec = None

    if expires_at:
        parsed = _parse_iso(str(expires_at))
        if parsed:
            stale = parsed < _now_utc()
            return LockCheck(
                name=path.name,
                path=path,
                present=True,
                stale=stale,
                details="expires_at",
            )

    if created_at and ttl_sec:
        parsed = _parse_iso(str(created_at))
        try:
            ttl = int(ttl_sec)
        except (TypeError, ValueError):
            ttl = None
        if parsed and ttl is not None:
            stale = parsed + timedelta(seconds=ttl) < _now_utc()
            return LockCheck(
                name=path.name,
                path=path,
                present=True,
                stale=stale,
                details="created_at+ttl",
            )

    return LockCheck(
        name=path.name, path=path, present=True, stale=None, details="unknown"
    )


def _detect_encoding_and_eol(paths: List[Path]) -> Dict[str, object]:
    encoding_counts = {"utf8_bom": 0, "non_utf8": 0}
    line_endings = {"lf": 0, "crlf": 0, "mixed": 0, "none": 0}

    for path in paths:
        try:
            data = path.read_bytes()
        except OSError:
            continue

        if data.startswith(b"\xef\xbb\xbf"):
            encoding_counts["utf8_bom"] += 1

        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            encoding_counts["non_utf8"] += 1

        count_crlf = data.count(b"\r\n")
        count_lf = data.count(b"\n") - count_crlf

        if count_crlf == 0 and count_lf == 0:
            line_endings["none"] += 1
        elif count_crlf > 0 and count_lf > 0:
            line_endings["mixed"] += 1
        elif count_crlf > 0:
            line_endings["crlf"] += 1
        else:
            line_endings["lf"] += 1

    return {"encoding": encoding_counts, "line_endings": line_endings}


def run_doctor(
    vault_path: Path, base_dir: Path, max_file_mb: int, lang: str = "en"
) -> Dict[str, object]:
    scan_result = scan_vault(vault_path, max_file_mb=max_file_mb)
    encoding_report = _detect_encoding_and_eol(scan_result.md_files)

    locks_dir = base_dir / "locks"
    write_lease = _check_lock(locks_dir / "write-lease.json")
    offline_lock = _check_lock(locks_dir / "offline-lock.json")

    path_checks = {
        "exists": vault_path.exists(),
        "is_dir": vault_path.is_dir(),
        "readable": vault_path.exists()
        and vault_path.is_dir()
        and os.access(vault_path, os.R_OK),
    }

    recommendations: List[str] = []
    if (
        encoding_report["encoding"]["utf8_bom"]
        or encoding_report["encoding"]["non_utf8"]
    ):
        recommendations.append(t(lang, "doctor_rec_normalize"))
    if encoding_report["line_endings"]["mixed"]:
        recommendations.append(t(lang, "doctor_rec_line_endings"))
    if write_lease.present and write_lease.stale:
        recommendations.append(t(lang, "doctor_rec_write_lease"))
    if offline_lock.present and offline_lock.stale:
        recommendations.append(t(lang, "doctor_rec_offline_lock"))

    return {
        "version": "1",
        "vault": str(vault_path),
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "path_checks": path_checks,
        "locks": {
            "write_lease": write_lease.as_dict(),
            "offline_lock": offline_lock.as_dict(),
        },
        "encoding": encoding_report["encoding"],
        "line_endings": encoding_report["line_endings"],
        "recommendations": recommendations,
        "scan": {
            "scanned_files": len(scan_result.md_files),
            "skipped": scan_result.skipped,
        },
    }
