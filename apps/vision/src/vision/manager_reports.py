"""Informes PROOF del Manager Comercial.

VISION solo acota los Documentos de ventas del ámbito (delegación y, opcionalmente,
comercial) y visualiza los resultados de los servicios públicos de PROOF.
"""

from __future__ import annotations

from datetime import date
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

import proof

GREEN, VIOLET, RED = "#16a34a", "#7c3aed", "#dc2626"
GRAINS = ("Día", "Semana", "Mes")

_STYLE = """
<style>
.mr-card{border:1px solid #e5e7eb;border-radius:12px;padding:.7rem .8rem;background:#fff;
height:100%}
.mr-card .n{font-size:.72rem;color:#6b7280}
.mr-card .t{font-weight:700;font-size:.9rem;margin:.1rem 0 .35rem}
.mr-card .v{font-size:1.6rem;font-weight:800;line-height:1.1}
.mr-card .v small{font-size:.72rem;font-weight:500;color:#6b7280}
.mr-card .u{font-size:.74rem;color:#6b7280}
.mr-card .k{font-size:.64rem;letter-spacing:.06em;color:#6b7280;font-weight:700;margin-top:.55rem}
.mr-card .kv{font-size:1rem;font-weight:700}
.mr-card .v{margin-top:.1rem}
.mr-leg>div{white-space:nowrap}
.mr-key{font-size:.78rem;color:#374151;display:flex;gap:1rem;flex-wrap:wrap;margin:.2rem 0 .6rem}
.mr-key i{display:inline-block;width:.6rem;height:.6rem;border-radius:50%;margin-right:.3rem}
.mr-bar{display:flex;height:.5rem;border-radius:4px;overflow:hidden;background:#eef0f3;
margin:.45rem 0 .25rem}
.mr-leg{font-size:.74rem;color:#374151;display:flex;flex-direction:column;gap:.1rem}
.mr-leg i{display:inline-block;width:.6rem;height:.6rem;border-radius:50%;margin-right:.2rem}
.mr-card.final{background:#f8fafc;border-style:dashed}
</style>
"""


def scope_documents(model: pd.DataFrame) -> list[str]:
    """Documentos de ventas (Pedido LION) de las máquinas del ámbito actual."""
    if "Pedido" not in model.columns:
        return []
    values = {
        str(value).strip()
        for value in model["Pedido"]
        if value is not None and not pd.isna(value) and str(value).strip()
    }
    return sorted(values)


def scoped_history(history: dict, documents: list[str]) -> dict:
    return proof.filter_history(history, documents)


def stage_cards(summary: dict) -> list[dict]:
    """Etapas 1–9 tal como las calcula PROOF; la etapa terminal queda fuera."""
    return [row for row in summary["stage_rows"] if not row["terminal"]]


def inventory_frame(history_view: dict, grain: str, start: str, end: str) -> pd.DataFrame:
    rows, _ = proof.project_inventory(
        history_view["instances"],
        history_view["dates"],
        history_view["sources"],
        grain,
        start,
        end,
    )
    return pd.DataFrame(rows)


def _stage_card(row: dict) -> str:
    before, around, over = row["before_target"], row["around_target"], row["over_target"]
    total = before + around + over
    parts = [
        (GREEN, before, "Antes del objetivo"),
        (VIOLET, around, "En torno al objetivo"),
        (RED, over, "Fuera de plazo"),
    ]
    bar = "".join(
        f'<span style="width:{count / total * 100:.1f}%;background:{color}"></span>'
        for color, count, _ in parts
        if total and count
    )
    legend = "".join(
        f'<div><i style="background:{color}"></i><b>{count}</b> {label}</div>'
        for color, count, label in parts
    )
    unclassified = row["documents"] - total
    if unclassified > 0:
        legend += (
            f'<div><i style="background:#9ca3af"></i><b>{unclassified}</b> '
            "Sin consumo calculable</div>"
        )
    average = row["average_consumption"]
    consumption = (
        f"{average:.0f} % del objetivo" if average is not None else "Sin dato"
    )
    target = (
        f"Objetivo: {row['target']} días laborables"
        if row.get("target")
        else "Sin objetivo definido"
    )
    return (
        '<div class="mr-card">'
        f'<div class="n">ETAPA {escape(str(row["id"]))}</div>'
        f'<div class="t">{escape(str(row["name"]))}</div>'
        f'<div class="v">{row["documents"]}</div>'
        '<div class="u">expedientes activos</div>'
        '<div class="k">CONSUMO MEDIO</div>'
        f'<div class="kv">{escape(consumption)}</div>'
        f'<div class="u">{escape(target)}</div>'
        '<div class="k">DISTRIBUCIÓN</div>'
        f'<div class="mr-bar">{bar}</div><div class="mr-leg">{legend}</div>'
        "</div>"
    )


