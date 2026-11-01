import pandas as pd
import pytest

pytest.importorskip("streamlit")

from vision import o2c_workspace


def test_stage_labels_are_the_ten_lion_stages():
    labels = o2c_workspace.stage_labels()

    assert len(labels) == 10
    assert labels[0] == "Creando pedido"
    assert labels[-1] == "Entregada a cliente"


def test_membership_uses_lion_stage_progress():
    labels = o2c_workspace.stage_labels()

    assert o2c_workspace.stages_for_state("Taller") == ("Implementando cambios",)
    assert o2c_workspace.stages_for_state("Entregadas") == (labels[-1],)
    assert o2c_workspace.stages_for_state("Paradero desconocido") == ()
    assert len(o2c_workspace.stages_for_state("Planning | Arcese")) == 2


def test_multistage_machine_is_counted_once_across_stages():
    model = pd.DataFrame(
        {"ID": ["a", "b"], "Estado": ["Planning | Arcese", "Taller"]}
    )
    stages = o2c_workspace.machine_stages(model)
    both = o2c_workspace.stages_for_state("Planning | Arcese")

    selected = model[o2c_workspace.in_stages(stages, both)]
    per_stage = sum(
        o2c_workspace.in_stages(stages, [stage]).sum() for stage in both
    )

    assert selected["ID"].nunique() == 1
    assert per_stage == 2


def test_stage_columns_are_declared_for_ten_stages_and_follow_spec():
    assert sorted(o2c_workspace.O2C_STAGE_COLUMNS) == list(range(1, 11))
    labels = {n: [c.label for c in cols] for n, cols in o2c_workspace.O2C_STAGE_COLUMNS.items()}
    assert labels[1] == [
        "Documento de ventas", "Nombre del solicitante", "Denomin.posición",
        "Comercial", "Delegación / área", "Status de usuario",
    ]
    assert "Documento de ventas" not in labels[8]
    assert labels[10][-1] == "Doc.facturación"


def test_build_display_reports_missing_fields_and_formats_dates():
    table = pd.DataFrame({"ID": ["a"], "Urgencia": ["3"]})
    details = {
        "a": pd.DataFrame(
            {
                "Documento de ventas": ["S1", "S1"],
                "Fecha de entrega": ["2026-05-14 00:00:00", None],
            }
        )
    }
    spec = (
        o2c_workspace.Col("Documento de ventas", "Documento de ventas"),
        o2c_workspace.Col("Fecha de entrega", "Fecha de entrega"),
        o2c_workspace.Col("Entrega", "Entrega"),
    )

    display, missing = o2c_workspace.build_display(table, details, spec, with_urgency=True)

    assert missing == ["Entrega"]
    assert display.iloc[0].to_dict() == {
        "Documento de ventas": "S1",
        "Fecha de entrega": "14/05/2026",
        "Urgencia operacional": "3",
    }


def test_urgency_distribution_groups_by_band_and_reports_missing():
    bands = [(0, "#0f0"), (10, "#f00")]
    model = pd.DataFrame({"Urgencia": ["0", "5", "10", None]})

    rows = o2c_workspace.urgency_distribution(model, bands)

    assert [(label, count) for label, _, count in rows] == [
        ("0–9 d", 2),
        ("≥ 10 d", 1),
        ("Sin urgencia", 1),
    ]
