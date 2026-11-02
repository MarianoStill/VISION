from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass
from http.cookies import CookieError, SimpleCookie
from typing import Protocol
from urllib.parse import parse_qs, urlsplit

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

SESSION_COOKIE = "vision_session"
CSRF_COOKIE = "vision_csrf"
SESSION_SECONDS = 8 * 60 * 60
CSRF_SECONDS = 10 * 60
PASSWORD_ITERATIONS = 600_000
MAX_ACTIVE_SESSIONS = 5_000
MAX_CSRF_NONCES = 10_000
ROLES = {
    "commercial": "commercial",
    "commercial_manager": "delegation",
    "o2c": "stages",
    "o2c_manager_sales_director": "stages",
}
_SUBJECT = re.compile(r"^[A-Za-z0-9._@+-]{1,128}$")


class AuthConfigurationError(ValueError):
    pass


class AuthCapacityError(RuntimeError):
    pass


@dataclass(frozen=True)
class Principal:
    subject: str


@dataclass(frozen=True)
class IdentityRequest:
    headers: dict[str, str]
    cookies: dict[str, str]


@dataclass(frozen=True)
class RoleAssignment:
    role: str
    scope: dict[str, str | tuple[str, ...]]


@dataclass(frozen=True)
class AuthSettings:
    secret: bytes
    public_origin: str
    users: dict[str, tuple[str, int, bytes, bytes]]
    session_seconds: int = SESSION_SECONDS

    @property
    def secure_cookie(self) -> bool:
        return urlsplit(self.public_origin).scheme == "https"

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> AuthSettings:
        values = os.environ if environ is None else environ
        if values.get("VISION_AUTH_MODE") != "temporary":
            raise AuthConfigurationError("VISION_AUTH_MODE must be 'temporary'.")
        secret_text = values.get("VISION_AUTH_COOKIE_SECRET", "")
        secret = secret_text.encode("utf-8")
        if len(secret) < 32:
            raise AuthConfigurationError(
                "VISION_AUTH_COOKIE_SECRET must be at least 32 bytes."
            )
        origin = values.get("VISION_AUTH_PUBLIC_ORIGIN", "").rstrip("/")
        parsed_origin = urlsplit(origin)
        if (
            not origin
            or parsed_origin.scheme not in {"https", "http"}
            or not parsed_origin.netloc
            or parsed_origin.path
            or parsed_origin.query
            or parsed_origin.fragment
            or parsed_origin.username
            or parsed_origin.password
        ):
            raise AuthConfigurationError(
                "VISION_AUTH_PUBLIC_ORIGIN must be an absolute origin."
            )
        if parsed_origin.scheme == "http" and parsed_origin.hostname not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise AuthConfigurationError(
                "Non-loopback temporary authentication requires HTTPS."
            )
        try:
            user_rows = json.loads(values["VISION_TEMP_USERS_JSON"])
        except (KeyError, json.JSONDecodeError) as exc:
            raise AuthConfigurationError("Temporary users are required JSON.") from exc
        users = _parse_users(user_rows)
        try:
            session_seconds = int(
                values.get("VISION_AUTH_SESSION_SECONDS", SESSION_SECONDS)
            )
        except ValueError as exc:
            raise AuthConfigurationError(
                "VISION_AUTH_SESSION_SECONDS must be an integer."
            ) from exc
        if not 300 <= session_seconds <= 86_400:
            raise AuthConfigurationError(
                "Session lifetime must be between 300 and 86400 seconds."
            )
        return cls(secret, origin, users, session_seconds)


