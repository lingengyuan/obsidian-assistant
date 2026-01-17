from __future__ import annotations

import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
tests_path = repo_root / "tests"
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(tests_path))
