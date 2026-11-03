from __future__ import annotations
import streamlit as st

ROLE_KEY="vision_role";COMMERCIAL_KEY="vision_commercial";ENTERED_KEY="vision_entered";ADMIN_KEY="admin_data_mode"
COMMERCIAL_ROLE="Comercial";MANAGER_ROLE="Manager Comercial";O2C_ROLE="O2C"
DELEGATION_KEY="vision_delegation";O2C_STAGES_KEY="o2c_stages";O2C_PRIMARY_KEY="o2c_primary";O2C_ACTIVE_KEY="o2c_active"
O2C_MANAGER_ROLE="Manager O2C Global";O2C_MANAGER_NAME="Ana Feliu"
ACCESS_ERROR_KEY="vision_access_error"
_PROFILE_KEYS=(ROLE_KEY,COMMERCIAL_KEY,DELEGATION_KEY,ENTERED_KEY)


def entered_o2c_manager():
    return bool(st.session_state.get(ENTERED_KEY) and st.session_state.get(ROLE_KEY)==O2C_MANAGER_ROLE)


def entered_commercial():
    return st.session_state.get(COMMERCIAL_KEY) if st.session_state.get(ENTERED_KEY) and st.session_state.get(ROLE_KEY)==COMMERCIAL_ROLE else None


def entered_manager():
    return st.session_state.get(DELEGATION_KEY) if st.session_state.get(ENTERED_KEY) and st.session_state.get(ROLE_KEY)==MANAGER_ROLE else None


def entered_o2c():
    return bool(st.session_state.get(ENTERED_KEY) and st.session_state.get(ROLE_KEY)==O2C_ROLE)


def current_author():
    if not st.session_state.get(ENTERED_KEY):return None
    role=st.session_state.get(ROLE_KEY)
    if role==COMMERCIAL_ROLE and st.session_state.get(COMMERCIAL_KEY):return st.session_state[COMMERCIAL_KEY],COMMERCIAL_ROLE
    if role==MANAGER_ROLE and st.session_state.get(DELEGATION_KEY):return "Manager Comercial · "+st.session_state[DELEGATION_KEY],MANAGER_ROLE
    if role==O2C_ROLE:return "Usuario O2C",O2C_ROLE
    if role==O2C_MANAGER_ROLE:return O2C_MANAGER_NAME,O2C_MANAGER_ROLE
    return None


def _clear_context():
    exact=set(_PROFILE_KEYS)|{ADMIN_KEY,"vision_navigation",O2C_STAGES_KEY,O2C_PRIMARY_KEY,O2C_ACTIVE_KEY,"o2c_stage_options","manager_workspace_view_v20",ACCESS_ERROR_KEY,"_vision_manager_report_cache_v6"}
    prefixes=("manager_","_manager_","mgr_report_","o2c_","global_o2c_","vision_access_text_","commercial_","comment_box::","comment_error::","comment_send::")
    for key in list(st.session_state):
        if key in exact or str(key).startswith(prefixes):
            st.session_state.pop(key,None)


def change_profile():
    _clear_context()
    # Fuerza una nueva instancia de los widgets de acceso en el navegador.
    st.session_state["vision_access_epoch"] = int(st.session_state.get("vision_access_epoch",0)) + 1


def _norm(text):
    return " ".join(str(text or "").split()).casefold()


def resolve_option(typed,options):
    """Devuelve el valor real de `options` que coincide con lo escrito (sin distinguir mayúsculas), o None."""
    wanted=_norm(typed)
    if not wanted:return None
    matches=[o for o in options if _norm(o)==wanted]
    exact=[o for o in matches if o==str(typed).strip()]
    return (exact or matches or [None])[0]


def is_o2c_manager_name(typed):
    return " ".join(str(typed or "").split())==O2C_MANAGER_NAME


def _resolve_access(typed,commercials,delegations):
    """Clasifica lo escrito: devuelve (tipo, valor) o (None, mensaje de error)."""
    if is_o2c_manager_name(typed):return "o2c_manager",O2C_MANAGER_NAME
    if _norm(typed)=="o2c":return "o2c",None
    commercial=resolve_option(typed,commercials);delegation=resolve_option(typed,delegations)
    if commercial and delegation:
        return None,"El nombre coincide con un comercial y una delegación; escribe el nombre completo exacto."
    if commercial:return "commercial",commercial
    if delegation:return "manager",delegation
    if not _norm(typed):return None,"Escribe un nombre para acceder."
    return None,"No se encontró ese nombre en los datos disponibles."


