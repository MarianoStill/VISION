import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest


def test_authenticated_binding_clears_previous_users_context():
    app = AppTest.from_string(
        """
import streamlit as st
from vision import role_selection

role_selection.bind_authenticated_profile(
    "qa-first", "commercial", {"commercial": "Synthetic Commercial A"}
)
st.session_state["o2c_unknown_v16"] = True
st.session_state["comment_box::synthetic-machine"] = "private note from first user"
role_selection.bind_authenticated_profile(
    "qa-second", "o2c", {"stages": ("Synthetic Stage B",)}
)
"""
    ).run()

    assert not app.exception
    assert app.session_state["vision_authenticated_subject"] == "qa-second"
    assert app.session_state["vision_role"] == "O2C"
    assert app.session_state["o2c_stages"] == ["Synthetic Stage B"]
    assert "vision_commercial" not in app.session_state
    assert "o2c_unknown_v16" not in app.session_state
    assert "comment_box::synthetic-machine" not in app.session_state
