import pandas as pd

from vision.proof_link import resolve_proof_order_link


def _history():
    membership = {
        "machine": "SYNTHETIC-ORDER-001",
        "stage": "1",
    }
    return {
        "observations": [
            {
                "observed_date": "2026-01-02",
                "memberships": [membership],
            }
        ],
        "events": [],
        "instances": [],
    }


def test_links_exact_sales_document_when_unique_in_lion():
    model = pd.DataFrame(
        [
            {"ID": "synthetic-internal-a", "Pedido": "SYNTHETIC-ORDER-001"},
        ]
    )

    link = resolve_proof_order_link(model, model.iloc[0], _history())

    assert link["linked"] is True
    assert link["sales_document"] == "SYNTHETIC-ORDER-001"
    assert len(link["observations"]) == 1
    assert "no demuestra por sí solo identidad física de chasis" in link[
        "granularity_notice"
    ]


def test_does_not_link_when_multiple_lion_records_share_the_order():
    model = pd.DataFrame(
        [
            {"ID": "synthetic-internal-a", "Pedido": "SYNTHETIC-ORDER-001"},
            {"ID": "synthetic-internal-b", "Pedido": "SYNTHETIC-ORDER-001"},
        ]
    )

    link = resolve_proof_order_link(model, model.iloc[0], _history())

    assert link["linked"] is False
    assert link["observations"] == []
    assert "2 resultados LION" in link["reason"]


def test_does_not_fall_back_to_another_identifier_or_missing_history():
    model = pd.DataFrame(
        [
            {
                "ID": "synthetic-internal-a",
                "Pedido": "",
                "Número de serie": "SYNTHETIC-CHASSIS-001",
            }
        ]
    )

    link = resolve_proof_order_link(model, model.iloc[0], _history())

    assert link["linked"] is False
    assert link["sales_document"] is None
    assert "no tiene Documento de ventas" in link["reason"]
