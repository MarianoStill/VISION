from __future__ import annotations

from datetime import date, datetime
from html import escape
import re

import pandas as pd
import streamlit as st

import proof
from vision import lion_adapter
from vision.commercial_portfolio import (
    ALL_CLIENTS,
    DELEGATION_FIELD,
    _available,
    _machine_count,
    _source_options,
    client_choices,
    client_options,
    commercial_options,
    delegation_options,
    delivered_mask,
    scope_by_delegation,
    sort_by_urgency,
)
from vision.proof_link import resolve_proof_order_link
















def urgency_bands(model: pd.DataFrame) -> list[tuple[int, str]]:
    """Límites inferiores inclusivos por color, derivados de la salida de LION.

    Para cada color asignado por LION a máquinas no entregadas se toma su valor
    mínimo de urgencia. Un valor pertenece a la banda cuyo límite inferior es el
    mayor que no lo supera, de modo que un valor compartido por dos colores
    entra siempre en la banda más urgente.
    """
    if not {"Urgencia", "Color urgencia", "Estado"} <= set(model.columns):
        return []
    delivered = model["Estado"].astype(str).str.split(" | ", regex=False).map(
        lambda parts: "Entregadas" in parts
    )
    values = pd.to_numeric(model["Urgencia"], errors="coerce")
    usable = ~delivered & values.notna() & model["Color urgencia"].map(_available)
    lowers: dict[str, int] = {}
    for value, color in zip(values[usable], model.loc[usable, "Color urgencia"]):
        lowers[str(color)] = min(int(value), lowers.get(str(color), int(value)))
    return sorted(((lower, color) for color, lower in lowers.items()))


def urgency_color(value, bands: list[tuple[int, str]]) -> str | None:
    number = pd.to_numeric(value, errors="coerce")
    if not bands or pd.isna(number):
        return None
    color = bands[0][1]
    for lower, band_color in bands:
        if int(number) >= lower:
            color = band_color
    return color


def urgency_legend(bands: list[tuple[int, str]]) -> str:
    items = []
    for index, (lower, color) in enumerate(bands):
        upper = bands[index + 1][0] - 1 if index + 1 < len(bands) else None
        if index == 0 and upper is not None:
            text = f"≤ {upper}"
        elif upper is None:
            text = f"≥ {lower}"
        else:
            text = f"{lower}–{upper}" if upper > lower else str(lower)
        items.append(
            f'<span style="display:inline-flex;align-items:center;gap:.3rem;'
            f'margin-right:.9rem"><i style="width:.7rem;height:.7rem;border-radius:50%;'
            f'background:{escape(color)};display:inline-block"></i>{escape(text)}</span>'
        )
    return "".join(items)






def proof_stage_counts(
    history: dict | None, sales_documents: list[str]
) -> tuple[list[dict], int]:
    if history is None:
        return [], 0

    sources = history.get("sources", [])
    counts = {str(source["id"]): set() for source in sources}
    observed_documents = set()
    for document in set(sales_documents):
        observations = proof.history_for_sales_document(history, document)[
            "observations"
        ]
        if not observations:
            continue
        observed_documents.add(document)
        latest = observations[-1]
        for membership in latest["memberships"]:
            if str(membership.get("machine", "")).strip() != document:
                continue
            stage = str(membership.get("stage", ""))
            if stage in counts:
                counts[stage].add(document)

    rows = [
        {
            "Etapa PROOF": source["name"],
            "Expedientes (Documento de ventas)": len(counts[str(source["id"])]),
        }
        for source in sources
    ]
    return rows, len(observed_documents)




NO_DATE = "—"
CONFIRMED_DELIVERY_FIELD = "Fecha de entrega confirmada"
_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[ T]00:00:00(?:\.0+)?)?$")


