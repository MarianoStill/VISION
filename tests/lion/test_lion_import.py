"""LION package import smoke test."""

import subprocess
import sys


def test_lion_imports_independently() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, lion; assert 'pandas' not in sys.modules; "
            "print(lion.availability())",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "Base técnica disponible; lógica empresarial pendiente"
