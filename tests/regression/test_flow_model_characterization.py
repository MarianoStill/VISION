import importlib.util
import os
from pathlib import Path
import sys

import pytest


@pytest.fixture(scope="module")
def flow_model():
    source_dir = os.environ.get("CO_VISION_PROOF_SOURCE_DIR")
    if not source_dir:
        pytest.skip("Set CO_VISION_PROOF_SOURCE_DIR to compare with received PROOF sources")

    source = Path(source_dir).expanduser().resolve() / "flow_model.py"
    if not source.is_file():
        pytest.fail(f"flow_model.py not found in configured source folder: {source.parent}")

    spec = importlib.util.spec_from_file_location("received_proof_flow_model", source)
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


RULES = [
    {"id": str(i), "name": f"Etapa {i}", "kind": "standard", "terminal": i == 10}
    for i in range(1, 11)
]
DATES = ["2026-10-13", "2026-10-14", "2026-10-16"]


def instance(machine, stage, instance_id, opened, closed=None):
    return {
        "machine": machine,
        "stage": stage,
        "instance": instance_id,
        "opening_date": opened,
        "closure_date": closed,
        "elapsed": 2,
        "status": "Cerrada" if closed else "Abierta",
    }


def events(rows):
    output = []
    for row in rows:
        output.append({**row, "type": "A", "observed_date": row["opening_date"]})
        if row["closure_date"]:
            output.append({**row, "type": "C", "observed_date": row["closure_date"]})
    return output


def test_initial_advanced_starts_at_next_opening(flow_model):
    rows = [
        instance("A", "3", "a", "2026-10-13", "2026-10-14"),
        instance("A", "4", "b", "2026-10-14", "2026-10-16"),
    ]
    projection = flow_model.project(events(rows), rows, DATES, RULES)

    assert projection["cohorts"]["A"]["entry"] == "2026-10-14"
    assert [row["instance"] for row in projection["instances"]] == ["b"]
    assert [(event["stage"], event["type"]) for event in projection["events"]] == [
        ("4", "A"),
        ("4", "C"),
    ]


def test_initial_stage1_is_partial_and_not_new_inflow(flow_model):
    rows = [instance("A", "1", "a", "2026-10-13", "2026-10-14")]
    projection = flow_model.project(events(rows), rows, DATES, RULES)

    assert len(projection["instances"]) == 1
    assert projection["instances"][0]["partial_start"]
    assert [event["type"] for event in projection["events"]] == ["C"]

    aggregates = flow_model.aggregate(
        projection, DATES, RULES, "Día", DATES[0], DATES[-1], ["1"]
    )
    assert sum(row["Entradas"] for row in aggregates) == 0
    assert sum(row["Salidas"] for row in aggregates) == 1
    assert all(row["Duración media de salidas (días)"] is None for row in aggregates)


def test_advanced_without_new_opening_excluded(flow_model):
    rows = [instance("A", "3", "a", "2026-10-13")]
    projection = flow_model.project(events(rows), rows, DATES, RULES)

    assert projection["cohorts"]["A"]["entry"] is None
    assert not projection["instances"]


def test_reopen_counts_movements_not_unique(flow_model):
    rows = [
        instance("A", "4", "a", "2026-10-14", "2026-10-14"),
        instance("A", "4", "b", "2026-10-16"),
    ]
    projection = flow_model.project(events(rows), rows, DATES, RULES)
    aggregate = flow_model.aggregate(
        projection, DATES, RULES, "Mes", DATES[0], DATES[-1], ["4"]
    )[0]

    assert aggregate["Entradas"] == 2
    assert aggregate["Documentos que entran"] == 1
    assert aggregate["Pendientes observados al cierre"] == 1


def test_terminal_no_pending_and_no_fake_day(flow_model):
    rows = [instance("A", "10", "a", "2026-10-14", "2026-10-14")]
    projection = flow_model.project(events(rows), rows, DATES, RULES)

    aggregates = flow_model.aggregate(
        projection, DATES, RULES, "Día", DATES[0], DATES[-1], ["10"]
    )
    assert len(aggregates) == 3
    assert all(row["Pendientes observados al cierre"] == 0 for row in aggregates)
    assert "2026-10-15" not in [row["Periodo"] for row in aggregates]
    assert flow_model.bucket("2026-10-16", "Semana") == "2026-10-12"
