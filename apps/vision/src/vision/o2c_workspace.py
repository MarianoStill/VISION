from __future__ import annotations
from functools import lru_cache
from typing import NamedTuple
import pandas as pd
import streamlit as st
from vision import lion_adapter
from vision.o2c_summary import STYLE as O2C_SUMMARY_STYLE, render_operational_summary
from vision.commercial_workspace import NO_DATE, _STYLE, _advance, _available, _contrast, _html, _label, format_sap_dates, render_machine_sheet, sort_by_urgency, urgency_bands, urgency_color, with_delivery_dates
from vision.role_selection import O2C_ACTIVE_KEY, O2C_PRIMARY_KEY, O2C_STAGES_KEY
ALL_STAGES = 'Todas mis etapas'
_ALL = {'urgency': 'Todas las urgencias', 'area': 'Todas las delegaciones / áreas', 'commercial': 'Todos los comerciales', 'client': 'Todos los clientes'}

class Col(NamedTuple):
    """Columna de presentación: etiqueta, campo de origen y de dónde sale."""
    label: str
    field: str
    source: str = 'sap'
_DATE_FIELDS = {'Fecha de entrega'}
_SAP_LABELS = {'Sales Representive Name': 'Comercial', 'Descripción de oficina de ventas': 'Delegación / área'}

def _sap(*fields: str) -> tuple[Col, ...]:
    return tuple((Col(_SAP_LABELS.get(f, f), f) for f in fields))
_ORDER = 'Documento de ventas'
_CLIENT = 'Nombre del solicitante'
_ITEM = 'Denomin.posición'
_REP = 'Sales Representive Name'
_AREA = 'Descripción de oficina de ventas'
_PURCH = 'Documento compras'
_SERIAL = 'Número de serie'
_DELIVERY = 'Fecha de entrega'
_GOODS = 'La entrada de mercancías está abierta'
_PP = 'PP DLV Status'
_NOTE = 'Internal Note Line'
_REQUEST = 'Solicitud de pedido'
O2C_STAGE_COLUMNS: dict[int, tuple[Col, ...]] = {1: _sap(_ORDER, _CLIENT, _ITEM, _REP, _AREA, 'Status de usuario'), 2: _sap(_ORDER, _CLIENT, _REQUEST, _ITEM, _REP, _AREA, 'Status de usuario'), 3: _sap(_ORDER, _CLIENT, _REQUEST, _PURCH, _SERIAL, _ITEM, _REP, _AREA), 4: _sap(_ORDER, _CLIENT, _PURCH, _ITEM, _REP, _AREA, _DELIVERY, _GOODS, _PP), 5: _sap(_ORDER, _CLIENT, _PURCH, _ITEM, _SERIAL, _REP, _AREA, _DELIVERY, _GOODS, _PP), 6: _sap(_ORDER, _CLIENT, _PURCH, _ITEM, _SERIAL, _REP, _AREA, _DELIVERY, _GOODS, _PP), 7: _sap(_ORDER, _CLIENT, _PURCH, _ITEM, _SERIAL, _REP, _AREA, _DELIVERY, _GOODS, _PP, _NOTE), 8: _sap(_CLIENT, _PURCH, _ITEM, _SERIAL, _REP, _AREA, _DELIVERY, _GOODS, _PP, _NOTE), 9: _sap(_ORDER, _CLIENT, _PURCH, _ITEM, _SERIAL, _REP, _AREA, _DELIVERY, 'Entrega'), 10: _sap(_ORDER, _CLIENT, _REQUEST, _PURCH, _SERIAL, _ITEM, _REP, _AREA, _DELIVERY, 'Doc.facturación')}
O2C_SUMMARY_COLUMNS: tuple[Col, ...] = (Col('Etapa actual', 'Etapas actuales', 'model'), Col('Documento de ventas', _ORDER), Col('Documento compras', _PURCH), Col('Número de serie', _SERIAL), Col(_ITEM, _ITEM), Col('Cliente', 'Cliente', 'model'), Col('Comercial', 'Comercial', 'model'), Col('Delegación / área', 'Oficina de ventas', 'model'), Col('Urgencia operacional', 'Urgencia', 'model'), Col('Fecha de entrega', _DELIVERY))
URGENCY_LABEL = 'Urgencia operacional'

