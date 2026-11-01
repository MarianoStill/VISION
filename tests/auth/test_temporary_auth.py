import json
import re
from urllib.parse import urlencode

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from vision.auth import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    AuthConfigurationError,
    AuthenticationMiddleware,
    AuthSettings,
    Principal,
    TemporaryCookieProvider,
    auth_routes,
    hash_password,
)
from vision.authorization import AuthorizationRegistry

from tests.auth.asgi_client import request

PASSWORD = "synthetic-dev-password-2026"


@pytest.fixture
def auth_env():
    encoded = hash_password(PASSWORD)
    return {
        "VISION_AUTH_MODE": "temporary",
        "VISION_AUTH_COOKIE_SECRET": "not-a-production-secret-for-tests-123456",
        "VISION_AUTH_PUBLIC_ORIGIN": "https://vision.example.test",
        "VISION_TEMP_USERS_JSON": (
            '[{"username":"qa-commercial","password_hash":"' + encoded + '"}]'
        ),
        "VISION_AUTHZ_ASSIGNMENTS_JSON": (
            '[{"subject":"qa-commercial","role":"commercial",'
            '"scope":{"commercial":"Synthetic Commercial"}}]'
        ),
    }


@pytest.fixture
def service(auth_env):
    return TemporaryCookieProvider(AuthSettings.from_env(auth_env))


@pytest.fixture
def authorization_registry(auth_env, service):
    return AuthorizationRegistry.from_env(service.settings, auth_env)


def build_test_app(provider, registry):
    async def home(request):
        return PlainTextResponse("protected")

    async def health(request):
        return PlainTextResponse("ok")

    return Starlette(
        routes=[
            *auth_routes(provider, registry),
            Route("/", home),
            Route("/_stcore/health", health),
        ],
        middleware=[
            Middleware(
                AuthenticationMiddleware,
                service=provider,
                authorization_registry=registry,
            )
        ],
    )


def form_nonce(response):
    match = re.search(r'name="csrf" value="([^"]+)"', response.text)
    assert match
    return match.group(1)


def test_signed_session_is_server_validated_and_expires(service):
    principal = service.authenticate_password("qa-commercial", PASSWORD, now=1000)
    assert principal is not None
    token = service.issue_session(principal, now=1000)
    cookies = {SESSION_COOKIE: token}

    assert service.authenticate(cookies, now=1001) == principal
    assert (
        service.authenticate(cookies, now=1000 + service.settings.session_seconds)
        is None
    )
    assert service.authenticate({SESSION_COOKIE: token + "tampered"}, now=1001) is None
    assert service.authenticate({"vision_session": "not-a-token"}, now=1001) is None


def test_password_authentication_and_hash_requirements(service):
    assert service.authenticate_password("qa-commercial", PASSWORD) is not None
    assert service.authenticate_password("qa-commercial", "wrong password") is None
    assert service.authenticate_password("unknown", PASSWORD) is None
    with pytest.raises(ValueError):
        hash_password("short")


@pytest.mark.parametrize(
    "invalid_setting",
    [
        "missing_mode",
        "weak_secret",
        "invalid_origin",
        "malformed_users",
        "missing_assignments",
        "unsupported_role",
        "empty_scope",
    ],
)
def test_invalid_or_missing_configuration_fails_closed(auth_env, invalid_setting):
    env = auth_env.copy()
    if invalid_setting == "missing_mode":
        env.pop("VISION_AUTH_MODE")
    elif invalid_setting == "weak_secret":
        env["VISION_AUTH_COOKIE_SECRET"] = "short"
    elif invalid_setting == "invalid_origin":
        env["VISION_AUTH_PUBLIC_ORIGIN"] = "https://example.test/path"
    elif invalid_setting == "malformed_users":
        env["VISION_TEMP_USERS_JSON"] = "not-json"
    elif invalid_setting == "missing_assignments":
        env["VISION_AUTHZ_ASSIGNMENTS_JSON"] = "[]"
    elif invalid_setting == "unsupported_role":
        env["VISION_AUTHZ_ASSIGNMENTS_JSON"] = (
            '[{"subject":"qa-commercial","role":"administrator","scope":{}}]'
        )
    elif invalid_setting == "empty_scope":
        env["VISION_AUTHZ_ASSIGNMENTS_JSON"] = (
            '[{"subject":"qa-commercial","role":"commercial",'
            '"scope":{"commercial":" "}}]'
        )
    if invalid_setting in {"missing_assignments", "unsupported_role", "empty_scope"}:
        settings = AuthSettings.from_env(env)
        with pytest.raises(AuthConfigurationError):
            AuthorizationRegistry.from_env(settings, env)
    else:
        with pytest.raises(AuthConfigurationError):
            AuthSettings.from_env(env)