def format_sap_date(value) -> str:
    """DD/MM/AAAA para una fecha SAP; «—» si no existe. No interpreta ni deriva."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return NO_DATE
    if isinstance(value, (datetime, date)):
        return value.strftime("%d/%m/%Y")
    if not _available(value):
        return NO_DATE
    text = str(value).strip()
    match = _ISO_DATE.match(text)
    if match:
        try:
            return date(*map(int, match.groups())).strftime("%d/%m/%Y")
        except ValueError:
            return text
    return text


def format_sap_dates(values) -> str:
    """Une los valores distintos presentes, sin sustituir los ausentes."""
    parts = []
    for value in values:
        for piece in str(value).split(" | ") if isinstance(value, str) else [value]:
            shown = format_sap_date(piece)
            if shown != NO_DATE and shown not in parts:
                parts.append(shown)
    return " · ".join(parts) or NO_DATE


def confirmed_delivery_dates(
    model: pd.DataFrame, details: dict | None
) -> pd.Series:
    """Fecha de entrega confirmada de SAP por máquina (solo desde los detalles LION)."""
    shown = []
    for identifier in model.get("ID", []):
        frame = (details or {}).get(identifier)
        values = (
            frame[CONFIRMED_DELIVERY_FIELD]
            if frame is not None and CONFIRMED_DELIVERY_FIELD in frame.columns
            else []
        )
        shown.append(format_sap_dates(values))
    return pd.Series(shown, index=model.index, dtype=object)


_STYLE = """
<style>
.vs-label{font-size:.72rem;font-weight:700;letter-spacing:.08em;color:#64748b;text-transform:uppercase;margin:.9rem 0 .35rem}
.vs-label small{font-weight:500;letter-spacing:0;text-transform:none;margin-left:.5rem;color:#94a3b8}
.vs-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(128px,1fr));gap:.55rem}
.vs-card{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:.55rem .7rem .6rem;border-top:3px solid var(--c,#cbd5e1)}
.vs-card.zero{background:#f8fafc;opacity:.62}
.vs-card .n{font-size:.68rem;color:#64748b;font-weight:600}
.vs-card .t{font-size:.78rem;color:#1e293b;font-weight:600;line-height:1.15;min-height:1.8em}
.vs-card .v{font-size:1.5rem;font-weight:700;color:var(--c,#334155);line-height:1.2}
.vs-card .u{font-size:.66rem;color:#94a3b8;margin-left:.25rem;font-weight:500}
.vs-bar{height:5px;border-radius:3px;background:#e2e8f0;overflow:hidden}
.vs-bar>span{display:block;height:100%;border-radius:3px;background:var(--c,#2563eb)}
.vs-badge{display:inline-block;border-radius:999px;padding:.08rem .6rem;font-size:.78rem;font-weight:600;background:#e0ecff;color:#1d4ed8}
.vs-badge.grey{background:#f1f5f9;color:#64748b}
.vs-panel{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:.8rem 1rem;height:100%}
.vs-panel h4{margin:0 0 .5rem;font-size:.72rem;letter-spacing:.08em;color:#64748b;text-transform:uppercase}
.vs-kv{display:flex;justify-content:space-between;gap:.8rem;font-size:.85rem;padding:.18rem 0;border-bottom:1px dashed #eef2f7}
.vs-kv span:first-child{color:#64748b}
.vs-kv span:last-child{font-weight:600;color:#0f172a;text-align:right}
.vs-tl{position:relative;margin:0;padding:0;list-style:none}
.vs-tl li{position:relative;padding:0 0 .42rem 1.9rem;font-size:.84rem;color:#94a3b8}
.vs-tl li:before{content:"";position:absolute;left:.62rem;top:1.15rem;bottom:-.1rem;width:2px;background:#e2e8f0}
.vs-tl li:last-child:before{display:none}
.vs-tl li .d{position:absolute;left:0;top:0;width:1.3rem;height:1.3rem;border-radius:50%;border:2px solid #cbd5e1;background:#fff;font-size:.7rem;line-height:1.05rem;text-align:center;font-weight:700}
.vs-tl li.done{color:#334155}
.vs-tl li.done .d{background:#20b26b;border-color:#20b26b;color:#fff}
.vs-tl li.done:before{background:#20b26b}
.vs-tl li.current{color:#1d4ed8;font-weight:700}
.vs-tl li.current .d{background:#2563eb;border-color:#2563eb;color:#fff;box-shadow:0 0 0 4px #dbeafe}
.vs-tl li .dt{float:right;font-size:.72rem;font-weight:500;color:#64748b}
.vs-tl.proof li{color:#334155;padding-bottom:.55rem}
.vs-tl.proof li .d{background:#7c3aed;border-color:#7c3aed;color:#fff}
.vs-tl.proof li:before{background:#ddd6fe}
.vs-adv{font-size:.8rem;color:#475569;margin:.2rem 0 .3rem}
.vs-adv b{color:#0f172a}
.vs-title{font-size:1.25rem;font-weight:700;color:#0f172a;margin:0 0 .15rem}
[data-testid="stButtonGroup"] button{border-radius:999px!important;padding:.25rem .85rem!important;font-weight:600!important;border:1px solid #cbd5e1!important;background:#fff!important}
[data-testid="stButtonGroup"] button[aria-checked="true"],[data-testid="stButtonGroup"] button[aria-pressed="true"],[data-testid="stButtonGroup"] button[kind="pillsActive"]{background:#1d4ed8!important;border-color:#1d4ed8!important;box-shadow:0 2px 6px rgba(29,78,216,.35)!important}
[data-testid="stButtonGroup"] button[aria-checked="true"] *,[data-testid="stButtonGroup"] button[aria-pressed="true"] *,[data-testid="stButtonGroup"] button[kind="pillsActive"] *{color:#fff!important}

.vs-stage-grid{grid-template-columns:repeat(5,minmax(0,1fr));gap:18px;margin:12px 0 28px}
.vs-stage-grid .vs-card{min-height:172px;padding:18px 20px;border-radius:12px;border-top-width:2px;display:flex;flex-direction:column;gap:7px;min-width:0;background:linear-gradient(135deg,#fff,#f9fbff)}
.vs-stage-grid .vs-card.zero{opacity:1;background:#f8faff}
.vs-stage-grid .vs-card .n{font-size:12px;font-weight:500;color:#6b80a5}
.vs-stage-grid .vs-card .t{font-size:15px;line-height:1.35;min-height:42px;font-weight:700;color:#102142;overflow-wrap:anywhere}
.vs-stage-grid .vs-card .v{font-size:32px;line-height:1.2;font-weight:800;margin-top:auto}
.vs-stage-grid .vs-card .u{font-size:13px;color:#6c80a3;margin-left:9px}
.vs-stage-grid .vs-bar{height:9px;border-radius:8px;margin-top:2px;background:#e5ebf4}
.vs-stage-grid .vs-bar>span{border-radius:8px}
@media(max-width:1150px){.vs-stage-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}}
@media(max-width:760px){.vs-stage-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.vs-stage-grid .vs-card{padding:14px;min-height:160px}}
@media(max-width:440px){.vs-stage-grid{grid-template-columns:minmax(0,1fr)}}
</style>
"""

_STAGE_COLOR = "#2563eb"
_DONE_COLOR = "#20b26b"
_PROOF_COLOR = "#7c3aed"


def _html(markup: str) -> None:
    st.markdown(markup.replace("\n", ""), unsafe_allow_html=True)


def _label(text: str, note: str = "") -> None:
    suffix = f"<small>{escape(note)}</small>" if note else ""
    _html(f'<div class="vs-label">{escape(text)}{suffix}</div>')


def _render_cards(
    rows: list[tuple[str, int]],
    total: int,
    unit: str,
    *,
    color: str = _STAGE_COLOR,
    numbered: bool = False,
    last_color: str | None = None,
) -> None:
    cards = []
    for position, (label, count) in enumerate(rows, start=1):
        accent = last_color if last_color and position == len(rows) else color
        share = min(count / total, 1.0) * 100 if total else 0
        number = f'<div class="n">Etapa {position}</div>' if numbered else ""
        cards.append(
            f'<div class="vs-card{"" if count else " zero"}" style="--c:{accent}">'
            f"{number}<div class=\"t\">{escape(label)}</div>"
            f'<div class="v">{count}<span class="u">{escape(unit)}</span></div>'
            f'<div class="vs-bar"><span style="width:{share:.0f}%"></span></div>'
            "</div>"
        )
    _html(f'<div class="vs-grid{" vs-stage-grid" if numbered else ""}">{"".join(cards)}</div>')


def _advance(status) -> dict:
    """Posición en la secuencia de etapas de LION; no es un porcentaje."""
    progress = lion_adapter.stage_progress(status)
    timeline = progress["timeline"]
    total = len(timeline)
    current = [item["number"] for item in timeline if item["kind"] == "current"]
    done = [item["number"] for item in timeline if item["kind"] == "done"]
    position = max(current) if current else (max(done) if done else None)
    return {
        "position": position,
        "total": total,
        "text": progress["caption"] if position else "Etapa no determinada",
        "timeline": timeline,
        "states": progress["states"],
    }


def _contrast(color: str) -> str:
    red, green, blue = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return "#1f2937" if (red * 299 + green * 587 + blue * 114) / 1000 > 150 else "#fff"


def _format_day(value: str, with_year: bool) -> str:
    try:
        parsed = datetime.strptime(str(value)[:10], "%Y-%m-%d")
    except ValueError:
        return str(value)
    return parsed.strftime("%d/%m/%Y" if with_year else "%d/%m")


def _history_segments(records: list[dict]) -> list[dict]:
    segments: list[dict] = []
    for record in records:
        if segments and segments[-1]["stages"] == record["stages"]:
            segments[-1]["last"] = record["date"]
            segments[-1]["count"] += 1
        else:
            segments.append(
                {
                    "stages": record["stages"],
                    "first": record["date"],
                    "last": record["date"],
                    "count": 1,
                }
            )
    return segments






def render_commercial_workspace(
    model: pd.DataFrame,
    *,
    details: dict | None = None,
    identity_model: pd.DataFrame | None = None,
    global_query: str = "",
    history: dict | None = None,
    demo: bool = False,
    observation_date: str | None = None,
    show_commercial: bool = False,
) -> None:
    _html(_STYLE)
    if not demo and observation_date:
        shown_date = format_sap_date(observation_date)
        if shown_date != NO_DATE:
            st.caption(f"Datos actualizados a: {shown_date}")
    show_delivered = bool(st.session_state.get("commercial_show_delivered_v9", False))
    _delivered = delivered_mask(model)
    hidden_delivered = int(model.loc[_delivered, "ID"].nunique()) if "ID" in model else int(_delivered.sum())
    if not show_delivered:
        model = model.loc[~_delivered].copy()
    _label("Mis clientes")

    if global_query.strip():
        matching = lion_adapter.search_machines(model, global_query.strip(), "Todo")
    else:
        matching = model.copy()
    matching_ids = set(matching.get("ID", []))
    matching_details = {
        identifier: frame
        for identifier, frame in (details or {}).items()
        if identifier in matching_ids
    }
    clients = client_options(matching, matching_details)
    if not clients:
        show_delivered = st.toggle(
            "Ver entregadas", value=False, key="commercial_show_delivered_v9",
            help="Incluye las máquinas con estado Entregadas. Desactivado: cartera pendiente de entrega.",
        )
        st.info("No hay máquinas pendientes para este ámbito. Activa «Ver entregadas» para consultar las entregadas." if not show_delivered else "No hay clientes disponibles para el ámbito seleccionado.")
        return

    stage_summary_slot = st.container()
    choices = client_choices(matching, matching_details)
    if st.session_state.get("commercial_client") not in (None, *choices):
        st.session_state.pop("commercial_client", None)
    _label("Mis clientes")
    selector, summary = st.columns([3, 3], vertical_alignment="center")
    with selector:
        picked = st.selectbox(
            "Cliente",
            list(choices),
            index=None,
            placeholder="Buscar cliente...",
            label_visibility="collapsed",
            key="commercial_client",
        )
    client = choices[picked][0] if picked else ALL_CLIENTS
    with summary:
        _html(
            '<div class="vs-adv">'
            f"Clientes: <b>{len(choices) - 1}</b> · "
            f"Máquinas: <b>{choices[ALL_CLIENTS][1]}</b> · "
            f"Cliente seleccionado: <b>{escape(client)}</b></div>"
        )
    client_model = (
        lion_adapter.filter_machines(
            matching,
            matching_details,
            filters={"Cliente": client},
        )
        if client != ALL_CLIENTS
        else matching.copy()
    )
    client_ids = set(client_model.get("ID", []))
    client_details = {
        identifier: frame
        for identifier, frame in matching_details.items()
        if identifier in client_ids
    }
    machine_count = (
        client_model["ID"].nunique()
        if "ID" in client_model.columns
        else len(client_model)
    )
    process_counts: dict[str, set[str]] = {}
    stage_order: list[str] = []
    for stage in lion_adapter.stage_progress(None)["timeline"]:
        process_counts[str(stage["label"])] = set()
        stage_order.append(str(stage["label"]))
    for _, row in client_model.iterrows():
        progress = lion_adapter.stage_progress(row.get("Estado"))
        identifier = str(row.get("ID", row.get("Pedido", "")))
        for stage in progress["timeline"]:
            if stage["kind"] == "current":
                process_counts[str(stage["label"])].add(identifier)

    with stage_summary_slot:
        _label(
            "Situación actual · LION",
            f"{machine_count} máquinas · una máquina puede estar en más de una etapa",
        )
        _render_cards(
            [(stage, len(process_counts[stage])) for stage in stage_order],
            machine_count,
            "máq.",
            numbered=True,
            last_color=_DONE_COLOR,
        )
    _label("Mis máquinas")
    show_delivered = st.toggle(
        "Ver entregadas", value=False, key="commercial_show_delivered_v9",
        help="Incluye las máquinas con estado Entregadas. Desactivado: cartera pendiente de entrega.",
    )
    if not show_delivered and hidden_delivered:
        st.caption(f"{hidden_delivered} entregadas ocultas. Activa «Ver entregadas» para consultarlas.")
    bands = urgency_bands(identity_model if identity_model is not None else model)
    client_model = client_model.copy()
    client_model["Fecha de entrega"] = [
        format_sap_dates([value])
        for value in client_model.get(
            "Fecha de entrega (Excel)", pd.Series([""] * len(client_model), index=client_model.index)
        )
    ]
    client_model["Fecha entrega confirmada"] = (
        confirmed_delivery_dates(client_model, details)
    )
    stage_choices = [stage for stage in stage_order if process_counts[stage]]
    urgency_choices = (
        sorted(
            {str(v).strip() for v in client_model["Urgencia"] if _available(v)},
            key=str.casefold,
        )
        if "Urgencia" in client_model.columns
        else []
    )
    if st.session_state.get("commercial_list_stage") not in (None, "Todas las etapas", *stage_choices):
        st.session_state.pop("commercial_list_stage", None)
    if st.session_state.get("commercial_list_urgency") not in (None, "Todas las urgencias", *urgency_choices):
        st.session_state.pop("commercial_list_urgency", None)
    filters = st.columns([3, 2, 2])
    text_filter = filters[0].text_input(
        "Buscar",
        placeholder="Buscar por modelo, referencia o cliente",
        label_visibility="collapsed",
        key="commercial_list_search",
    )
    stage_filter = filters[1].selectbox(
        "Etapa",
        ["Todas las etapas", *stage_choices],
        label_visibility="collapsed",
        key="commercial_list_stage",
    )
    urgency_filter = filters[2].selectbox(
        "Urgencia",
        ["Todas las urgencias", *urgency_choices],
        label_visibility="collapsed",
        key="commercial_list_urgency",
        disabled=not urgency_choices,
    )
    if bands:
        _html(
            '<div class="vs-adv" style="margin:.2rem 0 .4rem">Urgencia operacional '
            f"(días): {urgency_legend(bands)}<br>El color depende solo del valor "
            "mostrado, con límites inferiores inclusivos.</div>"
        )
    if text_filter.strip():
        client_model = lion_adapter.search_machines(
            client_model, text_filter.strip(), "Todo"
        )
    if stage_filter != "Todas las etapas":
        client_model = client_model[
            client_model["ID"].astype(str).isin(process_counts[stage_filter])
        ]
    if urgency_filter != "Todas las urgencias":
        client_model = client_model[
            client_model["Urgencia"].astype(str).str.strip() == urgency_filter
        ]
    client_model = sort_by_urgency(client_model).reset_index(drop=True)

    candidate_columns = (
        "Máquina",
        "Pedido",
        "Cliente",
        *(("Comercial",) if show_commercial else ()),
        "Estado",
        "Avance",
        "Oficina de ventas",
        "Urgencia",
        "Fecha de entrega",
        "Fecha entrega confirmada",
    )
    advances = [_advance(status) for status in client_model.get("Estado", [])]
    client_model["Avance"] = [item["position"] for item in advances]
    total_stages = advances[0]["total"] if advances else len(stage_order)
    visible_columns = [
        column
        for column in candidate_columns
        if column in client_model.columns
        and client_model[column].map(_available).any()
    ]
    display_model = client_model[visible_columns].rename(
        columns={
            "Máquina": "Modelo",
            "Pedido": "Referencia / pedido",
            "Estado": "Etapa actual",
            "Avance": "Avance del proceso",
            "Oficina de ventas": "Área responsable",
            "Urgencia": "Urgencia operacional",
        }
    )
    from vision import comments

    comment_counts = comments.counts_for(client_model)
    if comment_counts.any():
        display_model["Comentarios"] = comment_counts.map(comments.format_count)
    if client_model.empty:
        st.info("No hay máquinas para los filtros seleccionados.")
        return

    def urgency_style(column: pd.Series) -> list[str]:
        styles = []
        for index in column.index:
            color = urgency_color(column[index], bands)
            if color:
                styles.append(
                    f"background-color:{color};color:{_contrast(str(color))};"
                    "font-weight:600;text-align:center"
                )
            else:
                styles.append("")
        return styles

    styled = display_model.style
    if "Urgencia operacional" in display_model.columns:
        styled = styled.apply(urgency_style, subset=["Urgencia operacional"])
    if "Etapa actual" in display_model.columns:
        styled = styled.map(
            lambda _: "background-color:#e0ecff;color:#1d4ed8;font-weight:600",
            subset=["Etapa actual"],
        )
    if "Modelo" in display_model.columns:
        styled = styled.map(lambda _: "font-weight:700", subset=["Modelo"])
    column_config = {}
    if "Avance del proceso" in display_model.columns:
        column_config["Avance del proceso"] = st.column_config.ProgressColumn(
            "Avance del proceso",
            min_value=0,
            max_value=total_stages,
            format=f"Etapa %d de {total_stages}",
        )
    event = st.dataframe(
        styled,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config=column_config,
        key=f"commercial_machines_urgency_v9_{show_delivered}_{len(client_model)}_{client}",
        alt="Máquinas de la cartera comercial seleccionada",
    )
    selected_rows = event.selection.rows
    if not selected_rows or selected_rows[0] >= len(client_model):
        st.caption("Selecciona una máquina de la lista para abrir su detalle.")
        return
    selected = client_model.iloc[selected_rows[0]]
    render_machine_sheet(selected, client_model, model, identity_model, history, bands)


def with_delivery_dates(model: pd.DataFrame, details: dict | None) -> pd.DataFrame:
    """Añade las columnas de fecha de entrega y entrega confirmada de SAP/LION."""
    result = model.copy()
    result["Fecha de entrega"] = [
        format_sap_dates([value])
        for value in result.get(
            "Fecha de entrega (Excel)", pd.Series([""] * len(result), index=result.index)
        )
    ]
    result["Fecha entrega confirmada"] = confirmed_delivery_dates(result, details)
    return result


def render_machine_sheet(
    selected, client_model, model, identity_model, history, bands
) -> None:
    """Ficha de máquina compartida por Comercial, Manager y O2C."""
    selected_id = selected["ID"]

    def machine_label(identifier):
        row = client_model.loc[client_model["ID"] == identifier].iloc[0]
        values = [
            str(row[column]).strip()
            for column in ("Máquina", "Pedido", "Número de serie")
            if column in row.index and _available(row[column])
        ]
        return " · ".join(values) or "Máquina sin descripción disponible"

    def kv(label: str, value, *, raw: bool = False) -> str:
        shown = value if raw else escape(str(value))
        return f'<div class="vs-kv"><span>{escape(label)}</span><span>{shown}</span></div>'

    def field_value(field: str) -> str:
        return (
            str(selected[field])
            if field in selected.index and _available(selected[field])
            else "No disponible"
        )

    _label("Ficha de máquina")
    advance = _advance(selected.get("Estado"))
    stage_label = " · ".join(advance["states"]) or "No disponible"
    share = (advance["position"] or 0) / advance["total"] * 100
    urgency = field_value("Urgencia")
    urgency_tone = urgency_color(selected.get("Urgencia"), bands)
    urgency_html = (
        f'<span class="vs-badge" style="background:{urgency_tone};'
        f'color:{_contrast(urgency_tone)}">{escape(urgency)}</span>'
        if urgency_tone and urgency != "No disponible"
        else '<span class="vs-badge grey">No disponible</span>'
    )
    _html(f'<div class="vs-title">{escape(machine_label(selected_id))}</div>')
    left, steps, notes = st.columns([1, 1, 1.15])
    with left:
        identity = st.container()
        situation = st.container()
    with identity:
        _html(
            '<div class="vs-panel"><h4>Identificación</h4>'
            + kv("Cliente", field_value("Cliente"))
            + kv("Documento de ventas", field_value("Pedido"))
            + kv("Documento de compras", field_value("Documento de compras"))
            + kv("Número de serie / chasis", field_value("Número de serie"))
            + "</div>"
        )
    with situation:
        rows = (
            kv("Etapa actual", f'<span class="vs-badge">{escape(stage_label)}</span>', raw=True)
            + kv("Urgencia operacional", urgency_html, raw=True)
        )
        for label, field in (
            ("Área responsable", "Oficina de ventas"),
            ("Fecha de entrega", "Fecha de entrega"),
            ("Fecha entrega confirmada", "Fecha entrega confirmada"),
        ):
            if (
                field in selected.index
                and _available(selected[field])
                and selected[field] != NO_DATE
            ):
                rows += kv(label, selected[field])
        rows += kv(
            "Prioridad comercial",
            '<span class="vs-badge grey">Pendiente · no configurada</span>',
            raw=True,
        )
        _html(
            '<div class="vs-panel"><h4>Situación actual · LION</h4>'
            + rows
            + f'<div class="vs-adv" style="margin-top:.6rem">Avance del proceso: '
            f"<b>{escape(advance['text'])}</b> · posición en la secuencia, no un "
            "porcentaje de fabricación</div>"
            f'<div class="vs-bar"><span style="width:{share:.0f}%"></span></div></div>'
        )
    with steps:
        items = []
        for stage in advance["timeline"]:
            mark = {"done": "✓", "current": "●", "future": "○"}[stage["kind"]]
            items.append(
                f'<li class="{stage["kind"]}"><span class="d">{mark}</span>'
                f'{stage["number"]}. {escape(str(stage["label"]))}</li>'
            )
        _html(
            '<div class="vs-panel"><h4>Progresión del proceso</h4>'
            f'<ul class="vs-tl">{"".join(items)}</ul></div>'
        )

    with notes:
        with st.container(border=True):
            render_comments(selected)
    _render_proof_history(selected, model, identity_model, history)


def render_comments(selected) -> None:
    """Comentarios y notas compartidos por máquina entre todos los perfiles."""
    from vision import comments, role_selection

    _label("Comentarios y notas", "compartidos entre perfiles")
    machine = comments.identity_of(selected)
    if machine is None:
        st.info("Esta máquina no tiene documento de ventas: no se pueden asociar comentarios.")
        return
    author = role_selection.current_author()
    box_key = f"comment_box::{selected['ID']}"
    error_key = f"comment_error::{selected['ID']}"

    def send() -> None:
        try:
            comments.add_comment(
                machine,
                author=author[0],
                role=author[1],
                body=st.session_state.get(box_key, ""),
            )
        except ValueError as problem:
            st.session_state[error_key] = str(problem)
        else:
            st.session_state[box_key] = ""
            st.session_state.pop(error_key, None)

    if author is None:
        st.caption("Selecciona un perfil para poder escribir comentarios.")
    else:
        st.text_area(
            "Añadir comentario",
            key=box_key,
            max_chars=comments.MAX_LENGTH,
            placeholder="Escribe una nota visible para todos los perfiles",
            height=90,
        )
        st.button("Enviar", key=f"comment_send::{selected['ID']}", type="primary", on_click=send)
        if st.session_state.get(error_key):
            st.warning(st.session_state[error_key])
        st.caption(
            f"Se publicará como «{author[0]} ({author[1]})», el contexto seleccionado; "
            "no es una identidad autenticada."
        )
    existing = comments.comments_for(machine)
    if not existing:
        st.caption("Todavía no hay comentarios para esta máquina.")
    for item in existing:
        initials = "".join(part[0] for part in item["author"].split()[:2]).upper() or "?"
        stamp = datetime.strptime(item["created_at"], "%Y-%m-%d %H:%M:%S").strftime(
            "%d/%m/%Y %H:%M"
        )
        _html(
            '<div class="vs-cm"><div class="av">'
            f'{escape(initials)}</div><div><div class="hd"><b>{escape(item["author"])}</b> '
            f'({escape(item["role"])}) · {stamp}</div>'
            f'<div class="tx">{escape(item["body"])}</div></div></div>'
        )


def _render_proof_history(selected, model, identity_model, history) -> None:
    with st.container():
        if True:
            sales_document = selected.get("Pedido")
            if _available(sales_document) and history is not None:
                link = resolve_proof_order_link(
                    identity_model if identity_model is not None else model,
                    selected,
                    history,
                )
                observations = link["observations"]
                detail = (
                    st.expander("Ver detalle completo de observaciones")
                    if observations or link["events"] or link["instances"]
                    else None
                )
                if not link["linked"]:
                    st.info(link["reason"])
                if observations:
                    stage_names = {
                        str(source["id"]): str(source["name"])
                        for source in history.get("sources", [])
                    }
                    records = []
                    for observation in observations:
                        names = list(
                            dict.fromkeys(
                                stage_names.get(
                                    str(membership.get("stage")),
                                    "No disponible",
                                )
                                for membership in observation["memberships"]
                                if str(membership.get("machine", "")).strip()
                                == str(sales_document).strip()
                            )
                        )
                        records.append(
                            {
                                "Fecha": observation["observed_date"],
                                "Etapas registradas": " · ".join(names)
                                or "No disponible",
                                "stages": tuple(names),
                            }
                        )
                    with_year = (
                        len({str(item["Fecha"])[:4] for item in records}) > 1
                    )
                    steps_html = []
                    for segment in _history_segments(
                        [
                            {"date": item["Fecha"], "stages": item["stages"]}
                            for item in records
                        ]
                    ):
                        first = _format_day(segment["first"], with_year)
                        span = (
                            first
                            if segment["count"] == 1
                            else f"{first} → "
                            f"{_format_day(segment['last'], with_year)}"
                        )
                        note = (
                            ""
                            if segment["count"] == 1
                            else f" · {segment['count']} observaciones iguales"
                        )
                        steps_html.append(
                            '<li><span class="d">●</span>'
                            f"<b>{escape(span)}</b>&nbsp; "
                            f"{escape(' · '.join(segment['stages']) or 'No disponible')}"
                            f'<span class="dt">{escape(note)}</span></li>'
                        )
                    _html(
                        '<div class="vs-panel"><ul class="vs-tl proof">'
                        + "".join(steps_html)
                        + "</ul></div>"
                    )
                    detail.dataframe(
                        [
                            {key: value for key, value in item.items() if key != "stages"}
                            for item in records
                        ],
                        hide_index=True,
                        alt="Etapas observadas anteriormente para este pedido",
                    )
                    st.caption(
                        "El historial se conserva por pedido; no identifica por sí "
                        "solo una máquina física. Observaciones consecutivas iguales "
                        "se agrupan solo en esta vista."
                    )
                if link["events"]:
                    detail.dataframe(
                        [
                            {
                                "Fecha": event.get("observed_date"),
                                "Etapa": event.get("stage_name")
                                or event.get("stage")
                                or "No disponible",
                                "Evento": {
                                    "A": "Apertura registrada",
                                    "C": "Cierre registrado",
                                }.get(event.get("type"), event.get("type")),
                                "Estado": event.get("status"),
                            }
                            for event in link["events"]
                        ],
                        hide_index=True,
                        alt="Eventos PROOF asociados al pedido seleccionado",
                    )
                if link["instances"]:
                    detail.dataframe(
                        [
                            {
                                "Etapa": instance.get("stage_name")
                                or instance.get("stage"),
                                "Apertura": instance.get("opening_date"),
                                "Cierre": instance.get("closure_date"),
                                "Estado": instance.get("status"),
                                "Días laborables": instance.get("elapsed"),
                            }
                            for instance in link["instances"]
                        ],
                        hide_index=True,
                        alt="Instancias PROOF asociadas al pedido seleccionado",
                    )
            else:
                st.info("No hay historial disponible para este pedido.")