def _final_card(row: dict | None, completion: dict | None) -> str:
    name = escape(str(row["name"])) if row else "Entregada a cliente"
    number = escape(str(row["id"])) if row else "10"
    if completion is None:
        value, note = "—", "No disponible"
    else:
        value = str(completion["completed_count"])
        note = (
            f"{completion['baseline_completed_count']} ya finalizadas en la primera "
            f"observación ({completion.get('baseline_date') or '—'}) · "
            f"{completion['registered_completed_count']} cierres registrados después"
        )
    return (
        '<div class="mr-card final">'
        f'<div class="n">ETAPA {number} · TERMINAL</div>'
        f'<div class="t">{name}</div>'
        f'<div class="v">{value}</div>'
        '<div class="u">entregas acumuladas</div>'
        '<div class="k">DETALLE</div>'
        f'<div class="u">{escape(note)}</div>'
        '<div class="u">Métrica independiente: no se suma a los expedientes activos.</div>'
        "</div>"
    )


def _show_all(options: list[str]) -> None:
    st.session_state["mgr_report_stages"] = list(options)


def _report_bucket(history, documents, history_token=None):
    """Cache de sesion acotada por version del historico y documentos del ambito."""
    token = tuple(history_token) if history_token is not None else ("object", id(history))
    key = (token, tuple(sorted(set(documents))))
    cache = st.session_state.setdefault("_vision_manager_report_cache_v6", {})
    if key not in cache:
        # Solo se guardan resultados correctos; una excepcion permite reintentar.
        view = scoped_history(history, list(key[1]))
        cache[key] = {"view": view, "frames": {}}
        while len(cache) > 4:
            del cache[next(iter(cache))]
    return cache[key]


def _report_frame(bucket, grain, start, end):
    key = (grain, start, end)
    frames = bucket["frames"]
    if key not in frames:
        frames[key] = inventory_frame(bucket["view"], grain, start, end)
        while len(frames) > 8:
            del frames[next(iter(frames))]
    return frames[key]


def _report_summary(bucket):
    if "summary" not in bucket:
        bucket["summary"] = proof.operational_summary(bucket["view"])
    return bucket["summary"]


def _report_completion(bucket, documents, load_completion):
    if "completion" not in bucket:
        bucket["completion"] = load_completion(tuple(sorted(set(documents))))
    return bucket["completion"]