def test_login_issues_secure_http_only_cookie_and_protects_routes(
    service, authorization_registry
):
    app = build_test_app(service, authorization_registry)
    response = request(app, "GET", "https://vision.example.test/auth/login")
    nonce = form_nonce(response)
    assert response.headers["cache-control"] == ["no-store"]
    assert "content-security-policy" in response.headers

    response = request(
        app,
        "POST",
        "https://vision.example.test/auth/login",
        data=urlencode(
            {"csrf": nonce, "username": "qa-commercial", "password": PASSWORD}
        ).encode(),
        headers={
            "Origin": "https://vision.example.test",
            "Cookie": f"{CSRF_COOKIE}={response.cookies[CSRF_COOKIE]}",
        },
    )
    assert response.status_code == 303
    cookie = response.cookies[SESSION_COOKIE]
    session_header = next(
        value
        for value in response.headers["set-cookie"]
        if SESSION_COOKIE + "=" in value
    ).lower()
    assert "httponly" in session_header
    assert "secure" in session_header
    assert "samesite=strict" in session_header
    assert (
        request(
            app,
            "GET",
            "https://vision.example.test/",
            headers={"Cookie": f"{SESSION_COOKIE}={cookie}"},
        ).status_code
        == 200
    )
    assert (
        request(app, "GET", "https://vision.example.test/_stcore/health").text == "ok"
    )


def test_unauthorized_access_and_cross_site_login_are_rejected(
    service, authorization_registry
):
    app = build_test_app(service, authorization_registry)
    assert request(app, "GET", "https://vision.example.test/").status_code == 303
    assert (
        request(app, "GET", "https://vision.example.test/_stcore/health").status_code
        == 200
    )

    login_page = request(app, "GET", "https://vision.example.test/auth/login")
    response = request(
        app,
        "POST",
        "https://vision.example.test/auth/login",
        data=urlencode(
            {
                "csrf": form_nonce(login_page),
                "username": "qa-commercial",
                "password": PASSWORD,
            }
        ).encode(),
        headers={
            "Origin": "https://attacker.example",
            "Cookie": f"{CSRF_COOKIE}={login_page.cookies[CSRF_COOKIE]}",
        },
    )
    assert response.status_code == 403
    assert request(app, "GET", "https://vision.example.test/").status_code == 303


def test_opaque_origin_is_only_accepted_for_loopback_development(auth_env):
    env = auth_env.copy()
    env["VISION_AUTH_PUBLIC_ORIGIN"] = "http://127.0.0.1:8000"
    service = TemporaryCookieProvider(AuthSettings.from_env(env))
    registry = AuthorizationRegistry.from_env(service.settings, env)
    app = build_test_app(service, registry)
    login_page = request(app, "GET", "http://127.0.0.1:8000/auth/login")
    response = request(
        app,
        "POST",
        "http://127.0.0.1:8000/auth/login",
        data=urlencode(
            {
                "csrf": form_nonce(login_page),
                "username": "qa-commercial",
                "password": PASSWORD,
            }
        ).encode(),
        headers={
            "Origin": "null",
            "Cookie": f"{CSRF_COOKIE}={login_page.cookies[CSRF_COOKIE]}",
        },
    )
    assert response.status_code == 303


