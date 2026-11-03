import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest
from vision import role_selection as rs

SCRIPT = """
import streamlit as st
from vision import role_selection as rs
args = st.session_state.get("_args", {})
if st.session_state.get(rs.ENTERED_KEY):
    st.button("exit", key="exit", on_click=rs.change_profile)
else:
    rs.render_role_screen(
        args.get("commercials", []), True,
        delegations=args.get("delegations"), stages=args.get("stages"),
    )
"""

def _app(commercials=(), delegations=(), stages=()):
    app = AppTest.from_string(SCRIPT)
    app.session_state["_args"] = {
        "commercials": list(commercials),
        "delegations": list(delegations),
        "stages": list(stages),
    }
    return app.run(timeout=30)


def _text(app, kind):
    return next(t for t in app.text_input if "vision_access_text::" in str(t.key))


def _submit(app, kind):
    return next(b for b in app.button if b.label == "→")


def _enter(app, kind, typed):
    _text(app, kind).set_value(typed)
    _submit(app, kind).click().run(timeout=30)
    return app


def _o2c(app):
    next(b for b in app.button if str(b.key).startswith("vision_access_o2c::")).click().run(timeout=30)
    return app


def test_access_screen_has_single_search_and_o2c_button():
    app = _app(["Ana"], ["Norte"], ["E1"])
    assert not app.selectbox
    assert [t.label for t in app.text_input] == ["¿Quién debe acceder a VISION?"]
    assert len([b for b in app.button if b.label == "→"]) == 1
    assert any(b.label == "Acceso O2C" for b in app.button)


def test_commercial_typed_name_sets_context_case_insensitive():
    state = _enter(_app(["Ana Pérez", "Bea"], ["Norte"], ["E1"]), "commercial", "  ana   pérez ").session_state
    assert state[rs.ROLE_KEY] == rs.COMMERCIAL_ROLE
    assert state[rs.COMMERCIAL_KEY] == "Ana Pérez"
    assert state[rs.ENTERED_KEY] is True
    assert rs.DELEGATION_KEY not in state


def test_delegation_typed_name_sets_context():
    state = _enter(_app(["Ana"], ["Barcelona", "Madrid"], ["E1"]), "manager", "madrid").session_state
    assert state[rs.ROLE_KEY] == rs.MANAGER_ROLE
    assert state[rs.DELEGATION_KEY] == "Madrid"
    assert rs.COMMERCIAL_KEY not in state


def test_o2c_enters_directly_with_all_stages():
    state = _o2c(_app(["Ana"], ["Norte"], ["E1", "E2"])).session_state
    assert state[rs.ROLE_KEY] == rs.O2C_ROLE
    assert state[rs.O2C_STAGES_KEY] == ["E1", "E2"]
    assert state[rs.O2C_PRIMARY_KEY] == "E1"
    assert state[rs.ENTERED_KEY] is True


def test_ana_feliu_enters_dedicated_global_role_with_every_stage():
    state = _enter(_app(["Ana"], ["Norte"], ["E1", "E2"]), "o2c_manager", "Ana Feliu").session_state
    assert state[rs.ROLE_KEY] == rs.O2C_MANAGER_ROLE
    assert state[rs.O2C_STAGES_KEY] == ["E1", "E2"]
    assert rs.DELEGATION_KEY not in state
    assert rs.COMMERCIAL_KEY not in state


@pytest.mark.parametrize("typed", ["ana feliu", "Ana", "Ana Feliu X", ""])
def test_ana_feliu_requires_her_exact_name(typed):
    app = _enter(_app(["Bea"], ["Norte"], ["E1"]), "o2c_manager", typed)
    assert rs.ROLE_KEY not in app.session_state


def test_unknown_name_is_rejected_without_fallback_identity():
    app = _enter(_app(["Ana"], ["Norte"], ["E1"]), "commercial", "Inventado")
    assert rs.ROLE_KEY not in app.session_state
    assert rs.COMMERCIAL_KEY not in app.session_state
    assert rs.DELEGATION_KEY not in app.session_state
    assert len(app.error) == 1


