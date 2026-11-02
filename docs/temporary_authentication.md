# Temporary VISION DEV authentication

**DEV-only preparation. This is not corporate SSO, not a replacement for Entra ID, and not
approved for production.** It does not inspect or replay Microsoft cookies, passwords, or tokens.
There is no public registration, and the repository contains no active accounts.

## Boundaries

The authentication interface accepts an `IdentityRequest` (request headers and cookies) and returns
a verified `Principal(subject)`. The temporary provider authenticates a password against a
preconfigured user registry and a VISION-signed cookie. A separate `AuthorizationRegistry` maps
that subject to one approved VISION role and explicit data scope. The session cookie contains only
the subject/session proof, never a browser-selected role or scope.

The future Entra adapter should consume only claims validated by App Service Authentication
(`X-MS-CLIENT-PRINCIPAL` or an agreed equivalent from the trusted App Service boundary) and return
the same `Principal`. Keep the `AuthorizationRegistry`, backend scope filters, and UI policy
independent. Do not trust arbitrary forwarded identity headers if the app can be reached outside
the App Service authentication boundary.

## Temporary login/session

1. `GET /auth/login` creates a short-lived, single-use CSRF nonce and serves a local HTML form.
2. `POST /auth/login` requires the configured exact `Origin` on HTTPS, the paired CSRF
   cookie/form token, an allowlisted username, and a valid PBKDF2-SHA256 password hash. For
   loopback-only HTTP development, an opaque `Origin: null` is accepted only with the same
   single-use CSRF pair; non-loopback HTTP origins are rejected.
3. VISION signs `iss`, `aud`, `sub`, `iat`, `exp`, and random `jti` claims with
   `VISION_AUTH_COOKIE_SECRET` using HMAC-SHA256. Server memory tracks active `jti` values so
   logout can revoke the cookie before its expiry.
4. The `vision_session` cookie is `HttpOnly`, `SameSite=Strict`, `Path=/`, and `Secure` whenever
   the configured public origin is HTTPS. Non-loopback HTTP origins are rejected. Default session
   duration is eight hours; the allowed range is five minutes to 24 hours.
5. ASGI middleware checks the cookie on every HTTP request and WebSocket upgrade. Unauthenticated
   requests are redirected to login or rejected. The Streamlit script validates the cookie again
   against the same server-side session registry on each rerun, and a 30-second fragment notices
   expiry/revocation in an idle tab. Logout is a CSRF-protected POST after a confirmation page;
   it revokes the active session and clears cookies.
6. Ten failed attempts for a known username cause a five-minute in-memory lockout. Authentication
   responses do not disclose whether a username exists. Login form bodies are limited to 8 KiB;
   the in-memory registry caps active sessions at 5,000 and outstanding CSRF nonces at 10,000,
   returning a service-unavailable response when at capacity. Passwords and cookie values are not
   logged.

The session registry, CSRF nonces, and login throttling are process-local memory, not durable
storage. A process restart clears them: existing cookies are rejected and users must sign in again.
Rotating the signing secret also invalidates existing cookies. Logout revokes a session only in
the process that owns its registry. Expiration is checked on each request; expired entries are
pruned when new sessions are issued, and outstanding CSRF nonces are pruned on form requests.

The prepared Azure DEV configuration explicitly runs Uvicorn with one worker and sets the
App Service plan capacity to one instance. Do not increase either setting: separate worker or
instance registries would reject sessions on a different process and could not propagate logout
revocation. This is acceptable only for the synthetic, single-instance DEV demo. Scaling requires
a shared session/revocation store and a separately reviewed design; sticky routing alone does not
make logout revocation consistent.

## Server-side authorization and data scope

The assignments are not stored in the signed cookie and are looked up on the server. Authenticated
sessions cannot use the development role picker or toggle Administrator mode.

| Assignment | Required explicit scope | Enforcement |
| --- | --- | --- |
| `commercial` | `commercial`: exact existing LION commercial value | Filter the server-side source model and details before the UI renders. |
| `commercial_manager` | `delegation`: exact existing delegation value | Apply the existing LION delegation scope to the server-side model/details. |
| `o2c` | `stages`: explicit existing stage labels | Filter server-side rows by PROOF/LION-owned stage outputs; limit stage choices, current-state detail, progress timeline, and displayed labels to that assignment. O2C PROOF history is currently withheld because an approved history-scope contract is absent. |
| `o2c_manager_sales_director` | `stages`: explicit existing stage labels | Same current O2C read scope. No manager/sales-director privilege is inferred. |

