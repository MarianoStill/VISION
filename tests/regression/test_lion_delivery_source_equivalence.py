import ast
import os
from pathlib import Path

import pytest

from lion import is_delivered


def load_received_function(source_dir):
    source = Path(source_dir).expanduser().resolve() / "lion_sap_engine.py"
    if not source.is_file():
        pytest.fail(f"lion_sap_engine.py not found in configured source folder: {source.parent}")

    module_tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    functions = [
        node
        for node in module_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "is_delivered"
    ]
    if len(functions) != 1:
        pytest.fail(f"Expected one top-level is_delivered function in {source}")

    function = functions[0]
    expected_function = ast.parse(
        'def is_delivered(status):\n    return "Entregadas" in str(status).split(" | ")\n'
    ).body[0]
    if ast.dump(function, include_attributes=False) != ast.dump(
        expected_function, include_attributes=False
    ):
        pytest.fail("Received is_delivered function has an unexpected structure")

    isolated_module = ast.Module(body=[function], type_ignores=[])
    namespace = {}
    exec(compile(isolated_module, str(source), "exec"), namespace)
    return namespace["is_delivered"]


@pytest.fixture
def received_function():
    source_dir = os.environ.get("CO_VISION_LION_SOURCE_DIR")
    if not source_dir:
        pytest.skip("Set CO_VISION_LION_SOURCE_DIR to compare with received LION sources")
    return load_received_function(source_dir)


@pytest.mark.parametrize(
    "synthetic_status",
    [
        "Entregadas",
        "Planning | Entregadas",
        "Entregadas | Taller",
        "Taller | Planning",
        "entregadas",
        " Entregadas ",
        "Entregadas extra",
        "",
        None,
    ],
)
def test_public_service_matches_isolated_received_function(
    received_function, synthetic_status
):
    assert is_delivered(synthetic_status) == received_function(synthetic_status)
