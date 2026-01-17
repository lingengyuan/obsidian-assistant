from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict

from oka.core.i18n import t
from oka.core.index import IndexStore
from oka.core.pipeline import _load_notes_with_cache, scan_vault


def _try_low_priority() -> bool:
    if hasattr(os, "nice"):
        try:
            os.nice(10)
            return True
        except OSError:
            return False
    return False


def update_index_once(
    vault_path: Path,
    base_dir: Path,
    max_file_mb: int,
    max_files_per_sec: int,
    sleep_ms: int,
    top_terms_limit: int,
) -> Dict[str, int]:
    scan_result = scan_vault(
        vault_path,
        max_file_mb=max_file_mb,
        max_files_per_sec=max_files_per_sec,
        sleep_ms=sleep_ms,
    )
    cache_path = base_dir / "cache" / "index.sqlite"
    index = IndexStore(cache_path)
    _, incremental = _load_notes_with_cache(
        scan_result.md_files, vault_path, index, top_terms_limit
    )
    index.set_meta("last_updated", str(time.time()))
    index.set_meta("pending", "0")
    index.commit()
    index.close()
    return {
        "scanned": len(scan_result.md_files),
        "updated": incremental.updated,
        "unchanged": incremental.unchanged,
        "removed": incremental.removed,
    }


def watch_loop(
    vault_path: Path,
    base_dir: Path,
    max_file_mb: int,
    max_files_per_sec: int,
    sleep_ms: int,
    top_terms_limit: int,
    interval_sec: int,
    once: bool,
    low_priority: bool = True,
    lang: str = "en",
) -> None:
    if low_priority:
        _try_low_priority()

    while True:
        stats = update_index_once(
            vault_path=vault_path,
            base_dir=base_dir,
            max_file_mb=max_file_mb,
            max_files_per_sec=max_files_per_sec,
            sleep_ms=sleep_ms,
            top_terms_limit=top_terms_limit,
        )
        print(t(lang, "watch_summary", **stats))
        if once:
            break
        time.sleep(interval_sec)