`administrator` is deliberately not a supported authenticated role. Missing roles, unknown roles,
empty scope, unknown source scope, or incomplete configuration fail closed. Stage labels must be
the exact labels emitted by the existing module. No stages or business permissions are invented.

The current row-level scope can still expose other attributes of a machine that matches an assigned
O2C stage. The product owner must decide whether cross-stage machine visibility is acceptable;
until then, use synthetic data only. O2C detail timelines are limited to assigned stage labels and
do not show overall process position. Commercial and manager history/report paths receive their
already scoped current model. One business decision remains: whether comments/notes are shared
across roles for a machine visible through an assigned scope, or need role-specific filtering.
Current prototype comments are shared; do not use real or confidential notes until that policy is
approved. Review any future export, report, and history paths before real data is approved.

## Required configuration

The App Service startup sets `VISION_AUTH_MODE=temporary` and fails if any of these are absent:

| Variable | Required value |
| --- | --- |
| `VISION_AUTH_COOKIE_SECRET` | At least 32 random bytes, encoded as a string; use a cryptographic random generator. |
| `VISION_AUTH_PUBLIC_ORIGIN` | Exact absolute origin, e.g. the approved HTTPS App Service hostname (no path). HTTP is accepted only for loopback local testing. |
| `VISION_TEMP_USERS_JSON` | Non-empty JSON list with `username` and `password_hash`. No self-registration. |
| `VISION_AUTHZ_ASSIGNMENTS_JSON` | Non-empty JSON list with one `subject`, `role`, and role-specific `scope` for every configured user. |
| `VISION_AUTH_SESSION_SECONDS` | Optional integer from 300 to 86400; default 28800 (8 hours). |

Hash one test password locally without putting it in shell history or source:

```powershell
.\.venv\Scripts\python.exe scripts\hash_auth_password.py
```

The password is read with terminal echo disabled; only its PBKDF2 hash is printed. The user registry
shape is:

```json
[{"username":"qa-vision-example","password_hash":"<hash printed by the local utility>"}]
```

The corresponding authorization map uses the same subject and an approved scope:

```json
[{"subject":"qa-vision-example","role":"commercial","scope":{"commercial":"<exact approved source value>"}}]
```

The names and values above are placeholders, not actual accounts or SAP data. Do not commit the
generated secret, password hash, password, or registry. IT must distribute test credentials through
an approved channel. Configure secret-bearing app settings outside Git (prefer an IT-approved
Key Vault reference where available); the public origin and auth mode are non-secret Bicep settings.
GitHub Actions receives no user passwords, hashes, session key, or Azure client secret.

## Local/CI behavior

The existing local UI/Playwright harness runs the prototype directly on loopback with synthetic
fixtures and no login. This is not the Azure entrypoint. Azure startup runs the exported ASGI app
with Uvicorn (`python -m uvicorn vision.asgi_app:app`), requires the temporary auth configuration,
and re-seeds only the pinned ephemeral path `/tmp/co-vision-dev-data`. Its health endpoint is
technical process health and intentionally remains unauthenticated; it reveals no data or
filesystem paths.

Tests cover password hashes, valid/tampered/expired sessions, single-use CSRF, secure cookie flags,
logout revocation, unauthenticated route denial, fail-closed configuration, separate authorization
assignments, role-specific scope validation, and server-side O2C row filtering.

## Future Entra migration — IT-owned

1. IT creates/owns the Entra App Registration and enterprise application; define tenant, client ID,
   redirect URI (`https://<approved-host>/...` as selected by the App Service auth integration),
   logout URL, token/claim contract, allowed users/groups, consent, and conditional-access policy.
2. IT configures App Service Authentication to require authentication and validates the Entra
   identity at the platform boundary. Do not make the app trust client-supplied identity headers.
3. Implement and test an Entra `IdentityProvider` adapter that consumes only platform-validated
   claims and returns the verified subject. No access token or Microsoft cookie should be stored in
   the VISION session cookie.
4. Approve a mapping from Entra subject/group claims to the existing VISION `AuthorizationRegistry`
   and SAP-derived scopes. Keep unknown/unassigned users denied.
5. Remove the temporary username/password provider after migration and rotate/remove its signing
   key. Re-run role- and row-scope tests before any business data is allowed.

Until that review is complete, this mechanism is suitable only for approved synthetic DEV test
accounts behind IT-approved network restrictions.
