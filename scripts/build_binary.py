import argparse
import platform
import subprocess
import sys
from pathlib import Path


def _platform_tag() -> str:
    system = platform.system().lower()
    if system.startswith("darwin"):
        return "macos"
    if system.startswith("windows"):
        return "windows"
    if system.startswith("linux"):
        return "linux"
    return system.replace(" ", "-")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build oka binary with PyInstaller.")
    parser.add_argument(
        "--mode",
        choices=("onefile", "onedir"),
        default="onefile",
        help="Packaging mode (default: onefile).",
    )
    parser.add_argument("--name", default="oka", help="Binary name (default: oka).")
    parser.add_argument(
        "--platform-tag",
        default="",
        help="Override platform tag (default: auto).",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Skip PyInstaller --clean.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = Path(__file__).resolve().parents[1]
    entrypoint = root / "scripts" / "entrypoint.py"
    if not entrypoint.exists():
        print(f"entrypoint not found: {entrypoint}")
        return 2

    tag = args.platform_tag or _platform_tag()
    dist_path = root / "dist" / f"{args.name}-{tag}"
    work_path = root / "build" / f"{args.name}-{tag}"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--name",
        args.name,
        "--paths",
        str(root / "src"),
        "--distpath",
        str(dist_path),
        "--workpath",
        str(work_path),
        "--specpath",
        str(work_path),
        "--console",
    ]
    if not args.no_clean:
        cmd.append("--clean")
    if args.mode == "onefile":
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")
    cmd.append(str(entrypoint))

    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
