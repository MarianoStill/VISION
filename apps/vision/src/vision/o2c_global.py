"""Informe global O2C: consolida todas las delegaciones sin duplicar máquinas ni pedidos."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from vision import o2c_workspace

MULTIPLE_AREAS = "Varias delegaciones / áreas"
NO_AREA = "Sin delegación / área"
TOTAL = "Total"


def _text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (ValueError, TypeError):
        return ""
    return str(value).strip()


def delegation_breakdown(model: pd.DataFrame) -> pd.DataFrame:
    """Una fila por delegación y una fila Total.

    Un ID LION cuenta una sola vez aunque tenga varias filas. Un ID con varias
    delegaciones se agrupa aparte; sus pedidos y etapas no se reparten. La fila
    Total se calcula sobre IDs únicos, no sumando las delegaciones.
    """
    labels = o2c_workspace.stage_labels()
    columns = ["Delegación / área", "Máquinas", "Pedidos", *labels]
    if model is None or model.empty or "ID" not in model.columns:
        return pd.DataFrame(columns=columns)
    per_machine: dict[str, dict] = {}
    for _, record in model.iterrows():
        identifier = _text(record.get("ID"))
        if not identifier:
            continue
        entry = per_machine.setdefault(identifier, {"areas": set(), "orders": set(), "stages": set()})
        area = _text(record.get("Oficina de ventas"))
        if area:
            entry["areas"].add(area)
        order = _text(record.get("Pedido"))
        if order:
            entry["orders"].add(order)
        entry["stages"].update(o2c_workspace.stages_for_state(record.get("Estado")))
    groups: dict[str, list[dict]] = {}
    for entry in per_machine.values():
        areas = entry["areas"]
        name = MULTIPLE_AREAS if len(areas) > 1 else (next(iter(areas)) if areas else NO_AREA)
        groups.setdefault(name, []).append(entry)

    def row(name: str, entries: list[dict]) -> dict:
        data = {"Delegación / área": name, "Máquinas": len(entries),
                "Pedidos": len(set().union(*(e["orders"] for e in entries)))}
        for label in labels:
            data[label] = sum(1 for e in entries if label in e["stages"])
        return data

    rows = [row(name, groups[name]) for name in sorted(groups, key=str.casefold)]
    rows.append(row(TOTAL, [entry for entries in groups.values() for entry in entries]))
    return pd.DataFrame(rows, columns=columns)


def render_global_report(model: pd.DataFrame) -> None:
    st.markdown("### Informe global O2C")
    table = delegation_breakdown(model)
    if table.empty:
        st.info("No hay máquinas para consolidar.")
        return
    total = table[table["Delegación / área"] == TOTAL].iloc[0]
    metrics = st.columns(3)
    metrics[0].metric("Máquinas", int(total["Máquinas"]))
    metrics[1].metric("Pedidos", int(total["Pedidos"]))
    metrics[2].metric("Delegaciones / áreas", len(table) - 1)
    st.caption(
        "Cada máquina (ID LION) cuenta una sola vez. Una máquina puede estar en más de una "
        "etapa, por lo que la suma de etapas puede superar el total."
    )
    st.dataframe(table, hide_index=True, key="global_o2c_breakdown", alt="Consolidado por delegación")