def _sap_value(frame, field: str) -> str:
    if frame is None or field not in frame.columns:
        return ''
    if field in _DATE_FIELDS:
        shown = format_sap_dates(frame[field])
        return shown
    parts: list[str] = []
    for value in frame[field]:
        if _available(value):
            text = str(value).strip()
            if text not in parts:
                parts.append(text)
    return ' · '.join(parts)

def build_display(table: pd.DataFrame, details: dict | None, spec: tuple[Col, ...], *, with_urgency: bool=False) -> tuple[pd.DataFrame, list[str]]:
    """Tabla visible según la configuración; devuelve también campos no encontrados."""
    details = details or {}
    ids = list(table['ID'])
    present = set()
    for identifier in ids:
        frame = details.get(identifier)
        if frame is not None:
            present.update(frame.columns)
    data: dict[str, list] = {}
    missing: list[str] = []
    for col in spec:
        if col.source == 'model':
            if col.field not in table.columns:
                continue
            data[col.label] = list(table[col.field])
        elif col.field not in present:
            missing.append(col.field)
        else:
            data[col.label] = [_sap_value(details.get(i), col.field) for i in ids]
    if with_urgency and 'Urgencia' in table.columns:
        data[URGENCY_LABEL] = list(table['Urgencia'])
    return (pd.DataFrame(data, index=table.index), missing)

def stage_labels() -> list[str]:
    """Las 10 etapas reales de LION, en orden."""
    return [str(stage['label']) for stage in lion_adapter.stage_progress(None)['timeline']]

@lru_cache(maxsize=512)
def stages_for_state(estado) -> tuple[str, ...]:
    """Etapas de LION a las que pertenece un estado.

    Etapas actuales; una máquina entregada pertenece a la etapa 10.
    """
    timeline = lion_adapter.stage_progress(estado)['timeline']
    current = [str(s['label']) for s in timeline if s['kind'] == 'current']
    if current:
        return tuple(current)
    if timeline and all((s['kind'] == 'done' for s in timeline)):
        return (str(timeline[-1]['label']),)
    return ()

def machine_stages(model: pd.DataFrame) -> pd.Series:
    return model['Estado'].map(stages_for_state) if 'Estado' in model.columns else pd.Series([()] * len(model), index=model.index)

def in_stages(stages: pd.Series, wanted) -> pd.Series:
    wanted = set(wanted)
    return stages.map(lambda items: bool(wanted.intersection(items)))

def urgency_distribution(model: pd.DataFrame, bands) -> list[tuple[str, str | None, int]]:
    """(rango, color, máquinas) por banda de urgencia LION, más las sin valor."""
    colors = [urgency_color(v, bands) for v in model.get('Urgencia', [])]
    rows = []
    for index, (lower, color) in enumerate(bands):
        upper = bands[index + 1][0] - 1 if index + 1 < len(bands) else None
        label = f'{lower}–{upper} d' if upper is not None else f'≥ {lower} d'
        rows.append((label, color, sum((1 for c in colors if c == color))))
    missing = sum((1 for c in colors if c is None))
    if missing:
        rows.append(('Sin urgencia', None, missing))
    return rows

def _seed(key: str, value) -> None:
    if key not in st.session_state:
        st.session_state[key] = value

