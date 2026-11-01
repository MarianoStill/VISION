import subprocess
import sys

import pytest

from proof import project_inventory
from proof import inventory_projection
from proof.inventory_projection import period_key
from tests.proof.inventory_projection_consumer import consume_inventory_projection


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


def test_period_key_preserves_day_week_month_and_fallback():
    assert period_key("2026-01-08", "Día") == "2026-01-08"
    assert period_key("2026-01-08", "Semana") == "2026-01-05"
    assert period_key("2026-01-08", "Mes") == "2026-01-01"
    assert period_key("2026-01-08", "otro") == "2026-01-08"


def test_chart_rows_characterizes_inventory_projection(synthetic_inventory):
    instances, dates, rules = synthetic_inventory
    rows, stages = project_inventory(
        instances, dates, rules, "Día", "2026-01-02", "2026-01-15"
    )

    assert [str(stage["id"]) for stage in stages] == ["1", "2", "9"]
    assert [
        (
            row["Periodo"],
            row["Etapa"],
            row["Expedientes pendientes"],
            row["Fecha observada"],
        )
        for row in rows
    ] == [
            ("2026-01-02", "1. Pedido", 2, "2026-01-02"),
            ("2026-01-02", "2. Compras", 0, "2026-01-02"),
            ("2026-01-02", "9. Transporte", 1, "2026-01-02"),
            ("2026-01-08", "1. Pedido", 1, "2026-01-08"),
            ("2026-01-08", "2. Compras", 2, "2026-01-08"),
            ("2026-01-08", "9. Transporte", 0, "2026-01-08"),
            ("2026-01-15", "1. Pedido", 1, "2026-01-15"),
            ("2026-01-15", "2. Compras", 1, "2026-01-15"),
            ("2026-01-15", "9. Transporte", 0, "2026-01-15"),
    ]


def test_public_service_returns_projection_output(synthetic_inventory):
    instances, dates, rules = synthetic_inventory
    expected = inventory_projection.chart_rows(
        instances, dates, rules, "Semana", "2026-01-02", "2026-01-15"
    )
    assert project_inventory(
        instances, dates, rules, "Semana", "2026-01-02", "2026-01-15"
    ) == expected


def test_public_service_delegates_without_copying_calculation(monkeypatch):
    expected = (["synthetic-row"], ["synthetic-stage"])
    received = {}

    def fake_chart_rows(*args):
        received["args"] = args
        return expected

    monkeypatch.setattr(inventory_projection, "chart_rows", fake_chart_rows)
    inputs = ([], ["2026-01-08"], [], "Día", "2026-01-01", "2026-01-31")
    assert project_inventory(*inputs) is expected
    assert received["args"] == inputs


def test_public_service_handles_empty_inputs_as_current_implementation():
    assert project_inventory([], [], [], "Día", "2026-01-01", "2026-01-31") == ([], [])


def test_public_service_returns_zero_rows_for_empty_instances_and_observed_periods():
    rules = [{"id": "1", "name": "Sintética", "kind": "standard", "terminal": False}]
    assert project_inventory(
        [], ["2026-01-08"], rules, "Día", "2026-01-01", "2026-01-31"
    ) == (
        [
            {
                "Periodo": "2026-01-08",
                "Etapa": "1. Sintética",
                "Expedientes pendientes": 0,
                "Fecha observada": "2026-01-08",
            }
        ],
        rules,
    )


def test_public_service_does_not_import_streamlit_or_external_sources():
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
import proof
proof.project_inventory([], [], [], "Día", "2026-01-01", "2026-01-31")
assert "streamlit" not in sys.modules
assert "inventory_chart" not in sys.modules
""",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_another_module_can_use_the_public_service(synthetic_inventory):
    instances, dates, rules = synthetic_inventory
    result = consume_inventory_projection(
        instances, dates, rules, "Mes", "2026-01-01", "2026-01-31"
    )
    assert result[0][0]["Periodo"] == "2026-01-01"


def test_empty_dates_keep_selected_stages_but_return_no_rows():
    rules = [{"id": "1", "name": "Sintética", "kind": "standard", "terminal": False}]
    assert project_inventory([], [], rules, "Día", "2026-01-01", "2026-01-31") == (
        [],
        rules,
    )
