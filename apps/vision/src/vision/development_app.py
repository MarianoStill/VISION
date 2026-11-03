from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from time import perf_counter
from zipfile import BadZipFile

import pandas as pd
import proof
import streamlit as st
from openpyxl.utils.exceptions import InvalidFileException

from vision import design_system, lion_adapter, o2c_workspace, role_selection
from vision.commercial_workspace import (
    client_options,
    commercial_options,
    delegation_options,
    render_commercial_workspace,
    scope_by_delegation,
)
from vision.data_sources import (
    resolve_external_sources,
)
from vision.manager_reports import render_manager_reports, scope_documents
from vision.navigation_cache import (
    catalog_signature,
    read_catalog,
    session_value,
    write_catalog,
)
from vision.proof_link import resolve_proof_order_link
from vision.sap_snapshots import (
    SnapshotDiscoveryError,
    discover_daily_snapshots,
)
from vision.synthetic_examples import (
    EMPTY_INVENTORY_INPUTS,
    SYNTHETIC_INVENTORY_INPUTS,
    SYNTHETIC_LION_MACHINE,
)

st.set_page_config(page_title="VISION", layout="wide")
design_system.inject()


@st.cache_data(ttl=60, max_entries=4, show_spinner=False)
def _cached_history(database_path, modified_ns, size, wal_modified_ns, wal_size):
    return proof.read_history(database_path)


@st.cache_data(max_entries=4, show_spinner=False)
def _cached_lion_source(source_path, modified_ns, size, reference_date):
    path = Path(source_path)
    before = path.stat()
    if before.st_mtime_ns != modified_ns or before.st_size != size:
        raise ValueError("El archivo de origen cambió durante la carga.")
    content = path.read_bytes()
    after = path.stat()
    if (
        after.st_mtime_ns != modified_ns
        or after.st_size != size
        or len(content) != size
    ):
        raise ValueError("El archivo de origen cambió durante la carga.")
    return (
        lion_adapter.process_workbook(content, reference_date=reference_date),
        content,
    )


@st.cache_data(ttl=3600, max_entries=64, show_spinner=False)
def _cached_completion_metrics(
    database_path, modified_ns, size, wal_modified_ns, wal_size, documents=None
):
    return proof.calculate_completion_metrics(database_path, documents)


def _database_signature(database_path):
    path = Path(database_path).expanduser().resolve()
    stat = path.stat()
    wal_path = Path(str(path) + "-wal")
    wal_stat = wal_path.stat() if wal_path.exists() else None
    return (
        str(path),
        stat.st_mtime_ns,
        stat.st_size,
        wal_stat.st_mtime_ns if wal_stat else None,
        wal_stat.st_size if wal_stat else None,
    )


def _session_lion_source(source_path, modified_ns, size, reference_date):
    signature = (source_path, modified_ns, size, reference_date)
    return session_value(
        st.session_state, "_vision_lion_loaded_v2", signature,
        lambda: _cached_lion_source(*signature),
    )


def _session_history(*signature):
    return session_value(
        st.session_state, "_vision_history_loaded_v2", tuple(signature),
        lambda: _cached_history(*signature),
    )


@st.cache_resource(show_spinner=False)
def _preload_coordinator_v8():
    from vision.preload import PreloadCoordinator
    return PreloadCoordinator()


def _project_root_v22():
    return Path(__file__).resolve().parents[4]


def _warmup_paths_v22(data_root):
    folder=Path(data_root)/"vision"
    return folder/"landing_warmup_v22.lock",folder/"landing_warmup_v22.json"


def _launch_warmup_v22(data_root):
    marker,status=_warmup_paths_v22(data_root)
    marker.parent.mkdir(parents=True,exist_ok=True)
    if marker.exists():
        try:
            if time.time()-marker.stat().st_mtime<600:return marker,status
            marker.unlink()
        except OSError:return marker,status
    try:
        descriptor=os.open(marker,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        os.close(descriptor)
    except FileExistsError:
        return marker,status
    try:
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)
        subprocess.Popen(
            [sys.executable,str(Path(__file__).with_name("landing_warmup.py")),
             str(_project_root_v22()),str(marker),str(status)],
            cwd=str(_project_root_v22()),stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            creationflags=creationflags,start_new_session=(os.name!="nt"),
        )
    except Exception:
        marker.unlink(missing_ok=True)
    return marker,status


def _wait_for_warmup_v22(data_root):
    marker,status=_warmup_paths_v22(data_root)
    if not marker.exists():return False
    st.markdown("### Preparando tu espacio de trabajo")
    st.caption("Tu acceso ya fue aceptado. LION se está preparando en un proceso independiente.")
    @st.fragment(run_every=0.5)
    def poll():
        if not marker.exists():st.rerun()
        st.progress(0,text="Preparando LION y verificando PROOF…")
    poll();st.stop()


configured_sources = resolve_external_sources()
sap_daily_directory = configured_sources["sap_daily_dir"]
proof_database = configured_sources["proof_db"]
if st.session_state.get(role_selection.ADMIN_KEY):
    from vision.data_admin import render_data_admin
    render_data_admin(configured_sources, _preload_coordinator_v8())
    st.stop()
_navigation_only = not st.session_state.get(role_selection.ENTERED_KEY)
_catalog_path = configured_sources["root"] / "vision" / "access_catalog.json"
_catalog = dict(commercials=[], delegations=[], stages=o2c_workspace.stage_labels())
try:
    _raw_catalog = json.loads(_catalog_path.read_text(encoding="utf-8"))
    for _field in ("commercials", "delegations", "stages"):
        _values = _raw_catalog.get(_field, [])
        if isinstance(_values, list):
            _catalog[_field] = [value for value in _values if isinstance(value, str)]
except (OSError, ValueError, TypeError, AttributeError):
    pass

if _navigation_only:
    # Primero emitir la portada. El trabajo posterior no condiciona la búsqueda ni los controles.
    role_selection.render_role_screen(
        _catalog["commercials"], sources_ready=bool(_catalog["commercials"]),
        delegations=_catalog["delegations"],
        stages=_catalog["stages"] or o2c_workspace.stage_labels(),
        navigation_ready=True,
    )
    # Lanzamiento no bloqueante: la ejecución de portada termina inmediatamente.
    _launch_warmup_v22(configured_sources["root"])
    st.stop()

_wait_for_warmup_v22(configured_sources["root"])

