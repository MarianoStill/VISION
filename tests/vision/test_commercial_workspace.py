import pandas as pd

from vision.commercial_workspace import (
    ALL_CLIENTS,
    _advance,
    _history_segments,
    client_choices,
    client_options,
    commercial_options,
    confirmed_delivery_dates,
    delegation_options,
    format_sap_date,
    format_sap_dates,
    proof_stage_counts,
    scope_by_delegation,
    urgency_bands,
    urgency_color,
    urgency_legend,
)

BLUE, GREEN, YELLOW, ORANGE, RED = "#b", "#g", "#y", "#o", "#r"


def test_delegation_helpers_use_only_sales_office_field():
    model = pd.DataFrame(
        {
            "ID": ["1", "2", "3"],
            "Oficina de ventas": ["Delegación X", " Delegación X ", ""],
        }
    )
    details = {"1": pd.DataFrame(), "2": pd.DataFrame(), "3": pd.DataFrame()}
    assert delegation_options(model) == ["Delegación X"]
    scoped, scoped_details = scope_by_delegation(model, details, "Delegación X")
    assert scoped["ID"].tolist() == ["1", "2"]
    assert set(scoped_details) == {"1", "2"}
    assert delegation_options(model.drop(columns="Oficina de ventas")) == []


def test_sap_dates_format_without_timestamp_or_fallback():
    assert format_sap_date("2026-05-14 00:00:00") == "14/05/2026"
    assert format_sap_date(pd.Timestamp("2026-05-14")) == "14/05/2026"
    assert format_sap_date("") == "—"
    assert format_sap_date(None) == "—"
    assert format_sap_dates(["2026-05-14 00:00:00 | 2026-06-01 00:00:00"]) == (
        "14/05/2026 · 01/06/2026"
    )
    assert format_sap_dates(["", None]) == "—"


def test_confirmed_delivery_is_never_filled_from_other_fields():
    model = pd.DataFrame(
        {
            "ID": ["A", "B", "C"],
            "Fecha de entrega (Excel)": ["2026-05-14 00:00:00"] * 3,
        }
    )
    details = {
        "A": pd.DataFrame(
            {"Fecha de entrega confirmada": [pd.Timestamp("2026-05-20"), ""]}
        ),
        "B": pd.DataFrame({"Fecha de entrega confirmada": [""]}),
    }
    assert list(confirmed_delivery_dates(model, details)) == ["20/05/2026", "—", "—"]


def _urgency_model():
    # Valores sintéticos; el color por cuartiles repartía el 49, 75 y 133 entre colores.
    rows = [
        (-5, BLUE, "Taller"),
        (0, GREEN, "Taller"),
        (10, GREEN, "Taller"),
        (49, GREEN, "Taller"),
        (49, YELLOW, "Taller"),
        (60, YELLOW, "Taller"),
        (75, YELLOW, "Taller"),
        (75, ORANGE, "Taller"),
        (100, ORANGE, "Taller"),
        (133, ORANGE, "Taller"),
        (133, RED, "Taller"),
        (500, RED, "Taller"),
        (82, GREEN, "Entregadas"),
    ]
    return pd.DataFrame(rows, columns=["Urgencia", "Color urgencia", "Estado"])


def test_urgency_bands_use_inclusive_lower_bounds_from_lion_colors():
    bands = urgency_bands(_urgency_model())

    assert bands == [(-5, BLUE), (0, GREEN), (49, YELLOW), (75, ORANGE), (133, RED)]
    for value, expected in {
        -5: BLUE,
        -1: BLUE,
        0: GREEN,
        48: GREEN,
        49: YELLOW,
        74: YELLOW,
        75: ORANGE,
        132: ORANGE,
        133: RED,
        1534: RED,
    }.items():
        assert urgency_color(value, bands) == expected


def test_urgency_color_depends_only_on_value_not_on_row_or_state():
    model = _urgency_model()
    bands = urgency_bands(model)
    delivered_82 = urgency_color(model.iloc[-1]["Urgencia"], bands)

    assert delivered_82 == urgency_color(82, bands) == ORANGE
    assert urgency_color("82", bands) == urgency_color(82.0, bands) == ORANGE
    shuffled = model.sample(frac=1, random_state=3)
    assert urgency_bands(shuffled) == bands
    assert urgency_bands(model[model["Urgencia"] != 82]) == bands
    assert urgency_color(None, bands) is None
    assert urgency_color("no numérico", bands) is None
    assert urgency_color(5, []) is None


def test_urgency_legend_lists_ranges_without_overlap():
    legend = urgency_legend(urgency_bands(_urgency_model()))

    for text in ("≤ -1", "0–48", "49–74", "75–132", "≥ 133"):
        assert text in legend


