import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest
from vision import role_selection as rs

SCRIPT = """
import streamlit as st
from vision import role_selection as rs
args = st.session_state.get("_args", {})
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


def _choose_category(app, category):
    app.selectbox[0].select(category).run(timeout=30)
    return app


def _enter(app, category, value=None):
    _choose_category(app, category)
    if value is not None:
        app.selectbox[1].select(value).run(timeout=30)
    app.button[0].click().run(timeout=30)
    return app


def test_category_options_are_original_three():
    app = _app(["Ana"], ["Norte"], ["E1"])
    assert list(app.selectbox[0].options) == ["Comercial", "Delegación", "O2C"]


def test_commercial_selection_sets_context():
    state = _enter(_app(["Ana", "Bea"], ["Norte"], ["E1"]), "Comercial", "Ana").session_state
    assert state[rs.ROLE_KEY] == rs.COMMERCIAL_ROLE
    assert state[rs.COMMERCIAL_KEY] == "Ana"
    assert state[rs.ENTERED_KEY] is True
    assert rs.DELEGATION_KEY not in state
    assert rs.O2C_STAGES_KEY not in state


def test_delegation_selection_sets_context():
    state = _enter(_app(["Ana"], ["Norte", "Sur"], ["E1"]), "Delegación", "Sur").session_state
    assert state[rs.ROLE_KEY] == rs.MANAGER_ROLE
    assert state[rs.DELEGATION_KEY] == "Sur"
    assert state[rs.ENTERED_KEY] is True
    assert rs.COMMERCIAL_KEY not in state


def test_o2c_selection_sets_context():
    state = _enter(_app(["Ana"], ["Norte"], ["E1", "E2"]), "O2C").session_state
    assert state[rs.ROLE_KEY] == rs.O2C_ROLE
    assert state[rs.O2C_STAGES_KEY] == ["E1", "E2"]
    assert state[rs.O2C_PRIMARY_KEY] == "E1"
    assert state[rs.O2C_ACTIVE_KEY] == "Todas mis etapas"
    assert state[rs.ENTERED_KEY] is True
    assert rs.COMMERCIAL_KEY not in state
    assert rs.DELEGATION_KEY not in state


def test_commercial_requires_value_before_enter():
    app = _choose_category(_app(["Ana"], ["Norte"], ["E1"]), "Comercial")
    assert app.button[0].disabled
    assert not app.session_state[rs.ENTERED_KEY] if rs.ENTERED_KEY in app.session_state else True


def test_empty_commercials_preserve_other_options():
    app = _app([], ["Norte"], ["E1"])
    assert list(app.selectbox[0].options) == ["Comercial", "Delegación", "O2C"]
    _choose_category(app, "Comercial")
    assert len(app.selectbox) == 1
    assert [i.value for i in app.info] == ["No hay comerciales disponibles."]
    assert app.button[0].disabled
    _enter(app, "O2C")
    assert app.session_state[rs.ROLE_KEY] == rs.O2C_ROLE


def test_empty_delegations_preserve_o2c():
    app = _app(["Ana"], [], ["E1"])
    _choose_category(app, "Delegación")
    assert len(app.selectbox) == 1
    assert [i.value for i in app.info] == ["No hay delegaciones disponibles."]
    assert app.button[0].disabled
    _enter(app, "O2C")
    assert app.session_state[rs.ROLE_KEY] == rs.O2C_ROLE
    assert app.session_state[rs.O2C_STAGES_KEY] == ["E1"]


def test_both_empty_still_allow_o2c_without_stages():
    state = _enter(_app([], [], []), "O2C").session_state
    assert state[rs.ROLE_KEY] == rs.O2C_ROLE
    assert state[rs.O2C_STAGES_KEY] == []
    assert state[rs.O2C_PRIMARY_KEY] is None


@pytest.mark.parametrize(
    "category, value, author",
    [
        ("Comercial", "Ana", ("Ana", rs.COMMERCIAL_ROLE)),
        ("Delegación", "Norte", ("Manager Comercial · Norte", rs.MANAGER_ROLE)),
        ("O2C", None, ("Usuario O2C", rs.O2C_ROLE)),
    ],
)
def test_helpers_reflect_selected_context(category, value, author, monkeypatch):
    app = _enter(_app(["Ana"], ["Norte"], ["E1"]), category, value)
    keys = (rs.ROLE_KEY, rs.ENTERED_KEY, rs.COMMERCIAL_KEY, rs.DELEGATION_KEY)
    state = {k: app.session_state[k] for k in keys if k in app.session_state}
    monkeypatch.setattr(rs.st, "session_state", state)
    assert rs.current_author() == author
    assert rs.entered_commercial() == (value if category == "Comercial" else None)
    assert rs.entered_manager() == (value if category == "Delegación" else None)
    assert rs.entered_o2c() is (category == "O2C")