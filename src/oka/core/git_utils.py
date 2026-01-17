from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional, Tuple


def run_git(repo: Path, args: List[str]) -> Tuple[int, str, str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 1, "", "git not found"


def is_git_repo(repo: Path) -> bool:
    code, _, _ = run_git(repo, ["rev-parse", "--is-inside-work-tree"])
    return code == 0


def is_clean(repo: Path) -> bool:
    code, stdout, _ = run_git(repo, ["status", "--porcelain"])
    if code != 0:
        return False
    return stdout.strip() == ""


def stash_push(repo: Path) -> bool:
    code, stdout, _ = run_git(repo, ["stash", "push", "-u", "-m", "oka auto stash"])
    if code != 0:
        return False
    return "No local changes" not in stdout


def stash_pop(repo: Path) -> bool:
    code, _, _ = run_git(repo, ["stash", "pop"])
    return code == 0


def git_commit(repo: Path, message: str, allow_empty: bool) -> Optional[str]:
    run_git(repo, ["add", "-A"])
    commit_args = [
        "-c",
        "user.name=oka",
        "-c",
        "user.email=oka@local",
        "commit",
        "-m",
        message,
    ]
    if allow_empty:
        commit_args.append("--allow-empty")
    code, _, _ = run_git(repo, commit_args)
    if code != 0:
        return None
    code, stdout, _ = run_git(repo, ["rev-parse", "HEAD"])
    if code != 0:
        return None
    return stdout.strip()
