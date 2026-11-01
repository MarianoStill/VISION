from __future__ import annotations

import pandas as pd

import proof


def resolve_proof_order_link(model, selected, history):
    """Relate PROOF's sales-document history only when the exact order is unique in LION."""
    value = selected.get("Pedido")
    if value is None or pd.isna(value) or not str(value).strip():
        return {
            "linked": False,
            "sales_document": None,
            "reason": "El resultado seleccionado de LION no tiene Documento de ventas.",
            "observations": [],
            "events": [],
            "instances": [],
        }

    sales_document = str(value).strip()
    matching_lion_rows = model.loc[
        model["Pedido"].map(lambda item: str(item).strip()) == sales_document
    ]
    if len(matching_lion_rows) != 1:
        return {
            "linked": False,
            "sales_document": sales_document,
            "reason": (
                "PROOF registra el histórico por Documento de ventas y "
                f"{len(matching_lion_rows)} resultados LION comparten este pedido."
            ),
            "observations": [],
            "events": [],
            "instances": [],
        }

    records = proof.history_for_sales_document(history, sales_document)
    observations = records["observations"]
    events = records["events"]
    instances = records["instances"]
    if not observations and not events:
        return {
            "linked": False,
            "sales_document": sales_document,
            "reason": "PROOF no tiene observaciones clasificadas para este Documento de ventas.",
            "observations": [],
            "events": [],
            "instances": [],
        }
    return {
        "linked": True,
        "sales_document": sales_document,
        "reason": None,
        "observations": observations,
        "events": events,
        "instances": instances,
        "granularity_notice": (
            "Vínculo por coincidencia exacta de Documento de ventas. El histórico "
            "PROOF conserva granularidad de pedido y no demuestra por sí solo "
            "identidad física de chasis."
        ),
    }
