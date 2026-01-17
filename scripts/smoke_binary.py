import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path


REQUIRED_OUTPUTS = [
    "reports/health.json",
    "reports/action-items.json",
    "reports/run-summary.json",
    "reports/report.md",
]


def _platform_tag() -> str:
    system = platform.system().lower()
    if system.startswith("darwin"):
        return "macos"
    if system.startswith("windows"):
        return "windows"
    if system.startswith("linux"):
        return "linux"
    return system.replace(" ", "-")


def _default_binary(root: Path) -> Path:
    name = "oka.exe" if platform.system().lower().startswith("windows") else "oka"
    return root / "dist" / f"oka-{_platform_tag()}" / name


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test oka binary.")
    parser.add_argument("--binary", type=Path, default=None, help="Path to binary.")
    parser.add_argument(
        "--vault",
        type=Path,
        default=Path("tests/fixtures/sample_vault"),
        help="Vault path (default: tests/fixtures/sample_vault).",
    )
    parser.add_argument("--lang", default="en", help="Language (default: en).")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove previous outputs before running.",
    )
    return parser.parse_args()


def _clean_outputs(root: Path) -> None:
    for rel_path in REQUIRED_OUTPUTS:
        path = root / rel_path
        if path.exists():
            path.unlink()


def main() -> int:
    args = _parse_args()
    root = Path(__file__).resolve().parents[1]
    binary = args.binary or _default_binary(root)
    vault = args.vault
    if not vault.is_absolute():
        vault = root / vault

    if not binary.exists():
        print(f"binary not found: {binary}")
        return 2

    if args.clean:
        _clean_outputs(root)

    cmd = [str(binary), "run", "--vault", str(vault), "--lang", args.lang]
    result = subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("stdout:")
        print(result.stdout)
        print("stderr:")
        print(result.stderr)
        return result.returncode or 1

    missing = []
    for rel_path in REQUIRED_OUTPUTS:
        if not (root / rel_path).exists():
            missing.append(rel_path)
    if missing:
        print(f"missing outputs: {', '.join(missing)}")
        return 3

    for rel_path in ("reports/health.json", "reports/action-items.json", "reports/run-summary.json"):
        payload = json.loads((root / rel_path).read_text(encoding="utf-8"))
        if "version" not in payload:
            print(f"missing version in {rel_path}")
            return 4

    print("binary smoke test: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
