"""Resumen O2C: presentación de pertenencias LION, sin inferir eventos históricos."""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timedelta
from html import escape
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
import streamlit as st
import proof
from vision.commercial_workspace import urgency_color

STYLE = """
<style>
.o7-summary{display:grid;grid-template-columns:1.25fr 1fr 1fr;gap:22px;background:white;border:1px solid #dce6f5;border-radius:15px;padding:22px;margin:16px 0 22px;box-shadow:0 4px 18px #153e7005;color:#102142}
.o7-block{min-width:0}.o7-block+.o7-block{border-left:1px solid #e6edf8;padding-left:22px}
.o7-title{font-size:15px;font-weight:750;margin-bottom:14px;line-height:1.4;overflow-wrap:anywhere}
.o7-sub{font-size:12px;color:#7083a1;line-height:1.5;margin:8px 0}
.o7-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.o7-kpi{border:1px solid #e4ebf7;background:#f7faff;border-radius:10px;padding:14px 12px;min-height:142px}
.o7-kpi.in{background:#f4fbf7}.o7-kpi.out{background:#fffaf0}
.o7-icon{font-size:23px;color:#1d4ed8;margin-bottom:8px}.o7-kpi.in .o7-icon{color:#16a36b}.o7-kpi.out .o7-icon{color:#d49a00}
.o7-kpi-label{font-size:12px;line-height:1.45;min-height:38px}.o7-value{font-size:34px;font-weight:800;line-height:1.2;margin-top:9px}
.o7-value.na{font-size:24px;color:#7b8ba5}.o7-na{font-size:11px;color:#7888a2;line-height:1.4;margin-top:5px}
.o7-urgencies{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px}
.o7-urgency{border:1px solid #e6ebf4;border-top:3px solid var(--band);border-radius:9px;padding:10px 7px;background:#fbfcff;min-width:0;text-align:center}
.o7-range{font-size:11px;min-height:32px;line-height:1.4;overflow-wrap:anywhere;color:#4d6384}.o7-urgency strong{font-size:26px;display:block;margin:9px 0}.o7-pct{font-size:12px;color:#647b9e}
.o7-area{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(40px,1fr) 35px 42px;align-items:center;gap:8px;margin:10px 0;font-size:12px}
.o7-area-name{overflow-wrap:anywhere}.o7-track{height:8px;border-radius:6px;background:#eaf0f8;overflow:hidden}.o7-fill{height:100%;background:#2c64ee;border-radius:6px}.o7-area b{text-align:right}.o7-area small{text-align:right;color:#7d8eaa}
.o7-footer{font-size:12px;color:#7083a1;margin-top:10px;line-height:1.5}
.st-key-o2c_process_navigation button{min-height:85px;white-space:normal;border-radius:11px;line-height:1.4;text-align:left}
.st-key-o2c_process_navigation button[kind="primary"]{background:#1557ef;color:white;border-color:#1557ef;box-shadow:0 4px 10px #1557ef20}
.st-key-o2c_process_navigation button:focus-visible{outline:3px solid #82b0ff;outline-offset:3px}
@media(max-width:1250px){.o7-summary{grid-template-columns:1fr 1fr}.o7-block:last-child{grid-column:1/-1;border-left:0;border-top:1px solid #e6edf8;padding:18px 0 0}}
@media(max-width:800px){.o7-summary{grid-template-columns:1fr;padding:16px}.o7-block+.o7-block{border-left:0;border-top:1px solid #e6edf8;padding:16px 0 0}.o7-block:last-child{grid-column:auto}.o7-urgencies{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:450px){.o7-kpis{grid-template-columns:1fr}.o7-kpi{min-height:0}.o7-kpi-label{min-height:0}.o7-urgencies{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _text(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (ValueError, TypeError):
        return ""
    return str(value).strip()


def summary_metrics(scope, bands):
    """Un ID LION cuenta una vez. No fusiona pedidos ni fabrica identidades."""
    if "ID" not in scope.columns:
        return dict(total=0, urgencies=[], areas=[], missing_ids=len(scope),
                    conflict_urgency=0, missing_urgency=0, multiple_areas=0)
    valid = scope.loc[scope["ID"].map(lambda value: bool(_text(value))).astype(bool)]
    groups = valid.groupby("ID", sort=False, dropna=False)
    total = groups.ngroups
    colors, areas = Counter(), Counter()
    missing_urgency = conflict_urgency = multiple_areas = 0
    for _, records in groups:
        values = records["Urgencia"] if "Urgencia" in records else [None]
        categories = {urgency_color(value, bands) for value in values}
        if len(categories) > 1:
            conflict_urgency += 1
        elif not categories or next(iter(categories)) is None:
            missing_urgency += 1
        else:
            colors[next(iter(categories))] += 1
        values = records["Oficina de ventas"] if "Oficina de ventas" in records else []
        assigned = {_text(value) for value in values if _text(value)}
        if len(assigned) > 1:
            areas["Varias delegaciones / áreas"] += 1
            multiple_areas += 1
        else:
            areas[next(iter(assigned)) if assigned else "Sin delegación / área"] += 1
    urgency_rows = []
    for index, (lower, color) in enumerate(bands):
        upper = bands[index + 1][0] - 1 if index + 1 < len(bands) else None
        if index == 0 and upper is not None:
            label = f"≤ {upper} días"
        elif upper is None:
            label = f"≥ {lower} días"
        else:
            label = f"{lower}–{upper} días" if upper > lower else f"{lower} días"
        count = colors[color]
        urgency_rows.append(dict(label=label, color=color, count=count,
                                 percentage=100 * count / total if total else 0))
    area_rows = [dict(name=name, count=count, percentage=100 * count / total if total else 0)
                 for name, count in sorted(areas.items(), key=lambda item: (-item[1], item[0].casefold()))]
    return dict(total=total, urgencies=urgency_rows, areas=area_rows,
                missing_ids=len(scope)-len(valid), conflict_urgency=conflict_urgency,
                missing_urgency=missing_urgency, multiple_areas=multiple_areas)


def business_calendar(now=None, timezone_name=None):
    name = timezone_name or os.environ.get("CO_VISION_TIMEZONE", "Europe/Madrid")
    try:
        zone = ZoneInfo(name)
        instant = datetime.now(zone) if now is None else now
        if instant.tzinfo is None:
            raise ValueError("El instante debe incluir zona horaria.")
        today = instant.astimezone(zone).date()
        return dict(timezone=name, today=today, yesterday=today-timedelta(days=1), error=None)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        return dict(timezone=name, today=None, yesterday=None, error=type(exc).__name__)


def _area_html(row):
    name = escape(row["name"])
    return ('<div class="o7-area"><span class="o7-area-name">' + name +
            '</span><div class="o7-track" aria-hidden="true"><div class="o7-fill" style="width:' +
            f'{row["percentage"]:.2f}' + '%"></div></div><b>' + str(row["count"]) +
            '</b><small>' + f'{row["percentage"]:.1f}' + '%</small></div>')


def render_operational_summary(scope, bands, active, *, history=None, stage_ids=None):
    metrics = summary_metrics(scope, bands)
    calendar = business_calendar()
    today = calendar["today"].strftime("%d/%m/%Y") if calendar["today"] else "fecha no disponible"
    yesterday = calendar["yesterday"].strftime("%d/%m/%Y") if calendar["yesterday"] else "fecha no disponible"
    movements = None
    if history is not None and stage_ids and calendar["today"]:
        cached = st.session_state.get("_o2c_proof_movement_index_v9")
        if cached is None or cached[0] is not history:
            cached = (history, proof.movement_index(history))
            st.session_state["_o2c_proof_movement_index_v9"] = cached
        movements = proof.daily_stage_movements(history, stage_ids, calendar["today"], index=cached[1])
    def movement_card(kind, title, shown_day, record, field):
        value = record[field] if record is not None else None
        status = record["status"] if record is not None else "unavailable"
        note = {
            "missing_observation": "Sin observación para esta fecha",
            "initial_inventory": "Inventario inicial; no es movimiento nuevo",
            "events_unavailable": "Eventos derivados no disponibles",
            "unavailable": "Histórico o correspondencia de etapa no disponible",
        }.get(status, "Pedidos únicos · eventos PROOF")
        warnings = " · ".join(record.get("warnings", [])) if record else note
        if record and record.get("interval_days") not in (None, 1):
            note = "Intervalo observado desde " + str(record["previous_observation"])
        arrow = "↓" if kind == "in" else "↑"
        return ('<div class="o7-kpi ' + kind + '" title="' + escape(warnings or note, quote=True) + '">'
                '<div class="o7-icon" aria-hidden="true">' + arrow + '</div>'
                '<div class="o7-kpi-label">' + escape(title) + '<br>' + shown_day + '</div>'
                '<div class="o7-value' + (' na' if value is None else '') + '">' +
                ("N/D" if value is None else str(value)) + '</div><div class="o7-na">' + escape(note) + '</div></div>')
    kpis = (
        '<div class="o7-kpi"><div class="o7-icon" aria-hidden="true">▱</div>'
        '<div class="o7-kpi-label">Total de máquinas<br>en el proceso</div>'
        f'<div class="o7-value">{metrics["total"]}</div></div>'
        + movement_card("in", "Entradas observadas hoy · pedidos", today,
                        movements["today"] if movements else None, "entered")
        + movement_card("out", "Salidas observadas hoy · pedidos", today,
                        movements["today"] if movements else None, "exited")
    )
    urgencies = "".join(
        '<div class="o7-urgency" style="--band:' + escape(str(row["color"]), quote=True) +
        '" title="Banda operacional existente de LION. No es avance del proceso.">'
        '<div class="o7-range">' + escape(row["label"]) + '</div><strong>' + str(row["count"]) +
        '</strong><span class="o7-pct">' + f'{row["percentage"]:.1f}' + '%</span></div>'
        for row in metrics["urgencies"]
    )
    if not urgencies:
        urgencies = '<div class="o7-sub">Bandas de urgencia no disponibles en la fuente actual.</div>'
    exceptions = []
    if metrics["missing_urgency"]:
        exceptions.append(f'Sin urgencia: {metrics["missing_urgency"]}')
    if metrics["conflict_urgency"]:
        exceptions.append(f'Valores de urgencia contradictorios: {metrics["conflict_urgency"]}')
    areas = "".join(_area_html(row) for row in metrics["areas"][:5])
    remaining = metrics["areas"][5:]
    if remaining:
        count = sum(row["count"] for row in remaining)
        areas += _area_html(dict(name=f'Otras ({len(remaining)})', count=count,
                                 percentage=100*count/metrics["total"] if metrics["total"] else 0))
    if not areas:
        areas = '<div class="o7-sub">No hay máquinas en el ámbito seleccionado.</div>'
    st.markdown(STYLE, unsafe_allow_html=True)
    st.markdown(
        '<div class="o7-summary"><section class="o7-block"><div class="o7-title">Resumen de la operación: ' +
        escape(str(active)) + '</div><div class="o7-kpis">' + kpis +
        '</div><div class="o7-sub">Ámbito: etapa(s) seleccionada(s), antes de los filtros de la tabla. '
        'Conteo por ID LION único; no por filas SAP.</div></section>'
        '<section class="o7-block"><div class="o7-title">Máquinas por urgencia operativa</div>'
        '<div class="o7-urgencies">' + urgencies + '</div><div class="o7-sub">' +
        escape(" · ".join(exceptions)) + '</div></section>'
        '<section class="o7-block"><div class="o7-title">Máquinas por delegación / área</div>' +
        areas + '<div class="o7-sub">Incluye máquinas sin delegación y con varias áreas identificadas.</div>'
        '</section></div>', unsafe_allow_html=True,
    )
    if remaining:
        with st.expander("Ver todas las delegaciones / áreas", expanded=False):
            st.dataframe(pd.DataFrame(metrics["areas"]).rename(columns={
                "name":"Delegación / área", "count":"Máquinas", "percentage":"Porcentaje (%)"
            }), hide_index=True, width="stretch")
    if calendar["error"]:
        st.warning("No se pudo resolver la zona horaria. Revisa CO_VISION_TIMEZONE y la disponibilidad de tzdata; no se han calculado movimientos diarios.")
    if metrics["missing_ids"]:
        st.warning(f'{metrics["missing_ids"]} filas sin ID LION no se incluyen en los indicadores.')
    if metrics["multiple_areas"]:
        st.caption(f'{metrics["multiple_areas"]} máquinas tienen varias delegaciones/áreas; se muestran en un grupo separado sin elegir una arbitrariamente.')
    return metrics
