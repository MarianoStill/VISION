import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "imports",
    [
        ("proof", "lion", "vision.integration"),
        ("lion", "vision.integration", "proof"),
        ("vision.integration", "proof", "lion"),
    ],
)
def test_integrated_modules_load_without_circular_imports(
    imports: tuple[str, ...],
) -> None:
    script = """
import importlib
import sys

for module in sys.argv[1:]:
    importlib.import_module(module)

from vision.integration import integrated_availability

expected_status = "Base técnica disponible; lógica empresarial pendiente"
statuses = integrated_availability()
assert statuses == {
    "PROOF": expected_status,
    "LION": expected_status,
    "VISION": expected_status,
}
"""
    subprocess.run(
        [sys.executable, "-c", script, *imports],
        check=True,
        capture_output=True,
        text=True,
    )


def test_integrated_entry_point_reports_all_modules() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "vision"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.splitlines() == [
        "PROOF: Base técnica disponible; lógica empresarial pendiente",
        "LION: Base técnica disponible; lógica empresarial pendiente",
        "VISION: Base técnica disponible; lógica empresarial pendiente",
    ]