def test_empty_commercials_and_delegations_never_invent_options_and_keep_o2c():
    app = _app([], [], ["E1"])
    captions = [c.value for c in app.caption]
    assert "No hay comerciales disponibles." in captions
    assert "No hay delegaciones disponibles." in captions
    state = _o2c(app).session_state
    assert state[rs.ROLE_KEY] == rs.O2C_ROLE


def test_manager_exit_clears_every_manager_context():
    app = _enter(_app(["Ana"], ["Norte"], ["E1"]), "manager", "Norte")
    for key, value in {
        "manager_commercial::Norte": "Ana",
        "manager_report_client::Norte::Ana": "Cliente",
        "mgr_report_stages": ["E1"],
        "_manager_scope_v6": "stale",
        "_vision_manager_report_cache_v6": {"stale": 1},
        "manager_workspace_view_v20": "Informes",
        "vision_navigation": "Informes",
        "commercial_client": "Cliente",
        "comment_box::1": "texto",
    }.items():
        app.session_state[key] = value
    app.button(key="exit").click().run(timeout=30)
    state = app.session_state
    for key in ("manager_commercial::Norte", "manager_report_client::Norte::Ana", "mgr_report_stages",
                "_manager_scope_v6", "_vision_manager_report_cache_v6", "manager_workspace_view_v20",
                "vision_navigation", "commercial_client", "comment_box::1",
                rs.ROLE_KEY, rs.DELEGATION_KEY, rs.ENTERED_KEY):
        assert key not in state
    assert [t.label for t in app.text_input] == ["¿Quién debe acceder a VISION?"]
    assert all(t.value == "" for t in app.text_input)


def test_next_user_does_not_inherit_ana_feliu_context():
    app = _enter(_app(["Ana"], ["Norte"], ["E1"]), "o2c_manager", "Ana Feliu")
    app.session_state["o2c_search"] = "x"
    app.button(key="exit").click().run(timeout=30)
    assert rs.O2C_STAGES_KEY not in app.session_state and "o2c_search" not in app.session_state
    state = _enter(app, "commercial", "Ana").session_state
    assert state[rs.ROLE_KEY] == rs.COMMERCIAL_ROLE
    assert rs.O2C_STAGES_KEY not in state


def test_current_author_for_each_role(monkeypatch):
    cases = [
        ({rs.ROLE_KEY: rs.COMMERCIAL_ROLE, rs.COMMERCIAL_KEY: "Ana"}, ("Ana", rs.COMMERCIAL_ROLE)),
        ({rs.ROLE_KEY: rs.MANAGER_ROLE, rs.DELEGATION_KEY: "Norte"}, ("Manager Comercial · Norte", rs.MANAGER_ROLE)),
        ({rs.ROLE_KEY: rs.O2C_ROLE}, ("Usuario O2C", rs.O2C_ROLE)),
        ({rs.ROLE_KEY: rs.O2C_MANAGER_ROLE}, ("Ana Feliu", rs.O2C_MANAGER_ROLE)),
    ]
    for state, author in cases:
        monkeypatch.setattr(rs.st, "session_state", {**state, rs.ENTERED_KEY: True})
        assert rs.current_author() == author
    monkeypatch.setattr(rs.st, "session_state", {rs.ROLE_KEY: rs.O2C_MANAGER_ROLE, rs.ENTERED_KEY: True})
    assert rs.entered_o2c_manager() is True and rs.entered_o2c() is False


def test_o2c_can_be_typed_in_the_single_search():
    state = _enter(_app(["Ana"], ["Norte"], ["E1", "E2"]), "commercial", " o2c ").session_state
    assert state[rs.ROLE_KEY] == rs.O2C_ROLE
    assert state[rs.O2C_STAGES_KEY] == ["E1", "E2"]


def test_name_shared_by_commercial_and_delegation_is_not_guessed():
    app = _enter(_app(["Norte"], ["Norte"], ["E1"]), "commercial", "Norte")
    assert rs.ROLE_KEY not in app.session_state
    assert len(app.error) == 1
