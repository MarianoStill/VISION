import pytest
import streamlit as st
from vision.auth import AuthConfigurationError, AuthSettings


def test_deployment_entrypoint_is_streamlit_asgi_app(monkeypatch):
    monkeypatch.setenv("VISION_AUTH_MODE", "temporary")
    monkeypatch.setenv(
        "VISION_AUTH_COOKIE_SECRET", "test-only-signing-secret-with-32-bytes-minimum"
    )
    monkeypatch.setenv("VISION_AUTH_PUBLIC_ORIGIN", "https://vision.example.test")
    monkeypatch.setenv(
        "VISION_TEMP_USERS_JSON",
        '[{"username":"qa","password_hash":"pbkdf2_sha256$600000$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}]',
    )
    monkeypatch.setenv(
        "VISION_AUTHZ_ASSIGNMENTS_JSON",
        '[{"subject":"qa","role":"commercial","scope":{"commercial":"Synthetic"}}]',
    )
    from vision.asgi_app import create_app

    app = create_app()
    assert isinstance(app, st.App)


def test_deployment_entrypoint_fails_closed_without_auth_settings(monkeypatch):
    for name in (
        "VISION_AUTH_MODE",
        "VISION_AUTH_COOKIE_SECRET",
        "VISION_AUTH_PUBLIC_ORIGIN",
        "VISION_TEMP_USERS_JSON",
        "VISION_AUTHZ_ASSIGNMENTS_JSON",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(AuthConfigurationError):
        AuthSettings.from_env()