def test_client_choices_are_sorted_with_all_clients_first():
    model = pd.DataFrame(
        [
            {"ID": "1", "Cliente": "Zeta", "Comercial": "X"},
            {"ID": "2", "Cliente": "Alfa", "Comercial": "X"},
            {"ID": "3", "Cliente": "Alfa", "Comercial": "X"},
        ]
    )

    choices = client_choices(model, {})

    assert list(choices) == [ALL_CLIENTS, "Alfa — 2 máquinas", "Zeta — 1 máquina"]
    assert choices[ALL_CLIENTS] == (ALL_CLIENTS, 3)
    assert choices["Alfa — 2 máquinas"] == ("Alfa", 2)


def test_advance_is_the_position_in_the_lion_stage_sequence():
    current = _advance("Taller")
    assert (current["position"], current["total"]) == (6, 10)
    assert current["text"] == "Etapa 6 de 10"
    assert _advance("Taller | Planning")["position"] == 7
    assert _advance("Entregadas")["position"] == 10
    unknown = _advance("sin etapa conocida")
    assert unknown["position"] is None
    assert unknown["text"] == "Etapa no determinada"


def test_advance_limits_o2c_detail_timeline_to_authorized_stages():
    current_stage = "Planificando la entrega"
    advance = _advance("Planning | Arcese", allowed_stages=[current_stage])

    assert [stage["label"] for stage in advance["timeline"]] == [current_stage]
    assert advance["states"] == [current_stage]
    assert advance["total"] == 1
    assert advance["position"] is None
    assert "Etapa 7 de 10" not in advance["text"]
    assert advance["scoped_percent"] == 50


def test_history_segments_group_only_consecutive_equal_observations():
    records = [
        {"date": "2026-10-14", "stages": ("A",)},
        {"date": "2026-10-15", "stages": ("A",)},
        {"date": "2026-10-16", "stages": ("B",)},
        {"date": "2026-10-19", "stages": ("A",)},
    ]
    segments = _history_segments(records)
    assert [(s["first"], s["last"], s["count"]) for s in segments] == [
        ("2026-10-14", "2026-10-15", 2),
        ("2026-10-16", "2026-10-16", 1),
        ("2026-10-19", "2026-10-19", 1),
    ]
    assert sum(s["count"] for s in segments) == len(records)


def test_client_options_are_derived_from_current_lion_results():
    model = pd.DataFrame(
        [
            {"Cliente": "Cuenta Beta"},
            {"Cliente": "Cuenta Alfa"},
            {"Cliente": "Cuenta Beta"},
            {"Cliente": ""},
            {"Cliente": None},
        ]
    )

    assert client_options(model) == ["Cuenta Alfa", "Cuenta Beta"]
    assert client_options(pd.DataFrame([{"Máquina": "Sin campo Cliente"}])) == []


def test_commercial_and_client_options_come_from_scoped_source_rows():
    model = pd.DataFrame(
        [
            {"ID": "machine-a", "Comercial": "Comercial A", "Cliente": "Cuenta A"},
            {"ID": "machine-b", "Comercial": "Comercial B", "Cliente": "Cuenta B"},
        ]
    )
    details = {
        "machine-a": pd.DataFrame(
            {
                "Sales Representive Name": ["Comercial A"],
                "Nombre del solicitante": ["Cuenta A"],
            }
        ),
        "machine-b": pd.DataFrame(
            {
                "Sales Representive Name": ["Comercial B"],
                "Nombre del solicitante": ["Cuenta B"],
            }
        ),
    }

    assert commercial_options(model, details) == ["Comercial A", "Comercial B"]
    assert client_options(model.iloc[:1], {"machine-a": details["machine-a"]}) == [
        "Cuenta A"
    ]


def test_proof_stage_counts_use_latest_exact_sales_document_observations():
    history = {
        "sources": [
            {"id": "1", "name": "Etapa PROOF inicial"},
            {"id": "2", "name": "Etapa PROOF actual"},
        ],
        "observations": [
            {
                "observed_date": "2026-01-01",
                "memberships": [
                    {"machine": "ORDER-A", "stage": "1"},
                    {"machine": "ORDER-B", "stage": "1"},
                ],
            },
            {
                "observed_date": "2026-01-02",
                "memberships": [
                    {"machine": "ORDER-A", "stage": "2"},
                    {"machine": "ORDER-A", "stage": "2"},
                ],
            },
        ],
        "events": [],
        "instances": [],
    }

    rows, observed_count = proof_stage_counts(
        history, ["ORDER-A", "ORDER-B", "ORDER-NO-HISTORY"]
    )

    assert rows == [
        {"Etapa PROOF": "Etapa PROOF inicial", "Expedientes (Documento de ventas)": 1},
        {"Etapa PROOF": "Etapa PROOF actual", "Expedientes (Documento de ventas)": 1},
    ]
    assert observed_count == 2


def test_proof_stage_counts_do_not_invent_zero_history():
    rows, observed_count = proof_stage_counts(None, ["ORDER-A"])

    assert rows == []
    assert observed_count == 0
