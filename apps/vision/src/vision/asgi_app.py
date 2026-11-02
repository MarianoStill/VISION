from pathlib import Path

import streamlit as st
from starlette.middleware import Middleware

from vision.auth import (
    AuthenticationMiddleware,
    auth_routes,
    runtime_authorization_registry,
    runtime_provider,
)


def create_app(provider=None, authorization_registry=None, auth_routes_override=None):
    auth_provider = provider or runtime_provider()
    registry = authorization_registry or runtime_authorization_registry()
    routes = (
        auth_routes(auth_provider, registry)
        if auth_routes_override is None
        else auth_routes_override
    )
    return st.App(
        str(Path(__file__).with_name("development_app.py")),
        routes=routes,
        middleware=[
            Middleware(
                AuthenticationMiddleware,
                service=auth_provider,
                authorization_registry=registry,
                invalid_cookie_settings=getattr(auth_provider, "settings", None),
            )
        ],
    )


app = create_app()
