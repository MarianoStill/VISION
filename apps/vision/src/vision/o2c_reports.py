"""Informes globales del perfil O2C con filtros multiselección."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from vision.manager_reports import render_manager_reports, scope_documents

FILTERS = (
    ("areas", "Delegaciones", "Oficina de ventas"),
    ("commercials", "Comerciales", "Comercial"),
    ("clients", "Clientes", "Cliente"),
)


def _values(frame: pd.DataFrame, column: str) -> list[str]:
    if column not in frame.columns:
        return []
    found = {str(v).strip() for v in frame[column] if v is not None and not pd.isna(v) and str(v).strip()}
    return sorted(found, key=str.casefold)


def filter_scope(model: pd.DataFrame, *, areas=(), commercials=(), clients=()) -> pd.DataFrame:
    """Aplica los filtros acumulables; una lista vacía no restringe esa dimensión."""
    selected = {"Oficina de ventas": areas, "Comercial": commercials, "Cliente": clients}
    result = model
    for column, wanted in selected.items():
        wanted = set(wanted or ())
        if wanted and column in result.columns:
            result = result[result[column].astype(str).str.strip().isin(wanted)]
    return result


def render_o2c_reports(model: pd.DataFrame, history, *, history_token=None, load_completion) -> None:
    st.markdown("### Informes O2C")
    st.caption("Vista global. Sin filtros se incluye todo; puedes sumar varias delegaciones, comerciales y clientes.")
    cols = st.columns(3)
    chosen: dict[str, list[str]] = {}
    scope = model
    for slot, (key, title, column) in zip(cols, FILTERS):
        options = _values(scope, column)
        state_key = f"o2c_report_{key}"
        st.session_state[state_key] = [v for v in st.session_state.get(state_key, []) if v in options]
        chosen[key] = slot.multiselect(title, options, key=state_key, placeholder=f"Todas ({len(options)})" if key != "clients" else f"Todos ({len(options)})", disabled=not options)
        scope = filter_scope(scope, **{key: chosen[key]})
    st.caption(f"{scope['ID'].nunique() if 'ID' in scope.columns else len(scope)} máquinas en el ámbito")
    render_manager_reports(history, scope_documents(scope), load_completion=load_completion, history_token=history_token)
