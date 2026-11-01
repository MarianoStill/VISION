"""Indicador de carga: estado real y guiños claramente separados."""
from html import escape
import streamlit as st

_HINTS = (
    "Poniendo las carretillas en fila…",
    "Preparando café digital…",
    "Buscando sitio en el almacén de los datos…",
    "Ajustando los retrovisores de VISION…",
)
_STYLE = """<style>
.v8-load{display:flex;align-items:center;gap:16px;background:#f5f9ff;border:1px solid #dce7fa;border-radius:14px;padding:18px 22px;margin:16px 0;color:#13284a}
.v8-spin{width:24px;height:24px;border:3px solid #d7e5ff;border-top-color:#1557ef;border-radius:50%;animation:v8rotate 1s linear infinite;flex-shrink:0}
.v8-message{font-size:15px;font-weight:650}.v8-hint{font-size:12px;color:#7385a2;margin-top:6px}.v8-ready{color:#168354}
@keyframes v8rotate{to{transform:rotate(360deg)}}
@media(prefers-reduced-motion:reduce){.v8-spin{animation:none;border-top-color:#1557ef}}
</style>"""


def render_preload_status(job, *, waiting_for_entry=False, observed=None):
    initial = job.status()
    if initial["phase"] == "ready":
        if waiting_for_entry or (observed is not None and initial["revision"] != observed["revision"]):
            st.rerun()
        st.caption("✓ Datos preparados. Elige tu perfil y entra cuando quieras.")
        return
    # El fragmento solo consulta el estado; no ejecuta servicios ni reinicia trabajos.
    @st.fragment(run_every=1)
    def poll():
        status = job.status()
        marker = (job.key, status["revision"], bool(status["catalog"]), status["phase"] == "error")
        previous = st.session_state.get("_vision_preload_ui_marker_v8")
        if previous != marker:
            st.session_state["_vision_preload_ui_marker_v8"] = marker
            # Refrescar opciones o continuar al terminar; no relanzar por cada texto.
            if previous is not None and (status["phase"] in ("ready", "error")
                                         or bool(status["catalog"])):
                st.rerun()
        st.markdown(_STYLE, unsafe_allow_html=True)
        if status["phase"] == "error":
            st.error("Preparación no completada (" + str(status["error"]) + "). Usa Reintentar; no se ha descartado ningún archivo.")
            return
        if status["phase"] == "ready":
            st.rerun()
        hint = _HINTS[int(status["elapsed"] // 7) % len(_HINTS)]
        st.markdown(
            '<div class="v8-load" role="status" aria-live="polite">'
            '<div class="v8-spin" aria-hidden="true"></div><div><div class="v8-message">' +
            escape(status["message"]) + '</div><div class="v8-hint">Guiño VISION · ' +
            escape(hint) + '</div></div></div>', unsafe_allow_html=True,
        )
        if waiting_for_entry:
            st.caption("La preparación continúa en el servidor. No necesitas volver a pulsar Entrar.")
        else:
            st.caption("Puedes elegir el perfil mientras se preparan los datos. No se añaden esperas de presentación.")
    poll()
