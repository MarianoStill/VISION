"""Sistema visual único de VISION: tokens, CSS base y cabecera común."""

from __future__ import annotations

import base64
from functools import lru_cache
from html import escape
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).parent / "assets"

# Tokens: único lugar donde se definen los colores y medidas de marca.
TOKENS = {
    "blue": "#1d4ed8",
    "blue-soft": "#e0ecff",
    "ink": "#0f172a",
    "muted": "#64748b",
    "line": "#e2e8f0",
    "page": "#f5f7fb",
    "card": "#ffffff",
    "radius": "10px",
    "shadow": "0 1px 2px rgba(15,23,42,.06)",
}

_BASE_CSS = """
:root{--v-blue:%(blue)s;--v-blue-soft:%(blue-soft)s;--v-ink:%(ink)s;--v-muted:%(muted)s;
--v-line:%(line)s;--v-page:%(page)s;--v-card:%(card)s;--v-radius:%(radius)s;--v-shadow:%(shadow)s}
.stApp{background:var(--v-page);color:var(--v-ink)}
[data-testid="stHeader"]{background:transparent;height:2.2rem}
[data-testid="stToolbar"],[data-testid="stDecoration"],footer,#MainMenu{display:none!important}
.block-container{padding-top:2.4rem;padding-bottom:2rem;max-width:1500px}
h1,h2,h3{color:var(--v-ink);letter-spacing:-.01em}
.st-key-vision_shell{background:var(--v-card);border:1px solid var(--v-line);border-radius:12px;
box-shadow:var(--v-shadow);padding:.4rem .9rem;margin-bottom:.8rem}
.v-shell{background:var(--v-card);border:1px solid var(--v-line);border-radius:12px;
box-shadow:var(--v-shadow);padding:.35rem .9rem;margin-bottom:.8rem}
.v-shell img{display:block}
.v-brand{font-size:.7rem;color:var(--v-muted);margin-top:-.1rem}
.v-ctx{font-size:.72rem;color:var(--v-muted);line-height:1.2;text-align:right}
.v-ctx b{display:block;font-size:.88rem;color:var(--v-ink)}
[data-testid="stTextInput"] input,[data-baseweb="select"]>div{border-radius:8px!important;
background:#fff!important;border-color:var(--v-line)!important}
.stButton>button{border-radius:8px;font-weight:600;border:1px solid var(--v-line)}
.stButton>button[kind="primary"]{background:var(--v-blue);border-color:var(--v-blue);color:#fff}
[data-testid="stDataFrame"]{border:1px solid var(--v-line);border-radius:var(--v-radius);
overflow:hidden;box-shadow:var(--v-shadow)}
[data-testid="stExpander"]{background:var(--v-card);border:1px solid var(--v-line)!important;
border-radius:var(--v-radius)}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] .vs-card-host){}
.vs-cm{display:flex;gap:.6rem;padding:.5rem 0;border-bottom:1px solid #eef2f7}
.vs-cm .av{flex:0 0 2rem;height:2rem;border-radius:50%%;background:var(--v-blue-soft);color:var(--v-blue);
font-weight:700;font-size:.72rem;display:flex;align-items:center;justify-content:center}
.vs-cm .hd{font-size:.8rem;color:var(--v-muted)}
.vs-cm .hd b{color:var(--v-ink)}
.vs-cm .tx{font-size:.86rem;color:var(--v-ink);white-space:pre-wrap}
"""


@lru_cache(maxsize=4)
def _logo_data(name: str) -> str:
    path = ASSETS / name
    if not path.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def logo_html(name: str, alt: str, height: int) -> str:
    source = _logo_data(name)
    if not source:
        return f"<b>{escape(alt)}</b>"
    return f'<img src="{source}" alt="{escape(alt)}" style="height:{height}px">'


def brand_html(subtitle: str = "") -> str:
    """Marca VISION: icono oficial + palabra, con el espacio de trabajo debajo."""
    mark = _logo_data("vision_header.png") or _logo_data("vision_mark.png")
    icon = f'<img src="{mark}" alt="VISION" style="height:38px;border-radius:9px">' if mark else ""
    sub = f'<div class="v-brand">{escape(subtitle)}</div>' if subtitle else ""
    return (
        '<div style="display:flex;align-items:center;gap:.6rem">'
        + icon
        + '<div><div style="font-weight:800;font-size:1.25rem;letter-spacing:.04em;'
        f'color:{TOKENS["ink"]};line-height:1.1">VISION</div>{sub}</div></div>'
    )