_catalog_signature = None
sap_candidates = []
_preload_job = None
try:
    sap_candidates = discover_daily_snapshots(sap_daily_directory)
    _catalog_signature = catalog_signature(sap_candidates, date.today().isoformat())
    _access_catalog = read_catalog(_catalog_path, _catalog_signature)
    _specs = [(str(c.path), c.modified_ns, c.size, c.observation_date) for c in sap_candidates]
    if not _specs:
        raise ValueError("No hay snapshots XLSX disponibles.")
    _coordinator = _preload_coordinator_v8()
    _preload_job = _coordinator.request(
        _specs, date.today().isoformat(), configured_sources["root"],
        proof_database, o2c_workspace.stage_labels(), _access_catalog,
    )
except (SnapshotDiscoveryError, OSError, ValueError, RuntimeError) as exc:
    st.error("No se pudo iniciar la preparación (" + type(exc).__name__ + "). Revisa las fuentes externas.")
    if st.button("Volver al acceso"):
        role_selection.change_profile()
        st.rerun()
    st.stop()

from vision.loading_ui import render_preload_status

_status = _preload_job.status()
st.session_state["_vision_last_preload_job_v12"] = _preload_job
# Entrar solo finaliza la ingestión existente. No se procesa el XLSX en el hilo UI.
if _status["phase"] == "ready":
    _coordinator.enter(_preload_job)
    _status = _preload_job.status()
if _status["phase"] != "ready":
    # Se reutiliza el asset oficial existente, sin modificar portada ni logos.
    st.markdown(design_system.logo_html("vision_logo_full.png", "VISION", 130), unsafe_allow_html=True)
    st.markdown("### Preparando tu espacio de trabajo")
    if st.button("Volver a elegir perfil", key="v8_back_to_roles"):
        role_selection.change_profile()
        st.session_state.pop(role_selection.ADMIN_KEY, None)
        st.rerun()
    if _status["phase"] == "error" and st.button("Reintentar preparación", key="v8_retry_entry"):
        _coordinator.retry(_preload_job)
        st.rerun()
    render_preload_status(_preload_job, waiting_for_entry=True, observed=_status)
    st.stop()

# Una copia por sesión: los filtros/componentes no pueden modificar datos de otros usuarios.
_bundle = session_value(
    st.session_state, "_vision_preload_bundle_v8",
    (_preload_job.key, _status["revision"]), _preload_job.copy_result,
)
selected_snapshot = _bundle["selected_snapshot"]
snapshot_content = _bundle["snapshot_content"]
sap_error = _bundle["sap_error"]
automatic_lion_output = _bundle["automatic_lion_output"]
source_model, source_details, source_issues = automatic_lion_output[:3]
history_database = str(proof_database) if proof_database.is_file() else None
automatic_history = _bundle["automatic_history"]
proof_error = _bundle["proof_error"]
st.session_state["_vision_history_diagnostic_v15"] = proof_error


def _timed_view_v8(label, function, *args, **kwargs):
    started = perf_counter()
    try:
        return function(*args, **kwargs)
    finally:
        st.session_state.setdefault("_vision_view_timings_v8", {})[label] = round(perf_counter()-started, 3)


def _display(value):
    if value is None or pd.isna(value):
        return "—"
    text = str(value)
    return text if text.strip() else "—"


def _field_table(fields):
    st.dataframe(
        pd.DataFrame(
            [{"Campo": label, "Valor": _display(value)} for label, value in fields]
        ),
        hide_index=True,
        alt="Campos de la máquina seleccionada",
    )


def _stage_names(memberships, sources):
    names = {str(source["id"]): source["name"] for source in sources}
    order = {str(source["id"]): index for index, source in enumerate(sources)}
    stage_ids = sorted(
        {str(record["stage"]) for record in memberships},
        key=lambda stage: order.get(stage, len(order)),
    )
    return [names.get(stage, stage) for stage in stage_ids]


def _render_proof_history(history, sales_document):
    records = proof.history_for_sales_document(history, sales_document)
    if records["observations"]:
        snapshots = []
        for observation in records["observations"]:
            memberships = [
                membership
                for membership in observation["memberships"]
                if str(membership.get("machine", "")).strip() == sales_document
            ]
            snapshots.append(
                {
                    "Fecha de observación": observation["observed_date"],
                    "Etapas observadas": " · ".join(
                        _stage_names(memberships, history["sources"])
                    ),
                    "Pertenencias PROOF": len(memberships),
                    "Versión de reglas": observation["rules_version"],
                }
            )
        st.caption(
            "Cada fila corresponde a una observación almacenada; "
            "la ausencia de una fila no se interpreta como una transición."
        )
        st.dataframe(
            snapshots,
            hide_index=True,
            alt="Observaciones PROOF del Documento de ventas consultado",
        )
        if len(snapshots) == 1:
            st.info(
                "PROOF dispone de una única observación para este Documento de "
                "ventas. Se muestra como tal; no se inventan movimientos intermedios."
            )

    if records["events"]:
        event_rows = [
            {
                "Fecha observada": event.get("observed_date"),
                "Etapa PROOF": event.get("stage_name") or event.get("stage"),
                "Evento": {"A": "Apertura registrada", "C": "Cierre registrado"}.get(
                    event.get("type"), event.get("type")
                ),
                "Estado": event.get("status"),
                "Fecha de apertura": event.get("opening_date"),
                "Fecha de cierre": event.get("closure_date"),
            }
            for event in records["events"]
        ]
        st.markdown("#### Cambios registrados por PROOF")
        st.dataframe(
            event_rows,
            hide_index=True,
            alt="Aperturas y cierres almacenados por PROOF",
        )
    elif records["observations"]:
        st.caption(
            "No hay eventos de apertura o cierre almacenados para esta observación."
        )

    if records["instances"]:
        instance_rows = [
            {
                "Etapa PROOF": instance.get("stage_name") or instance.get("stage"),
                "Apertura observada": instance.get("opening_date"),
                "Cierre observado": instance.get("closure_date"),
                "Estado": instance.get("status"),
                "Días laborables": instance.get("elapsed"),
                "Objetivo (días)": instance.get("target"),
                "Consumo objetivo (%)": instance.get("consumption"),
            }
            for instance in records["instances"]
        ]
        st.markdown("#### Instancias históricas PROOF")
        st.dataframe(
            instance_rows,
            hide_index=True,
            alt="Instancias y duraciones calculadas por PROOF",
        )


with st.sidebar:
    admin_mode = st.toggle("Administración / Datos", key="admin_data_mode")
    mode = "Datos operacionales (DEV)"

