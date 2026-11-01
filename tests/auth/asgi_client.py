from __future__ import annotations

import asyncio
from dataclasses import dataclass
from http.cookies import SimpleCookie
from urllib.parse import urlsplit


@dataclass
class ASGIResponse:
    status_code: int
    text: str
    headers: dict[str, list[str]]
    cookies: dict[str, str]


def request(
    app, method: str, url: str, *, data: bytes = b"", headers=None
) -> ASGIResponse:
    parsed = urlsplit(url)
    request_headers = {
        key.lower().encode("latin-1"): value.encode("latin-1")
        for key, value in (headers or {}).items()
    }
    if data and b"content-type" not in request_headers:
        request_headers[b"content-type"] = b"application/x-www-form-urlencoded"
    events = []
    sent_request = False

    async def receive():
        nonlocal sent_request
        if not sent_request:
            sent_request = True
            return {"type": "http.request", "body": data, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(event):
        events.append(event)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": parsed.scheme or "https",
        "path": parsed.path or "/",
        "raw_path": (parsed.path or "/").encode("ascii"),
        "query_string": parsed.query.encode("ascii"),
        "root_path": "",
        "headers": list(request_headers.items()),
        "client": ("127.0.0.1", 50000),
        "server": (parsed.hostname or "vision.example.test", parsed.port or 443),
    }
    asyncio.run(app(scope, receive, send))
    start = next(event for event in events if event["type"] == "http.response.start")
    body = b"".join(
        event.get("body", b"")
        for event in events
        if event["type"] == "http.response.body"
    )
    response_headers: dict[str, list[str]] = {}
    for key, value in start.get("headers", []):
        response_headers.setdefault(key.decode("latin-1").lower(), []).append(
            value.decode("latin-1")
        )
    response_cookies: dict[str, str] = {}
    for value in response_headers.get("set-cookie", []):
        cookie = SimpleCookie()
        cookie.load(value)
        response_cookies.update({key: morsel.value for key, morsel in cookie.items()})
    return ASGIResponse(
        start["status"],
        body.decode("utf-8", errors="replace"),
        response_headers,
        response_cookies,
    )