_LANDING_CSS = '\n<style>\nbody:has(.vision-landing-hero) .st-key-vision_shell{display:none!important}\nbody:has(.vision-landing-hero) .stApp{background:radial-gradient(ellipse at 75% 20%,#e7f0ff 0%,#f5f9ff 48%,#f8fbff 100%)}\nbody:has(.vision-landing-hero) .block-container{max-width:1600px;padding-top:2rem}\n.vl-header{display:flex;align-items:center;justify-content:space-between;background:white;border:1px solid #dfE9fa;border-radius:16px;padding:12px 24px;box-shadow:0 5px 20px #1d4ed808}\n.vl-brand{display:flex;align-items:center;gap:14px}.vl-brand img{border-radius:10px;object-fit:contain}.vl-brand strong{display:block;font-size:25px;letter-spacing:2px;color:#0b1429}.vl-brand span{display:block;color:#74839e;font-size:14px}.vl-still img{max-width:140px;object-fit:contain}\n.vl-hero{display:grid;grid-template-columns:1fr 310px;align-items:center;gap:40px;padding:52px 28px 40px}.vl-eyebrow{font-size:13px;font-weight:800;color:#1649ed;letter-spacing:1.6px;margin-bottom:20px}.vl-copy h1{font-size:clamp(32px,4.2vw,64px);line-height:1.1;letter-spacing:-2px;margin:0 0 16px;color:#071126}.vl-copy h1 em{font-style:normal;color:#1245e9}.vl-tagline{font-size:clamp(19px,2.1vw,29px);line-height:1.4;color:#344b70;margin-bottom:22px}.vl-help{font-size:17px;color:#7888a2;max-width:800px}.vl-art{display:flex;justify-content:center}.vl-art img{width:250px;height:250px!important;object-fit:contain;border-radius:42px;box-shadow:0 18px 45px #184ee325}\nbody:has(.vision-landing-hero) [class*="st-key-landing_card_"]{background:#ffffffed;border:1px solid #dce7fa;border-radius:14px;padding:22px 20px;box-shadow:0 8px 24px #234a8306;transition:transform .18s,box-shadow .18s}\nbody:has(.vision-landing-hero) [class*="st-key-landing_card_"]:hover{transform:translateY(-3px);box-shadow:0 12px 28px #234a8312}\nbody:has(.vision-landing-hero) [class*="st-key-landing_card_"] [data-testid="stCaptionContainer"]{min-height:70px;font-size:15px;line-height:1.55;color:#7585a0}\nbody:has(.vision-landing-hero) [class*="st-key-landing_card_"] button{min-height:44px;border-radius:8px}\n.vl-icon{display:flex;align-items:center;justify-content:center;width:54px;height:54px;background:#f1f6ff;color:#0758ef;border-radius:12px;font-size:30px;margin-bottom:14px}\n.vl-footer{margin-top:42px;padding:20px 0;border-top:1px solid #dfE9fa;color:#7a8ba6;font-size:13px;text-align:center}\n@media(max-width:850px){.vl-hero{grid-template-columns:1fr;padding:30px 10px}.vl-art{display:none}.vl-header{padding:12px}.vl-brand span{font-size:11px}.vl-copy h1{letter-spacing:-1px}}\n@media(prefers-reduced-motion:reduce){body:has(.vision-landing-hero) [class*="st-key-landing_card_"]{transition:none;transform:none}}\n</style>\n'

def render_hero(subtitle: str = "Connecting operations, people and progress") -> None:
    """Portada VISION; estilos limitados a esta pantalla."""
    st.markdown(_LANDING_CSS, unsafe_allow_html=True)
    mark = logo_html("vision_mark.png", "VISION", 46)
    still = logo_html("still_logo.png", "STILL", 38)
    full = logo_html("vision_logo_full.png", "VISION", 250)
    st.markdown(
        '<div class="vision-landing-hero">'
        '<div class="vl-header"><div class="vl-brand">' + mark +
        '<div><strong>VISION</strong><span>Operaciones, personas y progreso</span></div></div>' +
        '<div class="vl-still">' + still + '</div></div>'
        '<div class="vl-hero"><div class="vl-copy">'
        '<div class="vl-eyebrow">TU ESPACIO DE TRABAJO</div>'
        '<h1>Bienvenido a <em>VISION</em></h1>'
        '<p class="vl-tagline">La operación, las personas y el progreso, conectados.</p>'
        '<p class="vl-help">Selecciona tu perfil para acceder a la información y herramientas de tu función.</p>'
        '</div><div class="vl-art">' + full + '</div></div></div>',
        unsafe_allow_html=True,
    )



def inject() -> None:
    """CSS base común; los componentes (tarjetas, badges, timelines) viven en commercial_workspace."""
    st.markdown("<style>" + (_BASE_CSS % TOKENS).replace("\n", "") + "</style>", unsafe_allow_html=True)


