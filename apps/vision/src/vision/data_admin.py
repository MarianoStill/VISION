"""Administración ligera: no requiere cargar LION ni todo el histórico."""
from pathlib import Path
from time import perf_counter

import streamlit as st

from vision import design_system, role_selection
from vision.folder_sync import audit_folder, synchronize_folder
from vision.preload import database_signature
from vision.sap_snapshots import discover_daily_snapshots


@st.cache_data(ttl=30,max_entries=4,show_spinner=False)
def _audit_cached(database_path,directory,signature):
    return audit_folder(database_path,directory)


def render_data_admin(sources,coordinator):
    def leave_admin():
        role_selection.change_profile()
        st.session_state[role_selection.ADMIN_KEY] = False
        st.session_state[role_selection.ENTERED_KEY] = False
    design_system.render_shell(workspace="Administration", on_change_profile=leave_admin)
    st.subheader("Fuentes operacionales · control de fechas")
    diagnostic = st.session_state.get("_vision_history_diagnostic_v15")
    if diagnostic:
        st.warning("Último diagnóstico del histórico en esta sesión: " + str(diagnostic) +
                   ". El banner general se ha retirado de los workspaces; este aviso no implica que el problema esté resuelto.")
    if st.button("Cerrar sesión · volver a la portada",key="admin_logout_v14",on_click=leave_admin):
        st.rerun()
    job=st.session_state.get("_vision_last_preload_job_v12")
    with st.expander("Tiempos medidos de preparación",expanded=False):
        if job is not None:
            status=job.status()
            st.caption("Estado de la última preparación de esta sesión: "+status['message'])
            st.dataframe([dict(Operación=name,Segundos=seconds) for name,seconds in status['timings'].items()],hide_index=True,width="stretch")
        else:
            st.caption("Todavía no se ha preparado un workspace en esta sesión. La administración no fuerza esa carga.")
        times=st.session_state.get("_vision_view_timings_v8",{})
        if times:st.dataframe([dict(Vista=name,Segundos=seconds) for name,seconds in times.items()],hide_index=True,width="stretch")
    db=Path(sources['proof_db']);folder=Path(sources['sap_daily_dir'])
    st.caption("Carpeta SAP configurada: "+str(Path("sap")/folder.name))
    st.caption("Base PROOF configurada: "+db.name)
    if not db.is_file():
        st.error("No se encuentra la base PROOF configurada. No se crea otra base automáticamente.")
        return
    try:
        candidates=discover_daily_snapshots(folder)
        signature=(tuple((str(c.path),c.modified_ns,c.size,c.observation_date) for c in candidates),database_signature(db))
        audit=_audit_cached(str(db),str(folder),signature)
    except Exception as exc:
        st.error("No se pudo conciliar el inventario de archivos ("+type(exc).__name__+").")
        return
    cols=st.columns(4)
    cols[0].metric("Fechas registradas",len(audit['registered_dates']))
    cols[1].metric("Excel disponibles",len(audit['files']))
    cols[2].metric("Pendientes",len(audit['pending']))
    cols[3].metric("Fechas en conflicto",len(audit['conflicts']))
    if audit['registered_dates']:
        st.caption("Primera observación: "+audit['registered_dates'][0]+" · Última observación: "+audit['registered_dates'][-1])
    st.dataframe(audit['rows'],hide_index=True,width="stretch")
    st.caption("Los días sin archivo ni observación se muestran como ausencia de fuente, no como cero movimientos. Incluye fines de semana; no presupone que deba existir un Excel cada día.")
    if audit['conflicts']:
        st.warning("Los conflictos se mantienen sin sobrescribir. Puedes incorporar los pendientes válidos de otras fechas; el histórico seguirá usando la versión ya registrada de las fechas en conflicto.")
    if audit['pending']:
        st.info("Hay Excel disponibles todavía no registrados. Se incorporarán en orden cronológico y PROOF reconstruirá los movimientos afectados con sus reglas guardadas.")
    elif not audit['conflicts']:
        st.success("No hay Excel disponibles pendientes de registrar.")
    st.caption("Antes de escribir se crea un backup SQLite consistente en proof/sync_backups. La reconstrucción conserva las reglas actuales y puede cambiar IDs técnicos de eventos/instancias derivados.")
    if st.button("Incorporar pendientes válidos a PROOF",key="sync_folder_v12",disabled=not audit['pending']):
        try:
            started=perf_counter()
            with st.spinner("Guardando backup e incorporando observaciones con PROOF…"):
                with coordinator._database_lock:
                    result=synchronize_folder(db,folder,Path(sources['root'])/'proof'/'sync_backups')
            st.session_state['_vision_sync_result_v12']=dict(status=result['status'],added=result['added'],backup=result['backup'],message=result['message'],seconds=round(perf_counter()-started,3))
            _audit_cached.clear()
            st.rerun()
        except Exception as exc:
            st.error("Sincronización no completada ("+type(exc).__name__+"). No se ha marcado como correcta. Revisa el backup y los archivos antes de reintentar.")
    last=st.session_state.get('_vision_sync_result_v12')
    if last:
        st.info(last['message'])
        st.caption("Añadidas: "+str(last['added'])+" · Segundos: "+str(last['seconds']))
        if last['backup']:st.caption("Backup de datos: "+Path(last['backup']).name)
    st.caption("La sincronización automática se solicita al entrar a un workspace cuando cambia la preparación de fuentes. No es un servicio programado que funcione con VISION cerrada.")
