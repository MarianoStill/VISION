from __future__ import annotations

import pandas as pd

from vision import lion_adapter


def _available(value) -> bool:
    return value is not None and not pd.isna(value) and bool(str(value).strip())


def _source_options(
    model: pd.DataFrame,
    details: dict | None,
    *,
    source_field: str,
    model_field: str,
) -> list[str]:
    values = set()
    for _, row in model.iterrows():
        source_rows = (details or {}).get(row.get("ID"))
        if source_rows is not None and source_field in source_rows.columns:
            values.update(
                str(value).strip()
                for value in source_rows[source_field]
                if _available(value)
            )
        elif model_field in row.index and _available(row[model_field]):
            values.add(str(row[model_field]).strip())
    return sorted(values, key=str.casefold)


def commercial_options(model: pd.DataFrame, details: dict | None = None) -> list[str]:
    return _source_options(
        model,
        details,
        source_field="Sales Representive Name",
        model_field="Comercial",
    )


DELEGATION_FIELD = "Oficina de ventas"


def delegation_options(model: pd.DataFrame) -> list[str]:
    """Delegaciones presentes en la salida LION (campo SAP Oficina de ventas)."""
    if DELEGATION_FIELD not in model.columns:
        return []
    values = {str(v).strip() for v in model[DELEGATION_FIELD] if _available(v)}
    return sorted(values, key=str.casefold)


def scope_by_delegation(
    model: pd.DataFrame, details: dict | None, delegation: str
) -> tuple[pd.DataFrame, dict]:
    """Máquinas (y detalles) cuya oficina de ventas es exactamente la delegación."""
    if DELEGATION_FIELD not in model.columns:
        return model.iloc[:0].copy(), {}
    mask = model[DELEGATION_FIELD].map(lambda v: str(v).strip() == delegation)
    scoped = model.loc[mask].copy()
    ids = set(scoped["ID"])
    return scoped, {k: v for k, v in (details or {}).items() if k in ids}


def client_options(
    model: pd.DataFrame, details: dict | None = None
) -> list[str]:
    return _source_options(
        model,
        details,
        source_field="Nombre del solicitante",
        model_field="Cliente",
    )


def client_choices(
    model: pd.DataFrame, details: dict | None
) -> dict[str, tuple[str, int]]:
    """Etiqueta visible -> (cliente, máquinas); «Todos los clientes» primero."""
    names = client_options(model, details)
    choices = {ALL_CLIENTS: (ALL_CLIENTS, _machine_count(model))}
    for name in names:
        count = _machine_count(
            lion_adapter.filter_machines(model, details, filters={"Cliente": name})
        )
        choices[f"{name} — {count} máquinas" if count != 1 else f"{name} — 1 máquina"] = (
            name,
            count,
        )
    return choices


ALL_CLIENTS = "Todos los clientes"


def _machine_count(model: pd.DataFrame) -> int:
    return model["ID"].nunique() if "ID" in model.columns else len(model)


def sort_by_urgency(model: pd.DataFrame) -> pd.DataFrame:
    """Orden de presentación numérico descendente; empates estables, vacíos al final."""
    if "Urgencia" not in model.columns:
        return model.copy()
    # Sort on a temporary Series; never overwrite LION values or introduce a model column.
    numeric = pd.to_numeric(model["Urgencia"], errors="coerce")
    positions = pd.Series(numeric.to_numpy(), index=range(len(model)))
    order = positions.sort_values(ascending=False, na_position="last", kind="mergesort").index
    return model.iloc[order].copy()


def delivered_mask(model: pd.DataFrame) -> pd.Series:
    """Pertenencia explícita a Entregadas; no inferir desde fechas ni avance."""
    if "Estado" not in model.columns:
        return pd.Series(False, index=model.index, dtype=bool)
    return model["Estado"].fillna("").astype(str).str.split(" | ", regex=False).map(
        lambda parts: any(part.strip() == "Entregadas" for part in parts)
    ).astype(bool)