def test_logout_revokes_server_session_and_clears_cookies(
    service, authorization_registry
):
    app = build_test_app(service, authorization_registry)
    login_page = request(app, "GET", "https://vision.example.test/auth/login")
    login = request(
        app,
        "POST",
        "https://vision.example.test/auth/login",
        data=urlencode(
            {
                "csrf": form_nonce(login_page),
                "username": "qa-commercial",
                "password": PASSWORD,
            }
        ).encode(),
        headers={
            "Origin": "https://vision.example.test",
            "Cookie": f"{CSRF_COOKIE}={login_page.cookies[CSRF_COOKIE]}",
        },
    )
    token = login.cookies[SESSION_COOKIE]

    logout_page = request(
        app,
        "GET",
        "https://vision.example.test/auth/logout",
        headers={"Cookie": f"{SESSION_COOKIE}={token}"},
    )
    logout = request(
        app,
        "POST",
        "https://vision.example.test/auth/logout",
        data=urlencode({"csrf": form_nonce(logout_page)}).encode(),
        headers={
            "Origin": "https://vision.example.test",
            "Cookie": (
                f"{SESSION_COOKIE}={token}; "
                f"{CSRF_COOKIE}={logout_page.cookies[CSRF_COOKIE]}"
            ),
        },
    )
    assert logout.status_code == 303
    assert service.authenticate({SESSION_COOKIE: token}) is None
    assert request(app, "GET", "https://vision.example.test/").status_code == 303
    assert any(SESSION_COOKIE in value for value in logout.headers["set-cookie"])
    assert any(CSRF_COOKIE in value for value in logout.headers["set-cookie"])


def test_oversized_login_and_capacity_limits_fail_closed(
    service, authorization_registry, monkeypatch
):
    app = build_test_app(service, authorization_registry)
    login_page = request(app, "GET", "https://vision.example.test/auth/login")
    response = request(
        app,
        "POST",
        "https://vision.example.test/auth/login",
        data=b"x" * 8193,
        headers={
            "Origin": "https://vision.example.test",
            "Cookie": f"{CSRF_COOKIE}={login_page.cookies[CSRF_COOKIE]}",
        },
    )
    assert response.status_code == 413

    monkeypatch.setattr("vision.auth.MAX_CSRF_NONCES", 0)
    assert (
        request(app, "GET", "https://vision.example.test/auth/login").status_code == 503
    )


def test_full_session_capacity_does_not_issue_cookie(
    service, authorization_registry, monkeypatch
):
    app = build_test_app(service, authorization_registry)
    login_page = request(app, "GET", "https://vision.example.test/auth/login")
    monkeypatch.setattr("vision.auth.MAX_ACTIVE_SESSIONS", 0)
    response = request(
        app,
        "POST",
        "https://vision.example.test/auth/login",
        data=urlencode(
            {
                "csrf": form_nonce(login_page),
                "username": "qa-commercial",
                "password": PASSWORD,
            }
        ).encode(),
        headers={
            "Origin": "https://vision.example.test",
            "Cookie": f"{CSRF_COOKIE}={login_page.cookies[CSRF_COOKIE]}",
        },
    )
    assert response.status_code == 503
    assert SESSION_COOKIE not in response.cookies


def test_assignment_is_separate_from_identity_and_unknown_users_are_denied(
    service, authorization_registry
):
    principal = service.authenticate_password("qa-commercial", PASSWORD)
    assert principal is not None
    assert authorization_registry.assignment(principal).role == "commercial"
    assert authorization_registry.assignment(type(principal)("unassigned")) is None


def test_role_assignments_require_explicit_role_specific_scope():
    password_hash = hash_password(PASSWORD)
    user_rows = '[{"username":"qa","password_hash":"' + password_hash + '"}]'
    for role, scope in (
        ("commercial", {"commercial": "Synthetic Commercial"}),
        ("commercial_manager", {"delegation": "Synthetic Area"}),
        ("o2c", {"stages": ["Stage A"]}),
        ("o2c_manager_sales_director", {"stages": ["Stage B"]}),
    ):
        env = {
            "VISION_AUTH_MODE": "temporary",
            "VISION_AUTH_COOKIE_SECRET": "not-a-production-secret-for-tests-123456",
            "VISION_AUTH_PUBLIC_ORIGIN": "http://127.0.0.1:8000",
            "VISION_TEMP_USERS_JSON": user_rows,
            "VISION_AUTHZ_ASSIGNMENTS_JSON": json.dumps(
                [{"subject": "qa", "role": role, "scope": scope}]
            ),
        }
        settings = AuthSettings.from_env(env)
        registry = AuthorizationRegistry.from_env(settings, env)
        assert registry.assignment(Principal("qa")).role == role
