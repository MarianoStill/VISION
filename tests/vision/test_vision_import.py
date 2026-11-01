"""VISION package import smoke test."""

import subprocess
import sys


def test_vision_imports_independently() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import vision; print(vision.availability())"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "Base técnica disponible; lógica empresarial pendiente"