_options_signature = (
    str(selected_snapshot.path), selected_snapshot.modified_ns,
    selected_snapshot.size, date.today().isoformat(),
) if selected_snapshot is not None else None
commercials = (
    session_value(st.session_state, "_vision_commercial_options_v2", _options_signature,
                  lambda: commercial_options(source_model, source_details))
    if source_model is not None else []
)
selected_commercial = role_selection.entered_commercial()
if selected_commercial is not None and selected_commercial not in commercials:
    role_selection.change_profile()
    selected_commercial = None
delegations = (
    session_value(st.session_state, "_vision_delegation_options_v2", _options_signature,
                  lambda: delegation_options(source_model))
    if source_model is not None else []
)
selected_delegation = role_selection.entered_manager()
if selected_delegation is not None and selected_delegation not in delegations:
    role_selection.change_profile()
    selected_delegation = None
selected_o2c = role_selection.entered_o2c()
selected_o2c_manager = role_selection.entered_o2c_manager()
o2c_labels = o2c_workspace.stage_labels()
if source_model is not None:
    if _catalog_signature is None:
        _catalog_signature = catalog_signature(sap_candidates, date.today().isoformat())
    _catalog_save_key = json.dumps(_catalog_signature, sort_keys=True)
    if st.session_state.get("_vision_catalog_saved_v2") != _catalog_save_key:
        if write_catalog(_catalog_path, _catalog_signature, commercials, delegations, o2c_labels):
            st.session_state["_vision_catalog_saved_v2"] = _catalog_save_key
page = "Mis clientes"
global_query = ""

if (
    selected_commercial is None
    and selected_delegation is None
    and not selected_o2c
    and not selected_o2c_manager
):
    if source_model is None:
        notice = (
            "No se pudo cargar un snapshot SAP válido. "
            "Revisa Administración / Datos."
        )
    else:
        notice = ""
    design_system.render_shell(workspace="Commercial Workspace")
    role_selection.render_role_screen(
        commercials,
        sources_ready=bool(commercials),
        message=notice,
        delegations=delegations,
        stages=o2c_labels if source_model is not None else [],
    )
    st.stop()

if selected_o2c or selected_o2c_manager:
    design_system.render_shell(
        context=("Perfil", "O2C" if selected_o2c else role_selection.O2C_MANAGER_NAME),
        on_change_profile=role_selection.change_profile,
        workspace="Operational Workspace",
    )
    if source_model is None:
        st.info("No hay un snapshot SAP válido. Revisa Administración / Datos.")
        st.stop()
    if selected_o2c_manager:
        from vision.o2c_global import render_global_report
        _o2c_tab, _global_tab = st.tabs(["Workspace O2C", "Informe global"])
        with _o2c_tab:
            _timed_view_v8("Workspace O2C", o2c_workspace.render_o2c_workspace,
                source_model,
                details=source_details,
                history=automatic_history,
                observation_date=selected_snapshot.observation_date,
            )
        with _global_tab:
            render_global_report(source_model)
            _timed_view_v8(
                "Informes Manager", render_manager_reports,
                automatic_history, scope_documents(source_model),
                history_token=(
                    _database_signature(history_database)
                    if history_database is not None else None
                ),
                load_completion=lambda documents: _cached_completion_metrics(
                    *_database_signature(history_database), documents
                ),
            )
        st.stop()
    _timed_view_v8("Workspace O2C", o2c_workspace.render_o2c_workspace,
        source_model,
        details=source_details,
        history=automatic_history,
        observation_date=selected_snapshot.observation_date,
    )
    st.stop()

if selected_commercial is not None or selected_delegation is not None:
    page, global_query = design_system.render_shell(
        pages=(["Mis clientes"] if selected_delegation is None else None),
        searchable=False,
        context=(
            ("Comercial", selected_commercial)
            if selected_commercial is not None
            else ("Manager Comercial", selected_delegation)
        ),
        on_change_profile=role_selection.change_profile,
        workspace="Commercial Workspace",
    )
    page = page or "Mis clientes"

