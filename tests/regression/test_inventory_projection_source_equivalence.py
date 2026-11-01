import importlib.util
import os
from pathlib import Path
import sys

import pytest

from proof import project_inventory
from proof.inventory_projection import period_key


def load_original_module(source_dir):
    source = Path(source_dir).expanduser().resolve() / "inventory_chart.py"
    if not source.is_file():
        pytest.fail(f"inventory_chart.py not found in configured source folder: {source.parent}")
    spec = importlib.util.spec_from_file_location("received_proof_inventory_chart", source)
    if spec is None or spec.loader is None:
        pytest.fail(f"Cannot load configured source file: {source}")
    module = importlib.util.module_from_spec(spec)
    write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = write_bytecode
    return module


@pytest.fixture
def original_module():
    source_dir = os.environ.get("CO_VISION_PROOF_SOURCE_DIR")
    if not source_dir:
        pytest.skip("Set CO_VISION_PROOF_SOURCE_DIR to compare with received PROOF sources")
    return load_original_module(source_dir)


@pytest.fixture
def synthetic_inventory():
    rules = [
        {"id": "9", "name": "Transporte", "kind": "standard", "terminal": False},
        {"id": "2", "name": "Compras", "kind": "standard", "terminal": False},
        {"id": "10", "name": "Entregada", "kind": "standard", "terminal": True},
        {"id": "3", "name": "Especial", "kind": "special", "terminal": False},
        {"id": "1", "name": "Pedido", "kind": "standard", "terminal": False},
        {"id": "4", "name": "Taller terminal", "kind": "standard", "terminal": True},
    ]
    instances = [
        {"machine": "A", "stage": "1", "opening_date": "2026-01-02"},
        {
            "machine": "B",
            "stage": "1",
            "opening_date": "2026-01-02",
            "closure_date": "2026-01-08",
        },
        {
            "machine": "A",
            "stage": "2",
            "opening_date": "2026-01-08",
            "closure_date": "2026-01-15",
        },
        {"machine": "C", "stage": "2", "opening_date": "2026-01-08"},
        {
            "machine": "X",
            "stage": "9",
            "opening_date": "2026-01-02",
            "closure_date": "2026-01-08",
        },
        {"machine": "T", "stage": "10", "opening_date": "2026-01-02"},
        {"machine": "S", "stage": "3", "opening_date": "2026-01-02"},
        {"machine": "Q", "stage": "4", "opening_date": "2026-01-02"},
    ]
    dates = ["2026-01-15", "2026-01-02", "2026-01-08", "2026-01-08"]
    return instances, dates, rules


@pytest.mark.parametrize(
    "grain", ["Día", "Semana", "Mes", "otro"], ids=["day", "week", "month", "fallback"]
)
def test_public_service_matches_received_source(original_module, synthetic_inventory, grain):
    instances, dates, rules = synthetic_inventory
    expected = original_module.chart_rows(
        instances, dates, rules, grain, "2026-01-02", "2026-01-15"
    )
    actual = project_inventory(
        instances, dates, rules, grain, "2026-01-02", "2026-01-15"
    )
    assert actual == expected


def test_period_key_matches_received_source(original_module):
    for grain in ("Día", "Semana", "Mes", "otro"):
        assert period_key("2026-01-08", grain) == original_module.period_key(
            "2026-01-08", grain
        )