def _enter_access(kind,text_key,commercials,delegations,stages):
    value=None
    if kind=="search":
        kind,value=_resolve_access(st.session_state.get(text_key),commercials,delegations)
        if kind is None:
            st.session_state[ACCESS_ERROR_KEY]=value;return
    elif kind!="o2c":
        return
    # Al entrar se limpia el contexto sin rotar el widget que disparó este callback.
    _clear_context()
    if kind=="commercial":
        st.session_state[ROLE_KEY]=COMMERCIAL_ROLE;st.session_state[COMMERCIAL_KEY]=value;st.session_state[ENTERED_KEY]=True
    elif kind=="manager":
        st.session_state[ROLE_KEY]=MANAGER_ROLE;st.session_state[DELEGATION_KEY]=value;st.session_state[ENTERED_KEY]=True
    elif kind in ("o2c","o2c_manager"):
        selected=list(stages)
        st.session_state[ROLE_KEY]=O2C_ROLE if kind=="o2c" else O2C_MANAGER_ROLE;st.session_state[O2C_STAGES_KEY]=selected
        st.session_state[O2C_PRIMARY_KEY]=selected[0] if selected else None
        st.session_state[O2C_ACTIVE_KEY]="Todas mis etapas";st.session_state[ENTERED_KEY]=True
_CSS="""<style>
body:has(.st-key-vision_access_box) .block-container{max-width:1100px;padding-top:8vh}
body:has(.st-key-vision_access_box) header[data-testid="stHeader"]{background:transparent}
.v20-title{text-align:center;font-size:clamp(34px,5vw,64px);font-weight:850;color:#061331;margin:0 0 4px}.v20-title b{color:#1557ef}.v20-sub{text-align:center;color:#7585a4;font-size:18px;margin-bottom:44px}.v20-question{text-align:center;color:#07142f;font-size:25px;font-weight:700;margin-bottom:18px}.st-key-vision_access_box{max-width:780px;margin:0 auto}.st-key-vision_access_box [data-baseweb="select"]>div{min-height:58px;border-radius:14px;border-color:#cddcf5;box-shadow:0 10px 30px #2c64ee10}.st-key-vision_access_box button{min-height:54px;border-radius:13px}.v20-note{text-align:center;color:#8491a9;font-size:12px;margin-top:28px}
</style>"""


def render_role_screen(commercials,sources_ready,message=None,*,navigation_ready=False,delegations=None,stages=None):
    commercials=sorted(set(commercials or []),key=str.casefold)
    delegations=sorted(set(delegations or []),key=str.casefold);stages=list(stages or [])
    st.markdown(_CSS,unsafe_allow_html=True)
    st.markdown('<div class="v20-title">Bienvenido a <b>VISION</b></div><div class="v20-sub">La operación, las personas y el progreso, conectados.</div><div class="v20-question">¿Quién debe acceder a VISION?</div>',unsafe_allow_html=True)
    epoch=int(st.session_state.get("vision_access_epoch",0))
    error=st.session_state.get(ACCESS_ERROR_KEY)
    text_key=f"vision_access_text::{epoch}"
    with st.container(key="vision_access_box"):
        with st.form(f"vision_access_form::{epoch}",border=False):
            cols=st.columns([8,1.2],vertical_alignment="bottom",gap="small")
            with cols[0]:
                st.text_input("¿Quién debe acceder a VISION?",placeholder="Escribe un nombre: comercial, delegación, O2C...",key=text_key,label_visibility="collapsed")
            with cols[1]:
                st.form_submit_button("→",type="primary",width="stretch",on_click=_enter_access,args=("search",text_key,commercials,delegations,stages))
        if error:st.error(error)
        if not commercials:st.caption("No hay comerciales disponibles.")
        if not delegations:st.caption("No hay delegaciones disponibles.")
        st.button("Acceso O2C",key=f"vision_access_o2c::{epoch}",width="stretch",on_click=_enter_access,args=("o2c",None,commercials,delegations,stages))
    if message:st.caption(message)
