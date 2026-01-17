from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from oka.core.doctor import _check_lock, _detect_encoding_and_eol


def test_check_lock_with_expires(tmp_path: Path) -> None:
    lock_path = tmp_path / "write-lease.json"
    expires_at = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    lock_path.write_text(json.dumps({"expires_at": expires_at}), encoding="utf-8")
    check = _check_lock(lock_path)
    assert check.present is True
    assert check.stale is True
    assert check.details == "expires_at"


def test_check_lock_with_ttl(tmp_path: Path) -> None:
    lock_path = tmp_path / "offline-lock.json"
    created_at = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    lock_path.write_text(
        json.dumps({"created_at": created_at, "ttl_sec": 5}), encoding="utf-8"
    )
    check = _check_lock(lock_path)
    assert check.present is True
    assert check.stale is True
    assert check.details == "created_at+ttl"


def test_detect_encoding_and_eol(tmp_path: Path) -> None:
    lf_path = tmp_path / "lf.md"
    crlf_path = tmp_path / "crlf.md"
    bom_path = tmp_path / "bom.md"

    lf_path.write_bytes(b"line1\nline2\n")
    crlf_path.write_bytes(b"line1\r\nline2\r\n")
    bom_path.write_bytes(b"\xef\xbb\xbf" + "line1\n".encode("utf-8"))

    result = _detect_encoding_and_eol([lf_path, crlf_path, bom_path])
    assert result["encoding"]["utf8_bom"] == 1
    assert result["line_endings"]["lf"] == 2
    assert result["line_endings"]["crlf"] == 1