def render_my_stages(labels: list[str], frame: pd.DataFrame | None=None) -> tuple[list[str], str]:
    """Control «Mis etapas»; devuelve (etapas elegidas, etapa activa)."""
    chosen = [s for s in st.session_state.get(O2C_STAGES_KEY, []) if s in labels]
    st.session_state[O2C_STAGES_KEY] = chosen
    primary = st.session_state.get(O2C_PRIMARY_KEY)
    if chosen and primary not in chosen:
        st.session_state[O2C_PRIMARY_KEY] = chosen[0]
    active = st.session_state.get(O2C_ACTIVE_KEY)
    if active not in (ALL_STAGES, *chosen):
        st.session_state[O2C_ACTIVE_KEY] = chosen[0] if chosen else ALL_STAGES
    with st.expander('Mis etapas', expanded=False):
        st.caption('Filtros de trabajo, no permisos. Puedes cambiarlos cuando quieras.')
        st.multiselect('Etapas con las que trabajo', labels, key=O2C_STAGES_KEY, placeholder='Selecciona al menos una etapa')
        chosen = list(st.session_state.get(O2C_STAGES_KEY, []))
        if chosen:
            if st.session_state.get(O2C_PRIMARY_KEY) not in chosen:
                st.session_state[O2C_PRIMARY_KEY] = chosen[0]
            st.selectbox('Etapa principal', chosen, key=O2C_PRIMARY_KEY)
    chosen = list(st.session_state.get(O2C_STAGES_KEY, []))
    if not chosen:
        return ([], ALL_STAGES)
    if st.session_state.get(O2C_ACTIVE_KEY) not in (ALL_STAGES, *chosen):
        st.session_state[O2C_ACTIVE_KEY] = st.session_state[O2C_PRIMARY_KEY]

    def select_stage(stage):
        st.session_state[O2C_ACTIVE_KEY] = stage
    st.markdown(O2C_SUMMARY_STYLE, unsafe_allow_html=True)
    with st.container(key='o2c_process_navigation'):
        if len(chosen) == 1:
            st.session_state[O2C_ACTIVE_KEY] = chosen[0]
            stage = chosen[0]
            count = int(frame[in_stages(frame['_stages'], [stage])]['ID'].nunique()) if frame is not None else None
            st.markdown(f'**{labels.index(stage) + 1}. {stage}**' + (f' · {count} máquinas' if count is not None else ''))
        else:
            for start in range(0, len(chosen), 5):
                row = chosen[start:start + 5]
                columns = st.columns(len(row), gap='small')
                for column, stage in zip(columns, row):
                    count = int(frame[in_stages(frame['_stages'], [stage])]['ID'].nunique()) if frame is not None else None
                    title = f'{labels.index(stage) + 1}. {stage}' + (f' · {count} máquinas' if count is not None else '')
                    with column:
                        st.button(title, key=f'o2c_stage_nav_v7::{stage}', type='primary' if st.session_state[O2C_ACTIVE_KEY] == stage else 'secondary', width='stretch', on_click=select_stage, args=(stage,))
            st.button('Todas mis etapas', key='o2c_all_nav_v7', type='primary' if st.session_state[O2C_ACTIVE_KEY] == ALL_STAGES else 'secondary', on_click=select_stage, args=(ALL_STAGES,))
    return (chosen, st.session_state[O2C_ACTIVE_KEY])

def _enriched(model: pd.DataFrame, details: dict | None, observation_date) -> pd.DataFrame:
    key = (str(observation_date), id(model), id(details), len(model))
    cached = st.session_state.get('o2c_enriched')
    if cached and cached[0] == key:
        return cached[1]
    frame = with_delivery_dates(model, details)
    frame['Etapas actuales'] = machine_stages(frame).map(' · '.join)
    frame['_stages'] = machine_stages(frame)
    st.session_state['o2c_enriched'] = (key, frame)
    return frame

