"""PROOF package import smoke test."""

import subprocess
import sys


def test_proof_imports_independently() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, proof; assert 'openpyxl' not in sys.modules; "
            "print(proof.availability())",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "Base técnica disponible; lógica empresarial pendiente"