if not admin_mode:
    if page == "Inicio":
        st.header("Inicio")
        st.info("Selecciona Mis clientes para consultar tu cartera.")
        st.stop()
    if page == "Informes" and selected_delegation is None:
        st.header("Informes")
        st.info("No hay informes disponibles.")
        st.stop()
    if source_model is None:
        if sap_error:
            st.error(
                "No se pudo cargar un snapshot SAP válido con LION ("
                + sap_error
                + "). Revisa Administración / Datos."
            )
        else:
            st.info(
                "No se encontró un snapshot XLSX válido en sap/daily. "
                "Revisa Administración / Datos."
            )
        st.stop()
    if selected_commercial is None and selected_delegation is None:
        st.info("Selecciona un comercial para ver su cartera.")
        st.stop()

    if selected_delegation is not None:
        # Ambas vistas se construyen en la misma ejecucion. Cambiar de pestaña
        # no usa callbacks ni st.rerun: la seleccion se realiza en el navegador.
        delegation = selected_delegation
        st.markdown("### Manager Comercial")
        st.caption(f"Delegación: **{delegation}**")
        context = st.columns([3, 7], vertical_alignment="bottom")
        delegation_model, delegation_details = session_value(
            st.session_state, "_manager_delegation_v6",
            (_options_signature, delegation),
            lambda: scope_by_delegation(source_model, source_details, delegation),
        )
        manager_commercials = session_value(
            st.session_state, "_manager_commercial_options_v6",
            (_options_signature, delegation),
            lambda: commercial_options(delegation_model, delegation_details),
        )
        all_commercials = "Todos los comerciales"
        with context[0]:
            chosen_commercial = st.selectbox(
                "Comercial", [all_commercials, *manager_commercials],
                key=f"manager_commercial::{delegation}",
            )
        def _manager_scope_v6():
            if chosen_commercial != all_commercials:
                model = lion_adapter.filter_machines(
                    delegation_model, delegation_details,
                    filters={"Comercial": chosen_commercial}, exact=True,
                )
            else:
                model = delegation_model
            ids = set(model["ID"])
            details = {identifier: frame for identifier, frame in delegation_details.items()
                       if identifier in ids}
            return model, details
        scoped_model, scoped_details = session_value(
            st.session_state, "_manager_scope_v6",
            (_options_signature, delegation, chosen_commercial),
            _manager_scope_v6,
        )
        clients = session_value(
            st.session_state, "_manager_client_options_v6",
            (_options_signature, delegation, chosen_commercial),
            lambda: client_options(scoped_model, scoped_details),
        )
        with context[1]:
            st.caption(f"{len(manager_commercials) if chosen_commercial == all_commercials else 1} comerciales · "
                       f"{len(clients)} clientes · {scoped_model['ID'].nunique()} máquinas")
        # Pestañas nativas: Streamlit prepara ambos contenidos una vez y el navegador
        # cambia entre paneles sin callbacks ni rerun de navegación.
        machines_tab, reports_tab = st.tabs(["Máquinas", "Informes"])
        with machines_tab:
            _timed_view_v8(
                "Workspace Máquinas", render_commercial_workspace,
                scoped_model, details=scoped_details, identity_model=source_model,
                global_query="", history=automatic_history,
                observation_date=selected_snapshot.observation_date,
                show_commercial=True,
            )
        with reports_tab:
            all_clients = "Todos los clientes"
            chosen_client = st.selectbox(
                "Cliente", [all_clients, *clients],
                key=f"manager_report_client::{delegation}::{chosen_commercial}",
            )
            def _manager_report_scope_v20():
                if chosen_client == all_clients:
                    return scoped_model
                return lion_adapter.filter_machines(
                    scoped_model, scoped_details,
                    filters={"Cliente": chosen_client}, exact=True,
                )
            report_model = session_value(
                st.session_state, "_manager_report_scope_v20",
                (_options_signature, delegation, chosen_commercial, chosen_client),
                _manager_report_scope_v20,
            )
            _timed_view_v8(
                "Informes Manager", render_manager_reports,
                automatic_history, scope_documents(report_model),
                history_token=(
                    _database_signature(history_database)
                    if history_database is not None else None
                ),
                load_completion=lambda documents: _cached_completion_metrics(
                    *_database_signature(history_database), documents
                ),
            )
        st.stop()

    show_commercial = False
    try:
        if selected_delegation is not None:
            show_commercial = True
            delegation = selected_delegation
            st.markdown("### Manager Comercial")
            st.caption(f"Delegación: **{delegation}**")
            context = st.columns(
                [3, 3, 4] if page == "Informes" else [3, 7],
                vertical_alignment="bottom",
            )
            delegation_model, delegation_details = scope_by_delegation(
                source_model, source_details, delegation
            )
            all_commercials = "Todos los comerciales"
            with context[0]:
                chosen_commercial = st.selectbox(
                    "Comercial",
                    [all_commercials, *commercial_options(delegation_model, delegation_details)],
                    key=f"manager_commercial::{delegation}",
                )
            if chosen_commercial != all_commercials:
                scoped_model = lion_adapter.filter_machines(
                    delegation_model,
                    delegation_details,
                    global_query=global_query,
                    filters={"Comercial": chosen_commercial},
                    exact=True,
                )
            elif global_query.strip():
                scoped_model = lion_adapter.filter_machines(
                    delegation_model,
                    delegation_details,
                    global_query=global_query,
                )
            else:
                scoped_model = delegation_model
        else:
            scoped_model = lion_adapter.filter_machines(
                source_model,
                source_details,
                global_query=global_query,
                filters={"Comercial": selected_commercial},
            )
    except ValueError as exc:
        st.error("No se pudo aplicar la búsqueda actual: " + str(exc))
        st.stop()
    if scoped_model.empty:
        st.info("No hay máquinas para los criterios seleccionados.")
        st.stop()
    _scoped_ids = set(scoped_model["ID"])
    scoped_details = {
        identifier: frame
        for identifier, frame in source_details.items()
        if identifier in _scoped_ids
    }
    if selected_delegation is not None:
        if page == "Informes":
            all_clients = "Todos los clientes"
            with context[1]:
                chosen_client = st.selectbox(
                    "Cliente",
                    [all_clients, *client_options(scoped_model, scoped_details)],
                    key=f"manager_report_client::{delegation}::{chosen_commercial}",
                )
            if chosen_client != all_clients:
                scoped_model = lion_adapter.filter_machines(
                    scoped_model,
                    scoped_details,
                    filters={"Cliente": chosen_client},
                    exact=True,
                )
                scoped_details = {
                    identifier: frame
                    for identifier, frame in scoped_details.items()
                    if identifier in set(scoped_model["ID"])
                }
        summary_slot = context[-1]
        with summary_slot:
            st.caption(
                f"{len(commercial_options(scoped_model, scoped_details))} comerciales · "
                f"{len(client_options(scoped_model, scoped_details))} clientes · "
                f"{scoped_model['ID'].nunique()} máquinas"
            )
    if page == "Informes":
        _timed_view_v8("Informes Manager", render_manager_reports,
            automatic_history,
            scope_documents(scoped_model),
            load_completion=lambda documents: _cached_completion_metrics(
                *_database_signature(history_database), documents
            ),
        )
        st.stop()
    scoped_history = automatic_history
    _timed_view_v8("Workspace Máquinas", render_commercial_workspace,
        scoped_model,
        details=scoped_details,
        identity_model=source_model,
        global_query="",
        history=scoped_history,
        observation_date=selected_snapshot.observation_date,
        show_commercial=show_commercial,
    )
    st.stop()

if page == "Inicio":
    st.header("Inicio")
    st.caption(
        "Selecciona Mis clientes para consultar los datos disponibles y abrir "
        "la ficha de una máquina."
    )
    st.info("Abre Mis clientes para consultar la cartera.")
    st.stop()