def render_o2c_workspace(model: pd.DataFrame, *, details: dict | None, history: dict | None, observation_date: str | None) -> None:
    _html(_STYLE)
    labels = stage_labels()
    if observation_date:
        st.caption(f'Datos actualizados a: {_format(observation_date)}')
    frame = _enriched(model, details, observation_date)
    unknown = frame['_stages'].map(len).eq(0)
    show_unknown = st.toggle(f"Estado desconocido · {frame.loc[unknown, 'ID'].nunique()} máquinas", key='o2c_unknown_v16', help='Filtro de seguimiento para máquinas sin etapa LION; no añade una etapa al proceso.')
    chosen, active = render_my_stages(labels, frame)
    if show_unknown:
        active = 'Estado desconocido'
    if not chosen and (not show_unknown):
        st.info('Selecciona al menos una etapa en «Mis etapas» para trabajar.')
        return
    bands = urgency_bands(model)
    wanted = chosen if active == ALL_STAGES else [active]
    scope = frame.loc[unknown] if show_unknown else frame[in_stages(frame['_stages'], wanted)]
    _label('Etapa activa: ' + active, f"{scope['ID'].nunique()} máquinas · una máquina puede estar en más de una etapa")
    if active == ALL_STAGES and len(chosen) > 1:
        st.caption('El total de «Todas mis etapas» cuenta cada máquina una sola vez; la suma de las etapas puede ser mayor.')
    _render_summary(scope, bands, active, history=history, stage_ids=None if show_unknown else _proof_stage_ids(history, wanted, labels))
    if scope.empty:
        st.info('No hay máquinas en las etapas seleccionadas.')
        return
    _label('Máquinas')
    top = st.columns([3, 2])
    text = top[0].text_input('Buscar', placeholder='Buscar por modelo, documento, serie o cliente', label_visibility='collapsed', key='o2c_search')
    urgency_values = sorted({str(v).strip() for v in scope['Urgencia'] if _available(v)}, key=str.casefold) if 'Urgencia' in scope.columns else []
    urgency = top[1].selectbox('Urgencia', [_ALL['urgency'], *urgency_values], label_visibility='collapsed', key='o2c_urgency', disabled=not urgency_values)
    with st.expander('Más filtros'):
        more = st.columns(4)
        choices = {'area': ('Oficina de ventas', 'Delegación / área responsable'), 'commercial': ('Comercial', 'Comercial'), 'client': ('Cliente', 'Cliente')}
        picks = {}
        for slot, (key, (column, title)) in zip(more, choices.items()):
            values = sorted({str(v).strip() for v in scope[column] if _available(v)}, key=str.casefold) if column in scope.columns else []
            picks[key] = slot.selectbox(title, [_ALL[key], *values], key=f'o2c_{key}', disabled=not values)
    table = scope
    if text.strip():
        table = lion_adapter.search_machines(table, text.strip(), 'Todo')
    if urgency != _ALL['urgency']:
        table = table[table['Urgencia'].astype(str).str.strip() == urgency]
    for key, (column, _) in choices.items():
        if picks[key] != _ALL[key] and column in table.columns:
            table = table[table[column].astype(str).str.strip() == picks[key]]
    table = sort_by_urgency(table).reset_index(drop=True)
    if table.empty:
        st.info('No hay máquinas para los filtros seleccionados.')
        return
    if active == ALL_STAGES or show_unknown:
        columns_spec = O2C_SUMMARY_COLUMNS
    else:
        columns_spec = O2C_STAGE_COLUMNS[labels.index(active) + 1]
    display, missing = build_display(table, details, columns_spec, with_urgency=active != ALL_STAGES)
    if missing:
        st.caption('CAMPO NO ENCONTRADO: ' + ', '.join(missing))
    from vision import comments
    comment_counts = comments.counts_for(table)
    if comment_counts.any():
        display['Comentarios'] = comment_counts.map(comments.format_count).values

    def urgency_style(column: pd.Series) -> list[str]:
        styles = []
        for value in column:
            color = urgency_color(value, bands)
            styles.append(f'background-color:{color};color:{_contrast(str(color))};font-weight:600;text-align:center' if color else '')
        return styles
    styled = display.style
    if 'Urgencia operacional' in display.columns:
        styled = styled.apply(urgency_style, subset=['Urgencia operacional'])
    event = st.dataframe(styled, hide_index=True, on_select='rerun', selection_mode='single-row', key=f'o2c_machines_urgency_v5_{active}_{len(table)}_{len(chosen)}', alt='Máquinas de las etapas seleccionadas')
    rows = event.selection.rows
    if not rows or rows[0] >= len(table):
        st.caption('Selecciona una máquina de la lista para abrir su detalle.')
        return
    render_machine_sheet(table.iloc[rows[0]], table, model, model, history, bands)

def _format(value) -> str:
    from vision.commercial_workspace import format_sap_date
    shown = format_sap_date(value)
    return shown if shown != NO_DATE else str(value)

def _proof_stage_ids(history, wanted, labels):
    """ID numérico de etapa solicitado por negocio; nombre exacto como alternativa verificable."""
    if history is None:
        return None
    sources = history.get('sources', [])
    available = {str(source.get('id')) for source in sources}
    result = []
    for label in wanted:
        number = str(labels.index(label) + 1)
        if number in available:
            result.append(number)
            continue
        matches = [str(source['id']) for source in sources if str(source.get('name', '')).strip() == label]
        if len(matches) != 1:
            return None
        result.append(matches[0])
    return result

def _render_summary(scope: pd.DataFrame, bands, active: str='Selección O2C', *, history=None, stage_ids=None) -> None:
    render_operational_summary(scope, bands, active, history=history, stage_ids=stage_ids)

    def available_dates(column):
        if column not in scope or 'ID' not in scope:
            return 0
        mask = scope[column].map(lambda value: _available(value) and value != NO_DATE).astype(bool)
        return scope.loc[mask, 'ID'].nunique()