_WORKSPACE_HEADER_CSS = '<style>\n.st-key-vision_shell{background:#fff;border:1px solid #dce7fa;border-radius:14px;padding:12px 18px;margin-bottom:20px;box-shadow:0 5px 18px #1b4c9b08}\n.st-key-vision_shell button{min-height:42px;border-radius:9px;border-color:#e0e8f5;font-size:13px;font-weight:600}\n.v4-context{text-align:right;line-height:1.2}.v4-context strong{display:block;font-size:clamp(18px,2vw,29px);font-weight:800;color:#0b1734;overflow-wrap:anywhere}.v4-context span{display:block;font-size:13px;color:#6c80a3;margin-top:5px;overflow-wrap:anywhere}.v4-still{text-align:right;border-left:1px solid #dce7fa;padding-left:14px}.v4-still img{max-width:100%;object-fit:contain}\n@media(max-width:800px){.st-key-vision_shell{padding:10px}.v4-context{text-align:left}.v4-still{border-left:0;padding-left:0}}\n</style>'

def render_shell(
    *,
    pages: list[str] | None = None,
    searchable: bool = False,
    context: tuple[str, str] | None = None,
    on_change_profile=None,
    workspace: str = "",
) -> tuple[str | None, str]:
    """Cabecera compacta. El cierre usa el callback de contexto existente."""
    page = None
    st.markdown(_WORKSPACE_HEADER_CSS + '\n<style>\nbody:has(.st-key-vision_shell):not(:has(.vision-landing-hero)) .block-container{max-width:1920px;padding-left:2rem;padding-right:2rem}\n.st-key-vision_shell{width:100%;box-sizing:border-box;padding:16px 20px}\n.st-key-vision_shell .v4-context strong{font-size:clamp(18px,1.8vw,29px);line-height:1.2;overflow-wrap:normal}\n.st-key-vision_shell button{white-space:nowrap;padding-left:10px;padding-right:10px}\n.st-key-vision_shell button[kind="primary"]{background:#1d4ed8;color:white;border-color:#1d4ed8;box-shadow:inset 0 2px 5px #102b7a55}\n.st-key-vision_shell button[kind="secondary"]{background:#fff;color:#23416b;box-shadow:none}\n@media(max-width:1000px){body:has(.st-key-vision_shell):not(:has(.vision-landing-hero)) .block-container{padding-left:1rem;padding-right:1rem}.st-key-vision_shell{padding:12px}}\n@media(max-width:760px){.st-key-vision_shell [data-testid="stHorizontalBlock"]{flex-wrap:wrap}.st-key-vision_shell [data-testid="stColumn"]{min-width:140px;flex:1 1 180px}}\n</style>\n', unsafe_allow_html=True)
    allowed = [p for p in (pages or []) if p != "Inicio"]
    if allowed:
        current = st.session_state.get("vision_navigation")
        if current not in allowed:
            st.session_state["vision_navigation"] = allowed[0]
        page = st.session_state["vision_navigation"]
    def choose_page(value):
        st.session_state["vision_navigation"] = value
    with st.container(key="vision_shell"):
        columns = st.columns([2.6, 2.5, 1.65, 3.0, 1.15], gap="small", vertical_alignment="center")
        with columns[0]:
            st.markdown(brand_html(workspace), unsafe_allow_html=True)
        with columns[1]:
            if "Informes" in allowed:
                machine_page = "Mis clientes" if "Mis clientes" in allowed else allowed[0]
                nav = st.columns(2, gap="small")
                with nav[0]:
                    st.button("Máquinas", key="vision_nav_machines",
                              type="primary" if page == machine_page else "secondary",
                              on_click=choose_page, args=(machine_page,), width="stretch")
                with nav[1]:
                    st.button("Informes", key="vision_nav_reports",
                              type="primary" if page == "Informes" else "secondary",
                              on_click=choose_page, args=("Informes",), width="stretch")
        with columns[2]:
            if on_change_profile is not None:
                st.button("Cambiar acceso", key="change_profile",
                          on_click=on_change_profile, width="stretch",
                          help="Finaliza el contexto de trabajo y vuelve a la selección de acceso.")
        with columns[3]:
            if context:
                st.markdown(
                    '<div class="v4-context"><strong>' + escape(str(context[0])) +
                    '</strong><span>' + escape(str(context[1])) + '</span></div>',
                    unsafe_allow_html=True,
                )
        with columns[4]:
            st.markdown('<div class="v4-still">' +
                        logo_html("still_logo.png", "STILL", 40) + '</div>',
                        unsafe_allow_html=True)
    return page, ""
