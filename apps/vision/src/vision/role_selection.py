from __future__ import annotations
import streamlit as st

ROLE_KEY="vision_role";COMMERCIAL_KEY="vision_commercial";ENTERED_KEY="vision_entered";ADMIN_KEY="admin_data_mode"
COMMERCIAL_ROLE="Comercial";MANAGER_ROLE="Manager Comercial";O2C_ROLE="O2C"
DELEGATION_KEY="vision_delegation";O2C_STAGES_KEY="o2c_stages";O2C_PRIMARY_KEY="o2c_primary";O2C_ACTIVE_KEY="o2c_active"
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
    subject=st.session_state.get("vision_authenticated_subject")
    if subject:
        return subject, role
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


def bind_authenticated_profile(subject, role, scope):
    _clear_context()
    st.session_state[ADMIN_KEY] = False
    st.session_state["vision_authenticated_subject"] = subject
    st.session_state[ENTERED_KEY] = True
    if role == "commercial":
        st.session_state[ROLE_KEY] = COMMERCIAL_ROLE
        st.session_state[COMMERCIAL_KEY] = scope["commercial"]
    elif role == "commercial_manager":
        st.session_state[ROLE_KEY] = MANAGER_ROLE
        st.session_state[DELEGATION_KEY] = scope["delegation"]
    else:
        stages = list(scope["stages"])
        st.session_state[ROLE_KEY] = O2C_ROLE
        st.session_state[O2C_STAGES_KEY] = stages
        st.session_state[O2C_PRIMARY_KEY] = stages[0]
        st.session_state[O2C_ACTIVE_KEY] = "Todas mis etapas"


def change_profile():
    _clear_context()
    # Fuerza una nueva instancia de los widgets de acceso en el navegador.
    st.session_state["vision_access_epoch"] = int(st.session_state.get("vision_access_epoch",0)) + 1


def _enter_access(entries,stages,access_key):
    label=st.session_state.get(access_key)
    entry=entries.get(label)
    if not entry:return
    kind,value=entry
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
    elif kind=="admin":
        st.session_state[ADMIN_KEY]=True;st.session_state[ENTERED_KEY]=False


_CSS="""<style>
body:has(.st-key-vision_access_box) .block-container{max-width:1100px;padding-top:8vh}
body:has(.st-key-vision_access_box) header[data-testid="stHeader"]{background:transparent}
.v20-title{text-align:center;font-size:clamp(34px,5vw,64px);font-weight:850;color:#061331;margin:0 0 4px}.v20-title b{color:#1557ef}.v20-sub{text-align:center;color:#7585a4;font-size:18px;margin-bottom:44px}.v20-question{text-align:center;color:#07142f;font-size:25px;font-weight:700;margin-bottom:18px}.st-key-vision_access_box{max-width:780px;margin:0 auto}.st-key-vision_access_box [data-baseweb="select"]>div{min-height:58px;border-radius:14px;border-color:#cddcf5;box-shadow:0 10px 30px #2c64ee10}.st-key-vision_access_box button{min-height:54px;border-radius:13px}.v20-note{text-align:center;color:#8491a9;font-size:12px;margin-top:28px}
</style>"""


def render_role_screen(commercials,sources_ready,message=None,*,navigation_ready=False,delegations=None,stages=None):
    delegations=list(delegations or []);stages=list(stages or [])
    st.markdown(_CSS,unsafe_allow_html=True)
    st.markdown('<div class="v20-title">Bienvenido a <b>VISION</b></div><div class="v20-sub">La operación, las personas y el progreso, conectados.</div><div class="v20-question">¿Quién va a iniciar sesión?</div>',unsafe_allow_html=True)
    entries={}
    for name in sorted(set(commercials),key=str.casefold):entries[name]=("commercial",name)
    for delegation in sorted(set(delegations),key=str.casefold):entries[f"{delegation} Manager"]=("manager",delegation)
    entries["O2C"]=("o2c",None);entries["Administrator"]=("admin",None)
    options=list(entries)
    epoch=int(st.session_state.get("vision_access_epoch",0))
    access_key=f"vision_access_picker::{epoch}"
    enter_key=f"vision_access_enter::{epoch}"
    with st.container(key="vision_access_box"):
        cols=st.columns([8,1.2],vertical_alignment="bottom",gap="small")
        with cols[0]:
            st.selectbox("Acceso",options,index=None,placeholder="Escribe tu nombre o acceso...",key=access_key,label_visibility="collapsed")
        with cols[1]:
            st.button("→",key=enter_key,type="primary",width="stretch",disabled=not st.session_state.get(access_key),on_click=_enter_access,args=(entries,stages,access_key))
    if message:st.caption(message)