if mode == "Demostración (DEMO)":
    st.warning(
        "MODO DEMOSTRACIÓN (DEMO). Datos sintéticos; sin conexión a SAP ni producción."
    )
    st.header("Espacio de máquina · DEMO")
    st.caption(
        "Este registro artificial solo demuestra la interfaz. No es una máquina, "
        "clasificación, urgencia ni evidencia operacional."
    )

    demo_model = pd.DataFrame([SYNTHETIC_LION_MACHINE])
    machine_query = st.text_input(
        "Buscar por documento de ventas / pedido",
        placeholder="Ejemplo técnico: DEMO-ORDEN-001",
    ).strip()
    demo_matches = lion_adapter.search_machines(
        demo_model, machine_query, mode="Pedido"
    )
    if machine_query and demo_matches.empty:
        st.info("No hay resultados DEMO para ese documento de ventas.")
    else:
        machine_options = demo_matches if machine_query else demo_model
        selected_id = st.selectbox(
            "Selecciona una máquina DEMO",
            machine_options["ID"].tolist(),
            format_func=lambda _: "DEMO · Equipo técnico",
        )
        selected = demo_model.loc[demo_model["ID"] == selected_id].iloc[0]

        st.subheader("Identificadores disponibles en la muestra")
        _field_table(
            [
                ("Documento de ventas / pedido", selected["Pedido"]),
                ("Documento de compras", selected["Documento de compras"]),
                ("Número de serie / chasis", selected["Número de serie"]),
            ]
        )

        st.subheader("Situación de LION · demostración técnica")
        stage_progress = lion_adapter.stage_progress(selected["Estado"])
        _field_table(
            [
                (
                    "Estado de muestra interpretado por LION",
                    stage_progress["display_status"],
                ),
                ("Urgencia operacional", "No disponible en DEMO"),
                ("Prioridad comercial de VISION", "Pendiente; no implementada"),
            ]
        )
        st.caption(
            "La etapa es texto sintético enviado al adaptador público de LION para "
            "demostrar su presentación. No es una clasificación operacional. "
            "La prioridad comercial no se deriva de la urgencia."
        )
        st.caption(stage_progress["caption"])
        for stage in stage_progress["timeline"]:
            st.progress(
                stage["percent"],
                text=f"{stage['number']}. {stage['label']} · {stage['percent']}%",
            )

    st.subheader("Proceso PROOF · proyección técnica DEMO")
    st.info(
        "No hay observaciones ni histórico operacional PROOF en modo DEMO. "
        "La proyección siguiente es sintética y no representa evolución histórica."
    )
    use_empty_input = st.checkbox("Probar una entrada vacía")
    projection_inputs = (
        EMPTY_INVENTORY_INPUTS if use_empty_input else SYNTHETIC_INVENTORY_INPUTS
    )
    rows, stages = proof.project_inventory(**projection_inputs)

    st.subheader("Filas de la proyección")
    st.dataframe(rows, alt="Filas devueltas por la proyección de inventario de PROOF")

    st.subheader("Etapas devueltas por la proyección")
    st.dataframe(stages, alt="Etapas devueltas por PROOF para el ejemplo sintético")

    if not rows:
        st.info("PROOF devolvió cero filas para esta entrada.")