def _parse_users(rows: object) -> dict[str, tuple[str, int, bytes, bytes]]:
    if not isinstance(rows, list) or not rows:
        raise AuthConfigurationError("At least one temporary user must be configured.")
    parsed: dict[str, tuple[str, int, bytes, bytes]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise AuthConfigurationError("Temporary user entries must be objects.")
        subject = row.get("username")
        if not isinstance(subject, str) or not _SUBJECT.fullmatch(subject):
            raise AuthConfigurationError(
                "Temporary usernames must be short, stable identifiers."
            )
        key = subject.casefold()
        if key in parsed:
            raise AuthConfigurationError(
                "Temporary usernames must be unique, ignoring case."
            )
        password_hash = row.get("password_hash")
        if not isinstance(password_hash, str):
            raise AuthConfigurationError(
                "Each temporary user requires a password hash."
            )
        fields = password_hash.split("$")
        if len(fields) != 4 or fields[0] != "pbkdf2_sha256":
            raise AuthConfigurationError(
                "Password hashes must use the pbkdf2_sha256 format."
            )
        try:
            iterations = int(fields[1])
            salt = _b64decode(fields[2])
            digest = _b64decode(fields[3])
        except (ValueError, TypeError) as exc:
            raise AuthConfigurationError(
                "A temporary user has an invalid password hash."
            ) from exc
        if (
            iterations < PASSWORD_ITERATIONS
            or iterations > 5_000_000
            or len(salt) < 16
            or len(digest) != 32
        ):
            raise AuthConfigurationError(
                "Password hashes require strong PBKDF2 parameters."
            )
        parsed[key] = (subject, iterations, salt, digest)
    return parsed


def _parse_assignments(rows: object) -> dict[str, RoleAssignment]:
    if not isinstance(rows, list) or not rows:
        raise AuthConfigurationError(
            "At least one authorization assignment must be configured."
        )
    parsed: dict[str, RoleAssignment] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise AuthConfigurationError(
                "Authorization assignment entries must be objects."
            )
        subject = row.get("subject")
        role = row.get("role")
        scope = row.get("scope")
        if not isinstance(subject, str) or not _SUBJECT.fullmatch(subject):
            raise AuthConfigurationError(
                "Authorization subjects must match configured usernames."
            )
        key = subject.casefold()
        if key in parsed:
            raise AuthConfigurationError(
                "Each user must have a single authorization assignment."
            )
        expected_scope = ROLES.get(role) if isinstance(role, str) else None
        if (
            expected_scope is None
            or not isinstance(scope, dict)
            or set(scope) != {expected_scope}
        ):
            raise AuthConfigurationError("The role or role-specific scope is invalid.")
        raw_scope = scope[expected_scope]
        if expected_scope == "stages":
            if (
                not isinstance(raw_scope, list)
                or not raw_scope
                or any(
                    not isinstance(value, str) or not value.strip()
                    for value in raw_scope
                )
                or len({value.casefold() for value in raw_scope}) != len(raw_scope)
            ):
                raise AuthConfigurationError(
                    "O2C assignments require unique, explicit stage scopes."
                )
            normalized_scope: str | tuple[str, ...] = tuple(raw_scope)
        else:
            if not isinstance(raw_scope, str) or not raw_scope.strip():
                raise AuthConfigurationError(
                    "Commercial assignments require an explicit data scope."
                )
            normalized_scope = raw_scope
        parsed[key] = RoleAssignment(role, {expected_scope: normalized_scope})
    return parsed


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.b64decode(
        value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
    )


def hash_password(password: str) -> str:
    if len(password) < 14:
        raise ValueError("Temporary passwords must contain at least 14 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return (
        f"pbkdf2_sha256${PASSWORD_ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"
    )


class IdentityProvider(Protocol):
    def authenticate(self, request: IdentityRequest) -> Principal | None: ...


class TemporaryCookieProvider:
    """Local identity proof only; permissions are resolved separately."""

    def __init__(self, settings: AuthSettings):
        self.settings = settings
        self._active_sessions: dict[str, int] = {}
        self._csrf_nonces: dict[str, int] = {}
        self._failed_logins: dict[str, tuple[int, int]] = {}
        self._lock = threading.RLock()

    def authenticate_password(
        self, subject: str, password: str, now: int | None = None
    ) -> Principal | None:
        current = int(time.time()) if now is None else now
        key = subject.casefold()
        with self._lock:
            _, blocked_until = self._failed_logins.get(key, (0, 0))
        if blocked_until > current:
            return None
        user = self.settings.users.get(key)
        if user is None:
            # Keep the unknown-user path close to the configured PBKDF2 cost.
            hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), bytes(16), PASSWORD_ITERATIONS
            )
            return None
        username, iterations, salt, expected = user
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations
        )
        if not hmac.compare_digest(actual, expected):
            self._record_failure(key, current)
            return None
        with self._lock:
            self._failed_logins.pop(key, None)
        return Principal(username)

    def _record_failure(self, key: str, now: int) -> None:
        with self._lock:
            count, blocked_until = self._failed_logins.get(key, (0, 0))
            count = count + 1 if blocked_until <= now else count
            self._failed_logins[key] = (count, now + 300 if count >= 10 else 0)

    def issue_session(self, principal: Principal, now: int | None = None) -> str:
        current = int(time.time()) if now is None else now
        subject_key = principal.subject.casefold()
        user = self.settings.users.get(subject_key)
        if user is None:
            raise ValueError("Cannot issue a session without an assigned user.")
        payload = {
            "iss": "vision-temporary-auth",
            "aud": "vision",
            "sub": user[0],
            "iat": current,
            "exp": current + self.settings.session_seconds,
            "jti": secrets.token_urlsafe(24),
        }
        encoded = _b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        signature = hmac.new(
            self.settings.secret, encoded.encode("ascii"), hashlib.sha256
        ).digest()
        token = f"{encoded}.{_b64encode(signature)}"
        with self._lock:
            self._active_sessions = {
                session_id: expiry
                for session_id, expiry in self._active_sessions.items()
                if expiry > current
            }
            if len(self._active_sessions) >= MAX_ACTIVE_SESSIONS:
                raise AuthCapacityError("Temporary session capacity is full.")
            self._active_sessions[payload["jti"]] = payload["exp"]
        return token

    def authenticate(
        self,
        request: IdentityRequest | dict[str, str],
        now: int | None = None,
    ) -> Principal | None:
        cookies = request.cookies if isinstance(request, IdentityRequest) else request
        token = cookies.get(SESSION_COOKIE)
        if not isinstance(token, str) or len(token) > 4096:
            return None
        try:
            encoded, signature_text = token.split(".", 1)
            signature = _b64decode(signature_text)
            expected = hmac.new(
                self.settings.secret, encoded.encode("ascii"), hashlib.sha256
            ).digest()
            if not hmac.compare_digest(signature, expected):
                return None
            payload = json.loads(_b64decode(encoded))
            current = int(time.time()) if now is None else now
            if (
                payload.get("iss") != "vision-temporary-auth"
                or payload.get("aud") != "vision"
                or not isinstance(payload.get("sub"), str)
                or not isinstance(payload.get("iat"), int)
                or not isinstance(payload.get("exp"), int)
                or not isinstance(payload.get("jti"), str)
                or payload["iat"] > current + 30
                or payload["exp"] <= current
                or payload["exp"] - payload["iat"] > self.settings.session_seconds
            ):
                return None
            key = payload["sub"].casefold()
            user = self.settings.users.get(key)
            if user is None or user[0] != payload["sub"]:
                return None
            with self._lock:
                expiry = self._active_sessions.get(payload["jti"])
                if expiry != payload["exp"] or expiry <= current:
                    return None
            return Principal(payload["sub"])
        except (
            ValueError,
            TypeError,
            KeyError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            return None

    def revoke(self, cookies: dict[str, str], now: int | None = None) -> None:
        token = cookies.get(SESSION_COOKIE)
        principal = self.authenticate(cookies, now)
        if principal is None or token is None:
            return
        try:
            payload = json.loads(_b64decode(token.split(".", 1)[0]))
        except (ValueError, TypeError, json.JSONDecodeError):
            return
        with self._lock:
            self._active_sessions.pop(payload.get("jti"), None)

    def create_csrf_nonce(self, now: int | None = None) -> str:
        current = int(time.time()) if now is None else now
        nonce = secrets.token_urlsafe(32)
        with self._lock:
            self._csrf_nonces = {
                key: expiry
                for key, expiry in self._csrf_nonces.items()
                if expiry > current
            }
            if len(self._csrf_nonces) >= MAX_CSRF_NONCES:
                raise AuthCapacityError(
                    "Temporary authentication request capacity is full."
                )
            self._csrf_nonces[hashlib.sha256(nonce.encode()).hexdigest()] = (
                current + CSRF_SECONDS
            )
        return nonce

    def consume_csrf_nonce(
        self, nonce: str, cookie_nonce: str, now: int | None = None
    ) -> bool:
        current = int(time.time()) if now is None else now
        if (
            not nonce
            or not cookie_nonce
            or not hmac.compare_digest(nonce, cookie_nonce)
        ):
            return False
        key = hashlib.sha256(nonce.encode()).hexdigest()
        with self._lock:
            expiry = self._csrf_nonces.pop(key, None)
        return expiry is not None and expiry > current


def _parse_cookies(request: Request) -> dict[str, str]:
    raw = request.headers.get("cookie", "")
    cookie = SimpleCookie()
    try:
        cookie.load(raw)
    except CookieError:
        return {}
    values = {key: morsel.value for key, morsel in cookie.items()}
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        if raw.count(name + "=") > 1:
            values.pop(name, None)
    return values


def _origin_matches(origin: str, public_origin: str) -> bool:
    if origin == public_origin:
        return True
    parsed_origin = urlsplit(public_origin)
    return (
        origin == "null"
        and parsed_origin.scheme == "http"
        and parsed_origin.hostname in {"localhost", "127.0.0.1", "::1"}
    )


def _csrf_matches(
    request: Request,
    service: TemporaryCookieProvider,
    cookies: dict[str, str],
    body: bytes,
    expected_fields: set[str],
) -> bool:
    origin = request.headers.get("origin", "")
    if not _origin_matches(origin, service.settings.public_origin) or len(body) > 8192:
        return False
    try:
        fields = parse_qs(body.decode("utf-8"), strict_parsing=True, max_num_fields=8)
    except (UnicodeDecodeError, ValueError):
        return False
    if set(fields) != expected_fields or any(
        len(values) != 1 for values in fields.values()
    ):
        return False
    nonce_values = fields.get("csrf", [])
    if len(nonce_values) != 1:
        return False
    nonce = nonce_values[0]
    return service.consume_csrf_nonce(nonce, cookies.get(CSRF_COOKIE, ""))


async def _read_limited_form(request: Request) -> bytes | None:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > 8192:
                return None
        except ValueError:
            return None
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 8192:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def _html_page(title: str, body: str) -> HTMLResponse:
    content = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{html.escape(title)}</title></head><body>
<main><h1>{html.escape(title)}</h1>{body}</main></body></html>"""
    return HTMLResponse(
        content,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'none'; form-action 'self'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
    )


def _set_cookie(
    response: Response, name: str, value: str, settings: AuthSettings, max_age: int
) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        path="/",
        secure=settings.secure_cookie,
        httponly=True,
        samesite="strict",
    )


def _clear_cookie(response: Response, name: str, settings: AuthSettings) -> None:
    response.delete_cookie(
        name,
        path="/",
        secure=settings.secure_cookie,
        httponly=True,
        samesite="strict",
    )


def auth_routes(
    service: TemporaryCookieProvider,
    authorization_registry,
) -> list[Route]:
    async def login(request: Request) -> Response:
        cookies = _parse_cookies(request)
        if request.method == "GET":
            if service.authenticate(cookies):
                return RedirectResponse("/", status_code=303)
            try:
                nonce = service.create_csrf_nonce()
            except AuthCapacityError:
                return Response(
                    "Temporary authentication is at capacity.",
                    status_code=503,
                    headers={"Cache-Control": "no-store"},
                )
            response = _html_page(
                "VISION — DEV sign in",
                f"""<form method="post" action="/auth/login">
<input type="hidden" name="csrf" value="{html.escape(nonce, quote=True)}">
<label>Test user <input name="username" autocomplete="username" required></label>
<label>Password <input type="password" name="password" autocomplete="current-password" required></label>
<button type="submit">Sign in</button></form>
<p>Temporary DEV authentication. Not corporate SSO.</p>""",
            )
            _set_cookie(response, CSRF_COOKIE, nonce, service.settings, CSRF_SECONDS)
            return response
        content_type = (
            request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        )
        if (
            request.method != "POST"
            or content_type != "application/x-www-form-urlencoded"
        ):
            return Response(status_code=405, headers={"Allow": "GET, POST"})
        body = await _read_limited_form(request)
        if body is None:
            return Response(
                "Request too large.",
                status_code=413,
                headers={"Cache-Control": "no-store"},
            )
        if not _csrf_matches(
            request, service, cookies, body, {"csrf", "username", "password"}
        ):
            return Response(
                "Invalid request.",
                status_code=403,
                headers={"Cache-Control": "no-store"},
            )
        try:
            fields = parse_qs(
                body.decode("utf-8"), strict_parsing=True, max_num_fields=8
            )
        except (UnicodeDecodeError, ValueError):
            fields = {}
        username = fields.get("username", [""])[0].strip()
        password = fields.get("password", [""])[0]
        if len(username) > 128 or len(password) > 1024:
            principal = None
        else:
            principal = service.authenticate_password(username, password)
        if principal is None or authorization_registry.assignment(principal) is None:
            try:
                nonce = service.create_csrf_nonce()
            except AuthCapacityError:
                return Response(
                    "Temporary authentication is at capacity.",
                    status_code=503,
                    headers={"Cache-Control": "no-store"},
                )
            response = _html_page(
                "VISION — DEV sign in",
                f"""<p>Sign-in failed. Check the test account and try again.</p>
<form method="post" action="/auth/login">
<input type="hidden" name="csrf" value="{html.escape(nonce, quote=True)}">
<label>Test user <input name="username" autocomplete="username" required></label>
<label>Password <input type="password" name="password" autocomplete="current-password" required></label>
<button type="submit">Sign in</button></form>""",
            )
            response.status_code = 401
            _set_cookie(response, CSRF_COOKIE, nonce, service.settings, CSRF_SECONDS)
            return response
        try:
            session_token = service.issue_session(principal)
        except AuthCapacityError:
            return Response(
                "Temporary authentication is at capacity.",
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )
        response = RedirectResponse("/", status_code=303)
        _set_cookie(
            response,
            SESSION_COOKIE,
            session_token,
            service.settings,
            service.settings.session_seconds,
        )
        _clear_cookie(response, CSRF_COOKIE, service.settings)
        return response

    async def logout(request: Request) -> Response:
        cookies = _parse_cookies(request)
        if request.method == "GET":
            principal = service.authenticate(cookies)
            if principal is None:
                response = RedirectResponse("/auth/login", status_code=303)
                _clear_cookie(response, SESSION_COOKIE, service.settings)
                return response
            try:
                nonce = service.create_csrf_nonce()
            except AuthCapacityError:
                return Response(
                    "Temporary authentication is at capacity.",
                    status_code=503,
                    headers={"Cache-Control": "no-store"},
                )
            response = _html_page(
                "Sign out of VISION",
                f"""<p>End the temporary DEV session for {html.escape(principal.subject)}?</p>
<form method="post" action="/auth/logout">
<input type="hidden" name="csrf" value="{html.escape(nonce, quote=True)}">
<button type="submit">Sign out</button></form>""",
            )
            _set_cookie(response, CSRF_COOKIE, nonce, service.settings, CSRF_SECONDS)
            return response
        content_type = (
            request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        )
        if (
            request.method != "POST"
            or content_type != "application/x-www-form-urlencoded"
        ):
            return Response(status_code=405, headers={"Allow": "GET, POST"})
        body = await _read_limited_form(request)
        if body is None:
            return Response(
                "Request too large.",
                status_code=413,
                headers={"Cache-Control": "no-store"},
            )
        if not _csrf_matches(request, service, cookies, body, {"csrf"}):
            return Response(
                "Invalid request.",
                status_code=403,
                headers={"Cache-Control": "no-store"},
            )
        service.revoke(cookies)
        response = RedirectResponse("/auth/login", status_code=303)
        _clear_cookie(response, SESSION_COOKIE, service.settings)
        _clear_cookie(response, CSRF_COOKIE, service.settings)
        return response

    return [
        Route("/auth/login", login, methods=["GET", "POST"]),
        Route("/auth/logout", logout, methods=["GET", "POST"]),
    ]


class AuthenticationMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        service: IdentityProvider,
        authorization_registry,
        invalid_cookie_settings: AuthSettings | None = None,
    ):
        self.app = app
        self.service = service
        self.authorization_registry = authorization_registry
        self.invalid_cookie_settings = invalid_cookie_settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "/")
        if path in {"/auth/login", "/auth/logout", "/_stcore/health"}:
            await self.app(scope, receive, send)
            return
        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope["headers"]
        }
        cookies = SimpleCookie()
        try:
            cookies.load(headers.get("cookie", ""))
        except CookieError:
            cookies = SimpleCookie()
        principal = self.service.authenticate(
            IdentityRequest(
                headers=headers,
                cookies={key: value.value for key, value in cookies.items()},
            )
        )
        if (
            principal is None
            or self.authorization_registry.assignment(principal) is None
        ):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            response = RedirectResponse("/auth/login", status_code=303)
            if SESSION_COOKIE in cookies and self.invalid_cookie_settings is not None:
                _clear_cookie(response, SESSION_COOKIE, self.invalid_cookie_settings)
            await response(scope, receive, send)
            return
        scope.setdefault("state", {})["vision_principal"] = principal
        await self.app(scope, receive, send)


_runtime_settings: AuthSettings | None = None
_runtime_provider: TemporaryCookieProvider | None = None
_runtime_authorization_registry = None
_runtime_lock = threading.RLock()


def runtime_settings() -> AuthSettings:
    global _runtime_settings
    if _runtime_settings is None:
        with _runtime_lock:
            if _runtime_settings is None:
                _runtime_settings = AuthSettings.from_env()
    return _runtime_settings


def runtime_provider() -> TemporaryCookieProvider:
    global _runtime_provider
    if _runtime_provider is None:
        with _runtime_lock:
            if _runtime_provider is None:
                _runtime_provider = TemporaryCookieProvider(runtime_settings())
    return _runtime_provider


def runtime_authorization_registry():
    global _runtime_authorization_registry
    if _runtime_authorization_registry is None:
        with _runtime_lock:
            if _runtime_authorization_registry is None:
                from vision.authorization import AuthorizationRegistry

                _runtime_authorization_registry = AuthorizationRegistry.from_env(
                    runtime_settings()
                )
    return _runtime_authorization_registry


def current_principal(
    cookies: dict[str, str],
    service: IdentityProvider | None = None,
    headers: dict[str, str] | None = None,
) -> Principal | None:
    provider = service or runtime_provider()
    return provider.authenticate(IdentityRequest(headers or {}, cookies))