def render_manager_reports(
    history: dict | None,
    documents: list[str],
    *,
    load_completion,
    history_token=None,
) -> None:
    """Pinta los dos informes PROOF para los Documentos de ventas del ámbito."""
    st.markdown(_STYLE, unsafe_allow_html=True)
    st.markdown("### Informes PROOF")
    if history is None:
        st.info("El historial PROOF no está disponible en este momento.")
        return
    if not documents:
        st.info("No hay Documentos de ventas en este ámbito: no se muestran informes.")
        return
    bucket = _report_bucket(history, documents, history_token)
    view = bucket["view"]
    st.caption(
        f"Ámbito: {len(documents):,} Documentos de ventas de LION. PROOF registra el "
        "histórico por Documento de ventas; los conteos son por pedido, no por máquina."
    )

    st.markdown("#### 1. Evolución del inventario por proceso")
    if not (view["dates"] and view["sources"]):
        st.info("PROOF no tiene observaciones para mostrar.")
    else:
        first, last = date.fromisoformat(view["dates"][0]), date.fromisoformat(view["dates"][-1])
        columns = st.columns(3)
        start = columns[0].date_input(
            "Desde", value=first, min_value=first, max_value=last,
            format="DD/MM/YYYY", key="mgr_report_start",
        )
        end = columns[1].date_input(
            "Hasta", value=last, min_value=first, max_value=last,
            format="DD/MM/YYYY", key="mgr_report_end",
        )
        grain = columns[2].selectbox("Agrupar por", GRAINS, key="mgr_report_grain")
        if start > end:
            st.error("La fecha inicial debe ser anterior a la final.")
        else:
            frame = _report_frame(bucket, grain, start.isoformat(), end.isoformat())
            if frame.empty:
                st.info("No hay observaciones en el periodo seleccionado.")
            else:
                options = list(dict.fromkeys(frame["Etapa"]))
                st.session_state.setdefault("mgr_report_stages", list(options))
                st.session_state["mgr_report_stages"] = [
                    item for item in st.session_state["mgr_report_stages"] if item in options
                ]
                pick, reset = st.columns([5, 1], vertical_alignment="bottom")
                chosen = pick.multiselect("Procesos visibles", options, key="mgr_report_stages")
                reset.button(
                    "Mostrar todos los procesos",
                    key="mgr_report_all",
                    on_click=_show_all,
                    args=(options,),
                )
                shown = frame[frame["Etapa"].isin(chosen)]
                if shown.empty:
                    st.info("Selecciona al menos un proceso.")
                else:
                    chart = (
                        alt.Chart(shown)
                        .mark_line(point=True)
                        .encode(
                            x=alt.X("Periodo:O", title="Periodo"),
                            y=alt.Y(
                                "Expedientes pendientes:Q",
                                title="Expedientes pendientes al cierre observado",
                            ),
                            color=alt.Color("Etapa:N", title="Proceso", sort=options),
                            tooltip=["Periodo", "Etapa", "Expedientes pendientes"],
                        )
                        .properties(height=360)
                    )
                    st.altair_chart(chart, width="stretch")
                st.caption(
                    "La primera observación se incluye como inventario inicial. Semana y "
                    "mes usan el último estado observado de cada periodo, no la suma de "
                    "sus días. Los días sin archivo no se inventan como cero. Los "
                    "recuentos son documentos de ventas únicos por proceso y pueden "
                    "coincidir entre procesos simultáneos. La etapa terminal no se "
                    "incluye en este gráfico."
                )

    st.markdown("#### 2. Proceso de 10 estadios")
    if not view["sources"]:
        st.info("PROOF no tiene etapas estándar configuradas.")
        return
    summary = _report_summary(bucket)
    cards = stage_cards(summary)
    terminal = next((row for row in summary["stage_rows"] if row["terminal"]), None)
    scope_key = tuple(documents)
    st.markdown(
        '<div class="mr-key"><b>Cumplimiento del objetivo</b>'
        f'<span><i style="background:{GREEN}"></i>Antes del objetivo</span>'
        f'<span><i style="background:{VIOLET}"></i>En torno al objetivo</span>'
        f'<span><i style="background:{RED}"></i>Fuera de plazo</span></div>',
        unsafe_allow_html=True,
    )
    columns = st.columns(5)
    for index, row in enumerate(cards):
        with columns[index % 5]:
            st.markdown(_stage_card(row), unsafe_allow_html=True)
    completion = None
    with st.spinner("Consultando entregas acumuladas en PROOF (solo lectura)…"):
        try:
            completion = _report_completion(bucket, scope_key, load_completion)
        except Exception:
            st.warning("No se pudieron consultar las entregas acumuladas de PROOF.")
    with columns[len(cards) % 5]:
        st.markdown(_final_card(terminal, completion), unsafe_allow_html=True)
    st.caption(
        "Etapas 1–9: expedientes activos según PROOF. Consumo medio: media del consumo "
        "del objetivo temporal calculado por PROOF (días laborables en la etapa respecto "
        "al objetivo). Antes < 80 %, en torno 80–120 %, fuera de plazo > 120 %. "
        "Etapa 10: entregas acumuladas de todo el histórico PROOF del ámbito; no depende "
        "de Desde/Hasta y no se suma a los activos."
    )
