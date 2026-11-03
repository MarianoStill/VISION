from __future__ import annotations
import streamlit as st

ROLE_KEY="vision_role";COMMERCIAL_KEY="vision_commercial";ENTERED_KEY="vision_entered";ADMIN_KEY="admin_data_mode"
COMMERCIAL_ROLE="Comercial";MANAGER_ROLE="Manager Comercial";O2C_ROLE="O2C"
DELEGATION_KEY="vision_delegation";O2C_STAGES_KEY="o2c_stages";O2C_PRIMARY_KEY="o2c_primary";O2C_ACTIVE_KEY="o2c_active"
ACCESS_CATEGORY_KEY="vision_access_category";ACCESS_VALUE_KEY="vision_access_value"
COMMERCIAL_ACCESS="Comercial";DELEGATION_ACCESS="Delegación";O2C_ACCESS="O2C"
_PROFILE_KEYS=(ROLE_KEY,COMMERCIAL_KEY,DELEGATION_KEY,ENTERED_KEY)


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
    return None


def _clear_context():
    exact=set(_PROFILE_KEYS)|{ADMIN_KEY,"vision_navigation",O2C_STAGES_KEY,O2C_PRIMARY_KEY,O2C_ACTIVE_KEY,"o2c_stage_options","manager_workspace_view_v20"}
    prefixes=("manager_","mgr_report_","o2c_","commercial_","comment_box::","comment_error::","comment_send::")
    for key in list(st.session_state):
        if key in exact or str(key).startswith(prefixes):
            st.session_state.pop(key,None)


def change_profile():
    _clear_context()
    # Fuerza una nueva instancia de los widgets de acceso en el navegador.
    st.session_state["vision_access_epoch"] = int(st.session_state.get("vision_access_epoch",0)) + 1


def _enter_access(commercials,delegations,stages,category_key,value_key):
    category=st.session_state.get(category_key)
    value=st.session_state.get(value_key)
    if category==COMMERCIAL_ACCESS and value in commercials:
        kind="commercial"
    elif category==DELEGATION_ACCESS and value in delegations:
        kind="manager"
    elif category==O2C_ACCESS:
        kind="o2c"
    else:
        return
    # Al entrar se limpia el contexto sin rotar el widget que disparó este callback.
    _clear_context()
    if kind=="commercial":
        st.session_state[ROLE_KEY]=COMMERCIAL_ROLE;st.session_state[COMMERCIAL_KEY]=value;st.session_state[ENTERED_KEY]=True
    elif kind=="manager":
        st.session_state[ROLE_KEY]=MANAGER_ROLE;st.session_state[DELEGATION_KEY]=value;st.session_state[ENTERED_KEY]=True
    elif kind=="o2c":
        selected=list(stages)
        st.session_state[ROLE_KEY]=O2C_ROLE;st.session_state[O2C_STAGES_KEY]=selected
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
    st.markdown('<div class="v20-title">Bienvenido a <b>VISION</b></div><div class="v20-sub">La operación, las personas y el progreso, conectados.</div><div class="v20-question">¿Cómo quieres acceder?</div>',unsafe_allow_html=True)
    epoch=int(st.session_state.get("vision_access_epoch",0))
    category_key=f"{ACCESS_CATEGORY_KEY}::{epoch}"
    enter_key=f"vision_access_enter::{epoch}"
    categories=[COMMERCIAL_ACCESS,DELEGATION_ACCESS,O2C_ACCESS]
    with st.container(key="vision_access_box"):
        cols=st.columns([8,1.2],vertical_alignment="bottom",gap="small")
        with cols[0]:
            category=st.selectbox("Tipo de acceso",categories,index=None,placeholder="Selecciona un acceso...",key=category_key,label_visibility="collapsed")
            value_key=f"{ACCESS_VALUE_KEY}::{category or 'none'}::{epoch}"
            options=[]
            if category==COMMERCIAL_ACCESS:
                options=commercials
                if options:
                    st.selectbox("Comercial",options,index=None,placeholder="Selecciona un comercial...",key=value_key)
                else:
                    st.info("No hay comerciales disponibles.")
            elif category==DELEGATION_ACCESS:
                options=delegations
                if options:
                    st.selectbox("Delegación",options,index=None,placeholder="Selecciona una delegación...",key=value_key)
                else:
                    st.info("No hay delegaciones disponibles.")
        with cols[1]:
            can_enter=category==O2C_ACCESS or bool(st.session_state.get(value_key) in options)
            st.button("→",key=enter_key,type="primary",width="stretch",disabled=not can_enter,on_click=_enter_access,args=(commercials,delegations,stages,category_key,value_key))
    if message:st.caption(message)
