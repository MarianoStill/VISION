import pandas as pd

from vision import manager_reports

RULES = [
    {"id": "1", "name": "Pedido", "kind": "standard", "terminal": False},
    {"id": "2", "name": "Compras", "kind": "standard", "terminal": False},
    {"id": "10", "name": "Entregada", "kind": "standard", "terminal": True},
]


def _history(instances, dates):
    return {"instances": instances, "dates": dates, "sources": RULES}


def test_scope_documents_uses_pedido_of_scoped_machines_only():
    model = pd.DataFrame({"Pedido": ["B", "A", "A", None, " "]})
    assert manager_reports.scope_documents(model) == ["A", "B"]
    assert manager_reports.scope_documents(pd.DataFrame({"X": [1]})) == []


def test_delegations_are_isolated_by_their_documents():
    instances = [
        {"machine": "A", "stage": "1", "opening_date": "2026-01-02"},
        {"machine": "B", "stage": "1", "opening_date": "2026-01-02"},
        {"machine": "C", "stage": "2", "opening_date": "2026-01-02"},
    ]
    history = _history(instances, ["2026-01-02"])
    frame_x = manager_reports.inventory_frame(
        _history([i for i in instances if i["machine"] in {"A", "B"}], history["dates"]),
        "Día", "2026-01-02", "2026-01-02",
    )
    frame_y = manager_reports.inventory_frame(
        _history([i for i in instances if i["machine"] == "C"], history["dates"]),
        "Día", "2026-01-02", "2026-01-02",
    )
    assert dict(zip(frame_x["Etapa"], frame_x["Expedientes pendientes"])) == {
        "1. Pedido": 2, "2. Compras": 0,
    }
    assert dict(zip(frame_y["Etapa"], frame_y["Expedientes pendientes"])) == {
        "1. Pedido": 0, "2. Compras": 1,
    }


def test_inventory_frame_aggregates_by_grain_and_excludes_terminal_stage():
    instances = [
        {"machine": "A", "stage": "1", "opening_date": "2026-01-05"},
        {"machine": "T", "stage": "10", "opening_date": "2026-01-05"},
    ]
    history = _history(instances, ["2026-01-05", "2026-01-07", "2026-02-02"])
    day = manager_reports.inventory_frame(history, "Día", "2026-01-05", "2026-02-02")
    week = manager_reports.inventory_frame(history, "Semana", "2026-01-05", "2026-02-02")
    month = manager_reports.inventory_frame(history, "Mes", "2026-01-05", "2026-02-02")
    assert day["Periodo"].nunique() == 3
    assert week["Periodo"].nunique() == 2
    assert month["Periodo"].nunique() == 2
    assert not any(day["Etapa"].str.startswith("10"))


def test_stage_card_explains_consumption_target_and_breakdown():
    row = {
        "id": "2", "name": "Solicitando máquina", "terminal": False, "target": 5,
        "documents": 134, "average_consumption": 159.4,
        "before_target": 17, "around_target": 3, "over_target": 114,
    }
    html = manager_reports._stage_card(row)
    for text in (
        "159 % del objetivo", "Objetivo: 5 días laborables", "expedientes activos",
        "CONSUMO MEDIO", "DISTRIBUCIÓN", "<b>17</b> Antes del objetivo",
        "<b>3</b> En torno al objetivo", "<b>114</b> Fuera de plazo",
    ):
        assert text in html
    assert "Sin consumo calculable" not in html
    row["documents"] = 140
    assert "<b>6</b> Sin consumo calculable" in manager_reports._stage_card(row)


def test_final_card_shows_deliveries_without_manual_button():
    done = {
        "completed_count": 7, "baseline_completed_count": 5,
        "registered_completed_count": 2, "baseline_date": "13/10/2026",
    }
    html = manager_reports._final_card(None, done)
    assert "entregas acumuladas" in html and "no se suma" in html
    assert "Calcular" not in html

    summary = {
        "stage_rows": [
            {"id": "1", "name": "Pedido", "terminal": False},
            {"id": "10", "name": "Entregada", "terminal": True},
        ]
    }
    assert [row["id"] for row in manager_reports.stage_cards(summary)] == ["1"]
    html = manager_reports._final_card(summary["stage_rows"][1], None)
    assert "terminal" in html.lower() and "No disponible" in html
    done = {"completed_count": 7, "baseline_completed_count": 5, "registered_completed_count": 2}
    assert "entregas acumuladas" in manager_reports._final_card(None, done)
