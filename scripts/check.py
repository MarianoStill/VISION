from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MODULES = ("pytest", "pandas", "openpyxl", "streamlit")


def interpreter_path(root: Path, platform: str | None = None) -> Path:
    platform = sys.platform if platform is None else platform
    if platform == "win32":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def project_interpreter(root: Path, platform: str | None = None) -> Path:
    environment = root / ".venv"
    if not environment.is_dir():
        raise FileNotFoundError(
            f"Project virtual environment not found: {environment}\n"
            'Create it with: uv venv --python 3.14 .venv'
        )

    interpreter = interpreter_path(root, platform)
    if not interpreter.is_file():
        raise FileNotFoundError(
            f"Project Python interpreter not found: {interpreter}\n"
            "Recreate the project environment with: uv venv --python 3.14 .venv"
        )
    return interpreter


def minimum_python_version(root: Path) -> tuple[int, int]:
    with (root / "pyproject.toml").open("rb") as project_file:
        requirement = tomllib.load(project_file)["project"]["requires-python"]
    match = re.fullmatch(r"\s*>=\s*(\d+)\.(\d+)(?:\.\d+)?\s*", requirement)
    if match is None:
        raise ValueError(f"Unsupported requires-python declaration: {requirement}")
    return int(match.group(1)), int(match.group(2))


def unsupported_python_message(
    version: tuple[int, int], required: tuple[int, int]
) -> str | None:
    if version >= required:
        return None
    return (
        f"Python {required[0]}.{required[1]} or newer is required; "
        f"the project interpreter is {version[0]}.{version[1]}.\n"
        "Install a supported version with: uv python install 3.14; "
        "then recreate the environment with: uv venv --python 3.14 .venv"
    )


def missing_dependencies() -> list[str]:
    return [
        module
        for module in REQUIRED_MODULES
        if importlib.util.find_spec(module) is None
    ]


def main() -> int:
    try:
        expected_interpreter = project_interpreter(ROOT)
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return 2

    if Path(sys.executable).resolve() != expected_interpreter.resolve():
        print(
            "Run this check with the project interpreter: "
            f"{expected_interpreter} scripts/check.py",
            file=sys.stderr,
        )
        return 2

    try:
        required_version = minimum_python_version(ROOT)
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(
            f"Could not read the project's Python requirement: {error}",
            file=sys.stderr,
        )
        return 2

    version_error = unsupported_python_message(
        (sys.version_info.major, sys.version_info.minor), required_version
    )
    if version_error is not None:
        print(version_error, file=sys.stderr)
        return 2

    missing = missing_dependencies()
    if missing:
        print(
            "Required development dependencies are unavailable: "
            f"{', '.join(missing)}.\n"
            "Install them with: uv sync --locked --all-extras",
            file=sys.stderr,
        )
        return 2

    checks = [
        ("pytest", ["-m", "pytest"]),
        ("PROOF entry point", ["-m", "proof"]),
        ("LION entry point", ["-m", "lion"]),
        ("integrated VISION entry point", ["-m", "vision"]),
    ]

    for label, args in checks:
        print(f"== {label} ==", flush=True)
        completed = subprocess.run([sys.executable, *args], cwd=ROOT, check=False)
        if completed.returncode != 0:
            return completed.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