else:
    st.warning(
        "MODO DATOS OPERACIONALES (DEV). Solo procesa el XLSX local que el usuario "
        "selecciona; sin conexión a SAP ni producción."
    )
    st.caption(
        "La copia recibida de LION no está confirmada como idéntica a Azure. "
        "LION conserva su urgencia operacional; VISION no calcula prioridad comercial. "
        "Los perfiles y permisos organizativos siguen pendientes; no hay autenticación."
    )
    st.header("LION y PROOF · Archivo local")
    st.info(
        "Los archivos operacionales no se guardan en Git. Sin un archivo seleccionado, "
        "no se muestran resultados operacionales."
    )
    uploaded_file = st.file_uploader(
        "Selecciona un archivo XLSX",
        type=["xlsx"],
        max_upload_size=30,
    )

    reference_database = (
        os.environ.get("CO_VISION_PROOF_DB")
        or os.environ.get("CO_VISION_PROOF_REFERENCE_DB")
        or (str(proof_database) if proof_database.is_file() else None)
    )
    reference_match = None
    reference_error = False
    content = uploaded_file.getvalue() if uploaded_file is not None else None
    if content and reference_database:
        try:
            reference_match = proof.find_reference_observation(
                reference_database, content
            )
        except (OSError, sqlite3.Error, ValueError):
            reference_error = True
            st.error(
                "No se pudo consultar el histórico configurado en solo lectura. "
                "El procesamiento queda deshabilitado para evitar una duplicación."
            )
    elif content:
        st.info(
            "No hay histórico de referencia configurado. El archivo nuevo se "
            "registrará únicamente en el almacenamiento DEV."
        )

    with st.form("local_processing"):
        if reference_match is not None:
            observed_date = date.fromisoformat(reference_match["observed_date"])
            st.text(
                "Fecha de observación ya registrada en la referencia: "
                + observed_date.isoformat()
            )
        else:
            observed_date = st.date_input(
                "Fecha de observación",
                value=None,
                format="DD/MM/YYYY",
                help=(
                    "Obligatoria para cada archivo nuevo; no se infiere del nombre "
                    "ni de su fecha de modificación."
                ),
            )
        submitted = st.form_submit_button(
            "Procesar con LION y consultar PROOF",
            disabled=uploaded_file is None or reference_error,
        )

    if submitted and uploaded_file is not None and observed_date is None:
        st.error("Selecciona la fecha de observación antes de procesar el archivo.")
    elif submitted and uploaded_file is not None and observed_date is not None:
        try:
            lion_output = lion_adapter.process_workbook(
                content,
                reference_date=observed_date.isoformat(),
            )
            proof_output = proof.register_snapshot(
                content,
                uploaded_file.name,
                observed_date.isoformat(),
                reference_database_path=reference_database,
            )
            history_database = (
                reference_database
                if proof_output["status"] == "already_in_reference"
                else proof.default_dev_database_path()
            )
            st.session_state["local_processing_key"] = (
                hashlib.sha256(content).hexdigest(),
                observed_date.isoformat(),
            )
            st.session_state["local_processing_result"] = (
                lion_output,
                proof_output,
                str(history_database),
            )
        except (OSError, sqlite3.Error, ValueError, proof.ProofError) as exc:
            st.error(
                "No se completó el procesamiento local ("
                + type(exc).__name__
                + "). Revisa el XLSX, la fecha y el almacenamiento DEV."
            )

    current_key = (
        (hashlib.sha256(content).hexdigest(), observed_date.isoformat())
        if content and observed_date is not None
        else None
    )
    if page == "Mis clientes" and (
        current_key is None
        or st.session_state.get("local_processing_key") != current_key
    ):
        st.info(
            "Selecciona un XLSX autorizado, indica su fecha de observación y "
            "procésalo para cargar los clientes de esta sesión."
        )
        st.stop()
    if (
        current_key is not None
        and st.session_state.get("local_processing_key") == current_key
    ):
        lion_output, proof_output, history_database = st.session_state[
            "local_processing_result"
        ]
        model, details, issues, _, source_sheet = lion_output
        history_label = (
            "copia aislada de referencia, solo lectura"
            if proof_output["status"] == "already_in_reference"
            else "observación independiente en almacenamiento DEV"
        )
        st.success(
            f"LION procesó la hoja {source_sheet!r}: {len(model):,} resultados."
        )
        st.caption(
            "PROOF · "
            + history_label
            + " · "
            + proof_output["observed_date"]
            + ". Las salidas de clasificación de LION y PROOF se mantienen separadas."
        )
        st.subheader("LION · Situación actual y búsqueda")
        st.caption(
            "Los identificadores y campos se muestran según el resultado de LION. "
            "El filtro Chasis solo usa columnas explícitas de chasis/bastidor; "
            "no sustituye el número de serie."
        )
        with st.form("lion_search"):
            global_query = st.text_input(
                "Búsqueda global",
                placeholder="Pedido, modelo, número de serie, material o cliente",
            )
            filter_columns = st.columns(5)
            filter_labels = ["Comercial", "Cliente", "Pedido", "Máquina", "Chasis"]
            filters = {}
            for column, label in zip(filter_columns, filter_labels):
                with column:
                    filters[label] = st.text_input(
                        label,
                        placeholder="Coincidencia parcial",
                    )
            exact_match = st.checkbox("Coincidencia exacta")
            submitted_search = st.form_submit_button("Buscar", type="primary")

        if submitted_search:
            st.session_state["lion_search_submitted"] = True
        if not st.session_state.get("lion_search_submitted"):
            st.info("Introduce un criterio y pulsa Buscar para consultar las máquinas.")
        else:
            try:
                results = lion_adapter.filter_machines(
                    model,
                    details,
                    global_query,
                    filters,
                    exact_match,
                )
            except ValueError as exc:
                st.error(str(exc))
                results = model.iloc[:0].copy()

            if results.empty:
                if not global_query.strip() and not any(
                    value.strip() for value in filters.values()
                ):
                    st.info("Indica al menos un criterio de búsqueda.")
                else:
                    st.info("No hay resultados para los criterios actuales.")
            else:
                visible_columns = [
                    column
                    for column in (
                        "Pedido",
                        "Máquina",
                        "Número de serie",
                        "Cliente",
                        "Estado",
                        "Urgencia",
                        "Color urgencia",
                    )
                    if column in results.columns
                ]
                st.caption(f"Resultados de LION: {len(results):,}")
                st.dataframe(
                    results[visible_columns],
                    hide_index=True,
                    alt="Resultados de búsqueda, clasificación y urgencia de LION",
                )

                def machine_label(identifier):
                    row = model.loc[model["ID"] == identifier].iloc[0]
                    values = [
                        str(row[column]).strip()
                        for column in ("Pedido", "Número de serie", "Máquina")
                        if column in row.index
                        and pd.notna(row[column])
                        and str(row[column]).strip()
                    ]
                    return " · ".join(values) or "Máquina sin descripción"

                selected_id = st.selectbox(
                    "Selecciona un resultado LION",
                    results["ID"].tolist(),
                    format_func=machine_label,
                )
                selected = model.loc[model["ID"] == selected_id].iloc[0]
                selected_details = details[selected_id]

                st.subheader("Ficha operacional · LION")
                st.caption(
                    "Clasificación, campos y urgencia proceden de LION; "
                    "no se recalculan en VISION."
                )
                stage_progress = lion_adapter.stage_progress(selected["Estado"])
                _field_table(
                    [
                        (
                            "Etapa o etapas actuales",
                            " · ".join(stage_progress["states"]),
                        ),
                        ("Estado presentado por LION", stage_progress["display_status"]),
                        ("Progreso del proceso LION", stage_progress["caption"]),
                        ("Urgencia operacional (días LION)", selected["Urgencia"]),
                        ("Color urgencia LION", selected["Color urgencia"]),
                        (
                            "Fecha de referencia de urgencia",
                            selected["Fecha de referencia de urgencia"],
                        ),
                    ]
                )
                st.markdown("#### Avance del proceso LION")
                for stage in stage_progress["timeline"]:
                    st.progress(
                        stage["percent"],
                        text=(
                            f"{stage['number']}. {stage['label']} · "
                            f"{stage['percent']}%"
                        ),
                    )
                st.caption(
                    "0% pendiente, 50% etapa actual y 100% completada. "
                    "Estos porcentajes de secuencia no representan tiempo transcurrido."
                )
                columns = st.columns(2)
                with columns[0]:
                    st.markdown("#### Identificadores disponibles en LION")
                    _field_table(
                        [
                            ("Documento de ventas / pedido", selected["Pedido"]),
                            ("Documento de compras", selected["Documento de compras"]),
                            ("Número de serie", selected["Número de serie"]),
                        ]
                    )
                with columns[1]:
                    st.markdown("#### Información comercial y de entrega")
                    _field_table(
                        [
                            ("Máquina", selected["Máquina"]),
                            ("Material", selected["Material"]),
                            ("Cliente", selected["Cliente"]),
                            ("Comercial", selected["Comercial"]),
                            ("Oficina de ventas", selected["Oficina de ventas"]),
                            (
                                "Fecha de entrega (Excel)",
                                selected["Fecha de entrega (Excel)"],
                            ),
                            (
                                "Fecha estimada de entrega",
                                selected["Fecha estimada de entrega"],
                            ),
                        ]
                    )
                _field_table(
                    [
                        ("Evidencia LION", selected["Evidencia"]),
                        ("Aviso LION", selected["Aviso"]),
                        ("Relaciones ambiguas LION", selected["Relaciones ambiguas"]),
                    ]
                )

                st.subheader("PROOF · Evolución e histórico disponible")
                try:
                    history_signature = _database_signature(history_database)
                    history = _cached_history(*history_signature)
                except (OSError, sqlite3.Error, ValueError) as exc:
                    st.error(
                        "No se pudo leer el historial PROOF ("
                        + type(exc).__name__
                        + "). El origen se mantiene sin modificar."
                    )
                    history = None

                if history is not None:
                    link = resolve_proof_order_link(model, selected, history)
                    if link["linked"]:
                        st.info(link["granularity_notice"])
                    else:
                        st.warning(
                            link["reason"],
                            title="Máquina no vinculada a PROOF",
                        )

                    if link["observations"] or link["events"] or link["instances"]:
                        _render_proof_history(history, link["sales_document"])

                with st.expander("Datos de origen para diagnóstico"):
                    derived_columns = [
                        column
                        for column in (
                            "Fila Excel",
                            "Weeks",
                            "Por días",
                            "Estimado",
                            "Hoy",
                            "Urgencia",
                        )
                        if column in selected_details.columns
                    ]
                    source_rows = selected_details.drop(
                        columns=derived_columns, errors="ignore"
                    )
                    st.caption(
                        "Columnas originales de la hoja procesada por LION, "
                        "sin recalcular sus valores."
                    )
                    st.dataframe(
                        source_rows,
                        hide_index=True,
                        alt="Campos originales de las filas XLSX asociadas",
                    )
                    if derived_columns:
                        with st.expander("Campos auxiliares derivados por LION"):
                            st.dataframe(
                                selected_details[derived_columns],
                                hide_index=True,
                                alt="Campos auxiliares incluidos en el detalle LION",
                            )

                if not issues.empty:
                    with st.expander(
                        f"Relaciones y registros que LION marca para revisión ({len(issues)})"
                    ):
                        st.dataframe(
                            issues,
                            hide_index=True,
                            alt="Avisos emitidos por LION durante la clasificación",
                        )

        st.divider()
        st.subheader("PROOF · Consultas temporales")
        try:
            history_signature = _database_signature(history_database)
            history = _cached_history(*history_signature)
        except (OSError, sqlite3.Error, ValueError) as exc:
            st.error(
                "No se pudieron cargar las consultas temporales PROOF ("
                + type(exc).__name__
                + ")."
            )
            history = None

        if history is not None:
            search_scope = tuple(history_signature)
            if st.session_state.get("proof_history_search_scope") != search_scope:
                for key in (
                    "proof_history_search_index",
                    "proof_history_search_results",
                    "proof_history_filters_applied",
                    "proof_completion_result",
                    "proof_history_selected_document",
                    "proof_attention_stage",
                ):
                    st.session_state.pop(key, None)
                for key in list(st.session_state):
                    if key.startswith("proof_history_filter_"):
                        st.session_state.pop(key, None)
                st.session_state["proof_history_search_scope"] = search_scope
            filter_applied = st.session_state.get(
                "proof_history_filters_applied", False
            )
            selected_documents = st.session_state.get(
                "proof_history_search_results"
            )
            history_view = (
                proof.filter_history(history, selected_documents)
                if filter_applied and selected_documents is not None
                else history
            )
            if filter_applied:
                st.info(
                    "Consultas temporales PROOF limitadas a los Documentos de "
                    "ventas seleccionados. La selección no altera el histórico guardado."
                )
            observations = history_view["observations"]
            with st.expander("Seguimiento y demoras PROOF"):
                summary = proof.operational_summary(history_view)
                kpi_columns = st.columns(4)
                kpi_columns[0].metric(
                    "Expedientes en seguimiento",
                    summary["monitored_count"],
                )
                kpi_columns[1].metric(
                    "En plazo",
                    summary["ontime_count"],
                )
                kpi_columns[2].metric(
                    "Fuera del 100% de consumo",
                    summary["overdue_count"],
                )
                kpi_columns[3].metric(
                    "Con objetivo calculable",
                    summary["calculable_count"],
                )
                st.caption(
                    "Métricas PROOF por Documento de ventas, independientes de "
                    "clasificación y urgencia LION. Se conserva el comportamiento "
                    "recibido: los KPI de seguimiento cuentan consumo >100%, mientras "
                    "que el desglose por etapa marca >120% como fuera del objetivo."
                )
                stage_rows = [
                    {
                        "Etapa": f"{row['id']}. {row['name']}",
                        "Expedientes": row["documents"],
                        "Consumo medio (%)": (
                            round(row["average_consumption"], 1)
                            if row["average_consumption"] is not None
                            else None
                        ),
                        "Antes (<80%)": row["before_target"],
                        "En torno (80–120%)": row["around_target"],
                        "Fuera (>120%)": row["over_target"],
                        "Objetivo (días)": row["target"],
                    }
                    for row in summary["stage_rows"]
                    if not row["terminal"]
                ]
                st.dataframe(
                    stage_rows,
                    hide_index=True,
                    alt="Métricas de seguimiento PROOF por etapa",
                )
                standard_stages = [
                    f"{row['id']}. {row['name']}"
                    for row in summary["stage_rows"]
                    if not row["terminal"]
                ]
                selected_stage = st.selectbox(
                    "Filtrar expedientes que requieren atención por etapa",
                    ["Todas"] + standard_stages,
                    key="proof_attention_stage",
                )
                attention = [
                    row
                    for row in summary["attention_rows"]
                    if row["Consumo de tiempo (%)"] is not None
                    and row["Consumo de tiempo (%)"] >= 80
                    and (
                        selected_stage == "Todas"
                        or row["Etapa"] == selected_stage
                    )
                ]
                st.markdown("#### Expedientes desde el 80% del objetivo")
                if attention:
                    st.dataframe(
                        attention,
                        hide_index=True,
                        alt="Expedientes PROOF con consumo de objetivo desde 80%",
                    )
                else:
                    st.info("No hay casos con los filtros actuales.")

            if observations:
                observation_rows = [
                    {
                        "Fecha de observación": observation["observed_date"],
                        "Archivo": observation["summary"].get("Archivo"),
                        "Documentos clasificados": observation["record_count"],
                        "Pertenencias clasificadas": observation["membership_count"],
                        "Versión de reglas": observation["rules_version"],
                    }
                    for observation in observations
                ]
                with st.expander(
                    f"Observaciones disponibles en PROOF ({len(observations)})"
                ):
                    st.dataframe(
                        observation_rows,
                        hide_index=True,
                        alt="Observaciones almacenadas en PROOF",
                    )

            with st.expander(
                "Buscar histórico PROOF por serie o documento de compras"
            ):
                st.caption(
                    "El índice se prepara solo a petición y permanece en la sesión. "
                    "La consulta por serie o compra localiza Documentos de ventas; "
                    "no convierte esos identificadores en una clave común."
                )
                if "proof_history_search_index" not in st.session_state:
                    if st.button(
                        "Preparar índice desde las fuentes guardadas",
                        key="proof_history_search_prepare",
                    ):
                        progress = st.progress(0.0)
                        try:
                            with st.spinner(
                                "Leyendo los XLSX almacenados en modo de solo lectura."
                            ):
                                st.session_state["proof_history_search_index"] = (
                                    proof.read_search_index(
                                        history_database,
                                        progress=progress.progress,
                                    )
                                )
                        except (
                            BadZipFile,
                            InvalidFileException,
                            OSError,
                            sqlite3.Error,
                            ValueError,
                        ) as exc:
                            st.error(
                                "No se pudo preparar el índice PROOF ("
                                + type(exc).__name__
                                + ")."
                            )
                    st.caption(
                        "La preparación lee una fuente XLSX cada vez y no modifica "
                        "observaciones, eventos ni reglas."
                    )

                search_index = st.session_state.get("proof_history_search_index")
                if search_index is not None:
                    if search_index["missing"]:
                        st.warning(
                            "Sin fuente indexable en: "
                            + ", ".join(search_index["missing"])
                        )
                    filter_options = {
                        label: sorted(
                            {
                                row.get(label) or "Sin dato"
                                for document in search_index["documents"].values()
                                for row in document["rows"]
                            }
                        )
                        for label in ("Delegación", "Comercial", "Cliente")
                    }
                    with st.form("proof_history_search"):
                        filter_columns = st.columns(3)
                        selections = {}
                        for column, label in zip(
                            filter_columns, ("Delegación", "Comercial", "Cliente")
                        ):
                            with column:
                                selections[label] = set(
                                    st.multiselect(
                                        label,
                                        filter_options[label],
                                        default=filter_options[label],
                                        key="proof_history_filter_" + label,
                                    )
                                )
                        identifier_query = st.text_input(
                            "Número de serie o documento de compras",
                            placeholder="Coincidencia exacta; vacío para todos",
                        ).strip()
                        search_submitted = st.form_submit_button(
                            "Consultar PROOF por identificador"
                        )
                    if search_submitted:
                        st.session_state["proof_history_search_results"] = (
                            proof.filter_history_documents(
                                search_index,
                                history["events"],
                                selections,
                                identifier_query,
                            )
                        )
                        st.session_state["proof_history_filters_applied"] = True
                        st.session_state.pop("proof_completion_result", None)
                        st.rerun()

                    matched_documents = st.session_state.get(
                        "proof_history_search_results"
                    )
                    if matched_documents is not None:
                        if st.session_state.get("proof_history_filters_applied"):
                            if st.button(
                                "Restablecer filtros de las consultas PROOF",
                                key="proof_history_filters_reset",
                            ):
                                st.session_state[
                                    "proof_history_filters_applied"
                                ] = False
                                st.session_state.pop("proof_completion_result", None)
                                st.rerun()
                        st.caption(
                            f"{len(matched_documents):,} Documentos de ventas "
                            "seleccionados; atributos de la última fuente disponible "
                            "por documento."
                        )
                        if identifier_query and len(matched_documents) > 1:
                            st.info(
                                "El identificador coincide con varios expedientes. "
                                "Se muestran por separado, sin fusionar sus recorridos."
                            )
                        if matched_documents:
                            selected_document = st.selectbox(
                                "Documento de ventas consultado",
                                matched_documents,
                                key="proof_history_selected_document",
                            )
                            st.warning(
                                "PROOF registra este histórico por Documento de ventas. "
                                "Si el pedido incluye varias máquinas, sus eventos y "
                                "duraciones no pueden separarse retrospectivamente."
                            )
                            _render_proof_history(history, selected_document)
                        else:
                            st.info(
                                "No hay expedientes PROOF para los filtros e "
                                "identificador exacto seleccionados."
                            )

            if history_view["dates"] and history_view["sources"]:
                with st.expander("Inventario PROOF por periodo"):
                    first_date = date.fromisoformat(history_view["dates"][0])
                    last_date = date.fromisoformat(history_view["dates"][-1])
                    date_columns = st.columns(2)
                    start_date = date_columns[0].date_input(
                        "Desde",
                        value=first_date,
                        min_value=first_date,
                        max_value=last_date,
                        format="DD/MM/YYYY",
                        key="proof_inventory_start",
                    )
                    end_date = date_columns[1].date_input(
                        "Hasta",
                        value=last_date,
                        min_value=first_date,
                        max_value=last_date,
                        format="DD/MM/YYYY",
                        key="proof_inventory_end",
                    )
                    grain = st.segmented_control(
                        "Agrupar por",
                        ["Día", "Semana", "Mes"],
                        default="Semana",
                        key="proof_inventory_grain",
                    )
                    if start_date > end_date:
                        st.error("La fecha inicial debe ser anterior a la final.")
                    else:
                        rows, _ = proof.project_inventory(
                            history_view["instances"],
                            history_view["dates"],
                            history_view["sources"],
                            grain,
                            start_date.isoformat(),
                            end_date.isoformat(),
                        )
                        if rows:
                            inventory = pd.DataFrame(rows)
                            chart = inventory.pivot(
                                index="Periodo",
                                columns="Etapa",
                                values="Expedientes pendientes",
                            )
                            st.line_chart(
                                chart,
                                alt="Inventario PROOF por etapa y periodo",
                            )
                            st.dataframe(
                                inventory,
                                hide_index=True,
                                alt="Valores del inventario PROOF por periodo",
                            )
                            st.caption(
                                "La proyección usa el último estado observado de cada "
                                "periodo. Las etapas simultáneas pueden contar un mismo "
                                "Documento de ventas en más de una etapa."
                            )
                        else:
                            st.info("No hay observaciones en el periodo seleccionado.")

            with st.expander("Consulta PROOF de finalizaciones y tiempos"):
                st.caption(
                    "Consulta recibida de PROOF: el acumulado se obtiene del histórico; "
                    "las duraciones requieren leer las fechas de precio almacenadas."
                )
                if st.button(
                    "Calcular o actualizar promedio de finalizadas",
                    key="proof_completion_calculate",
                ):
                    try:
                        signature = _database_signature(history_database)
                        with st.spinner(
                            "Calculando con los Excel históricos almacenados, sin modificar PROOF."
                        ):
                            st.session_state["proof_completion_result"] = (
                                _cached_completion_metrics(
                                    *signature,
                                    documents=(
                                        selected_documents
                                        if filter_applied
                                        else None
                                    ),
                                )
                            )
                    except (OSError, sqlite3.Error, ValueError) as exc:
                        st.error(
                            "No se pudo calcular la consulta PROOF ("
                            + type(exc).__name__
                            + ")."
                        )
                completion = st.session_state.get("proof_completion_result")
                if completion is not None:
                    st.write(
                        "Finalizadas acumuladas:",
                        completion["completed_count"],
                        "· Iniciales excluidas del promedio:",
                        completion["baseline_completed_count"],
                        "· Cierres posteriores:",
                        completion["registered_completed_count"],
                    )
                    st.write(
                        "Promedio:",
                        completion["average_days"],
                        "· Mediana:",
                        completion["median_days"],
                        "· Mínimo / máximo:",
                        completion["min_days"],
                        "/",
                        completion["max_days"],
                        "días laborables",
                    )
                    if completion["rows"]:
                        st.dataframe(
                            completion["rows"],
                            hide_index=True,
                            alt="Detalle de las finalizaciones calculables por PROOF",
                        )
                    st.caption(
                        "Cobertura calculable: "
                        f"{completion['calculable_count']} de "
                        f"{completion['registered_completed_count']} cierres posteriores."
                    )
