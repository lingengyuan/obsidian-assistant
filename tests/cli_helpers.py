from __future__ import annotations

import io
import os
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from oka.cli.main import main


@dataclass
class CliResult:
    returncode: int
    stdout: str
    stderr: str


def run_oka(args: List[str], cwd: Optional[Path] = None) -> CliResult:
    stdout_io = io.StringIO()
    stderr_io = io.StringIO()
    prev_cwd = Path.cwd()

    if cwd is not None:
        os.chdir(cwd)

    try:
        with redirect_stdout(stdout_io), redirect_stderr(stderr_io):
            try:
                code = main(args)
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 0
    finally:
        os.chdir(prev_cwd)

    return CliResult(code or 0, stdout_io.getvalue(), stderr_io.getvalue())
