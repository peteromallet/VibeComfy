"""Authorization boundary for VibeComfy's ComfyUI HTTP routes.

VibeComfy is a single-operator tool.  The supported boundary is therefore an
instance capability with a strict loopback exception, not a user/session
identity system.  Session identifiers are deliberately not accepted as proof
of authority.
"""

from __future__ import annotations

import functools
import hmac
import ipaddress
import os
import re
import secrets
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


PUBLIC_HTTP_ROUTES = frozenset(
    {
        ("GET", "/vibecomfy/info"),
        ("GET", "/vibecomfy/ping"),
    }
)
CSRF_BOOTSTRAP_PATH = "/vibecomfy/security/csrf"
CSRF_HEADER = "X-VibeComfy-CSRF"

_PUBLIC = "public"
_SENSITIVE = "sensitive"
_LOCAL_ONLY = "local_only"
HTTP_ROUTE_POLICIES = {
    ("GET", "/vibecomfy/ping"): _PUBLIC,
    ("GET", "/vibecomfy/info"): _PUBLIC,
    ("GET", CSRF_BOOTSTRAP_PATH): _LOCAL_ONLY,
    ("POST", "/vibecomfy/agent-edit"): _SENSITIVE,
    ("POST", "/vibecomfy/agent-executor"): _SENSITIVE,
    ("POST", "/agent/edit"): _SENSITIVE,
    ("POST", "/vibecomfy/agent-edit/accept"): _SENSITIVE,
    ("POST", "/vibecomfy/agent-edit/prepare"): _SENSITIVE,
    ("POST", "/vibecomfy/agent-edit/finalize"): _SENSITIVE,
    ("POST", "/vibecomfy/agent-edit/rollback"): _SENSITIVE,
    ("POST", "/vibecomfy/agent-edit/reconcile"): _SENSITIVE,
    ("POST", "/vibecomfy/agent-edit/reject"): _SENSITIVE,
    ("POST", "/vibecomfy/agent-edit/rebaseline"): _SENSITIVE,
    ("GET", "/vibecomfy/agent-edit/chat"): _SENSITIVE,
    ("GET", "/vibecomfy/agent-edit/recover"): _SENSITIVE,
    ("GET", "/vibecomfy/agent-edit/session-bundle"): _SENSITIVE,
    ("GET", "/vibecomfy/agent-edit/session-json"): _SENSITIVE,
    ("POST", "/vibecomfy/node-packs/install"): _SENSITIVE,
    ("GET", "/vibecomfy/demo/scenarios"): _SENSITIVE,
    ("GET", "/vibecomfy/demo/scenario"): _SENSITIVE,
    ("GET", "/vibecomfy/agentic-replay/runs"): _SENSITIVE,
    ("GET", "/vibecomfy/agentic-replay/runs/{run_id}/tests"): _SENSITIVE,
    ("GET", "/vibecomfy/agentic-replay/runs/{run_id}/tests/{test_id}"): _SENSITIVE,
    ("POST", "/vibecomfy/roundtrip"): _SENSITIVE,
    ("POST", "/vibecomfy/agent-edit/rating"): _SENSITIVE,
    ("GET", "/vibecomfy/agent/status"): _SENSITIVE,
    ("POST", "/vibecomfy/agent/credentials"): _SENSITIVE,
    ("GET", "/vibecomfy/agent/settings"): _SENSITIVE,
    ("POST", "/vibecomfy/agent/settings"): _SENSITIVE,
    ("POST", "/vibecomfy/agent/research-contribution/run"): _SENSITIVE,
}
if (
    frozenset(key for key, access in HTTP_ROUTE_POLICIES.items() if access == _PUBLIC)
    != PUBLIC_HTTP_ROUTES
):
    raise RuntimeError("public HTTP route inventory is inconsistent")

_BEARER_ENV = "VIBECOMFY_HTTP_BEARER_TOKEN"
_BEARER_FILE_ENV = "VIBECOMFY_HTTP_BEARER_TOKEN_FILE"
_ORIGINS_ENV = "VIBECOMFY_HTTP_ALLOWED_ORIGINS"
_TRUSTED_PROXIES_ENV = "VIBECOMFY_HTTP_TRUSTED_PROXY_PEERS"
_FORWARDED_HEADERS = (
    "Forwarded",
    "X-Forwarded-For",
    "X-Forwarded-Host",
    "X-Forwarded-Port",
    "X-Forwarded-Proto",
    "X-Real-IP",
)
_FETCH_HEADERS = (
    "Sec-Fetch-Dest",
    "Sec-Fetch-Mode",
    "Sec-Fetch-Site",
    "Sec-Fetch-User",
)
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._~+/=-]{32,}$")
_OBVIOUS_DEFAULTS = frozenset(
    {
        "bearer",
        "changeme",
        "default",
        "password",
        "secret",
        "token",
        "vibecomfy",
    }
)
_PROCESS_CSRF_TOKEN = secrets.token_urlsafe(32)


class HttpSecurityConfigurationError(ValueError):
    """Raised when the explicit remote HTTP authority is unsafe or ambiguous."""


@dataclass(frozen=True)
class HttpSecurityConfig:
    """Validated process configuration; secret bytes are excluded from repr."""

    bearer_token: bytes | None = field(default=None, repr=False)
    allowed_origins: frozenset[str] = frozenset()
    trusted_proxy_peers: frozenset[ipaddress.IPv4Address | ipaddress.IPv6Address] = (
        frozenset()
    )


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    status: int
    code: str
    mode: str | None = None
    cors_origin: str | None = None


@dataclass(frozen=True)
class _RequestFacts:
    method: str
    scheme: str
    peer: ipaddress.IPv4Address | ipaddress.IPv6Address
    listen_port: int
    host: str
    host_port: int
    local_host: bool
    browser: bool
    origin: str | None
    referer_origin: str | None
    fetch_site: str | None
    fetch_mode: str | None
    has_forwarded_headers: bool


def _configuration_error(message: str) -> HttpSecurityConfigurationError:
    # Configuration errors must never interpolate token values.
    return HttpSecurityConfigurationError(message)


def _validated_token(raw: str, *, source: str) -> bytes:
    if raw != raw.strip():
        raise _configuration_error(f"{source} must not contain surrounding whitespace")
    try:
        encoded = raw.encode("ascii")
    except UnicodeEncodeError as exc:
        raise _configuration_error(
            f"{source} must be an ASCII bearer capability"
        ) from exc
    if not _TOKEN_PATTERN.fullmatch(raw):
        raise _configuration_error(
            f"{source} must be a generated bearer capability of at least 32 ASCII characters"
        )
    if raw.casefold() in _OBVIOUS_DEFAULTS or len(set(raw)) < 8:
        raise _configuration_error(
            f"{source} must be generated, not a default or repeated value"
        )
    return encoded


def _read_token_file(raw_path: str) -> bytes:
    path = Path(raw_path)
    if not path.is_absolute():
        raise _configuration_error(f"{_BEARER_FILE_ENV} must name an absolute path")
    try:
        link_status = path.lstat()
        file_status = path.stat()
    except OSError as exc:
        raise _configuration_error(f"{_BEARER_FILE_ENV} is not readable") from exc
    if stat.S_ISLNK(link_status.st_mode) or not stat.S_ISREG(file_status.st_mode):
        raise _configuration_error(
            f"{_BEARER_FILE_ENV} must name a regular, non-symlink file"
        )
    if os.name != "nt" and file_status.st_mode & 0o077:
        raise _configuration_error(
            f"{_BEARER_FILE_ENV} permissions must not grant group/other access"
        )
    if file_status.st_size > 4096:
        raise _configuration_error(f"{_BEARER_FILE_ENV} is unexpectedly large")
    try:
        raw = path.read_text(encoding="ascii").rstrip("\r\n")
    except (OSError, UnicodeError) as exc:
        raise _configuration_error(
            f"{_BEARER_FILE_ENV} is not a readable ASCII file"
        ) from exc
    return _validated_token(raw, source=_BEARER_FILE_ENV)


def _normalize_origin(raw: str) -> str:
    if (
        raw == "null"
        or not raw
        or raw != raw.strip()
        or "*" in raw
        or any(ord(character) < 32 or ord(character) == 127 for character in raw)
    ):
        raise ValueError("origin is absent, null, wildcarded, or padded")
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("origin is malformed") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.netloc.endswith(":")
    ):
        raise ValueError("origin must use http or https and include a host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("origin must not contain user information")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("origin must not contain a path, query, or fragment")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("origin port is invalid")
    normalized_port = (
        port if port is not None else (443 if parsed.scheme == "https" else 80)
    )
    hostname = parsed.hostname.lower()
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        rendered_host = hostname
    else:
        rendered_host = f"[{ip.compressed}]" if ip.version == 6 else ip.compressed
    default_port = 443 if parsed.scheme == "https" else 80
    suffix = "" if normalized_port == default_port else f":{normalized_port}"
    return f"{parsed.scheme}://{rendered_host}{suffix}"


def _normalize_referer_origin(raw: str) -> str:
    if (
        raw.casefold() == "null"
        or not raw
        or raw != raw.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in raw)
    ):
        raise ValueError("Referer is absent, null-equivalent, padded, or malformed")
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Referer is malformed") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.netloc.endswith(":")
    ):
        raise ValueError("Referer must be an absolute HTTP URL")
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        raise ValueError("Referer contains forbidden URL components")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Referer port is invalid")
    normalized_port = (
        port if port is not None else (443 if parsed.scheme == "https" else 80)
    )
    hostname = parsed.hostname.lower()
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        rendered_host = hostname
    else:
        rendered_host = f"[{ip.compressed}]" if ip.version == 6 else ip.compressed
    default_port = 443 if parsed.scheme == "https" else 80
    suffix = "" if normalized_port == default_port else f":{normalized_port}"
    return f"{parsed.scheme}://{rendered_host}{suffix}"


def load_http_security_config(
    environ: Mapping[str, str] | None = None,
) -> HttpSecurityConfig:
    """Load and validate the explicit remote-instance authority configuration."""

    env = os.environ if environ is None else environ
    direct = env.get(_BEARER_ENV, "")
    token_file = env.get(_BEARER_FILE_ENV, "")
    if direct and token_file:
        raise _configuration_error(
            f"configure only one of {_BEARER_ENV} and {_BEARER_FILE_ENV}"
        )
    bearer = _validated_token(direct, source=_BEARER_ENV) if direct else None
    if token_file:
        bearer = _read_token_file(token_file)

    origins: set[str] = set()
    for raw_origin in env.get(_ORIGINS_ENV, "").split(","):
        if not raw_origin.strip():
            continue
        try:
            origins.add(_normalize_origin(raw_origin.strip()))
        except ValueError as exc:
            raise _configuration_error(
                f"{_ORIGINS_ENV} contains an invalid exact origin"
            ) from exc

    proxies: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    for raw_peer in env.get(_TRUSTED_PROXIES_ENV, "").split(","):
        if not raw_peer.strip():
            continue
        try:
            proxies.add(ipaddress.ip_address(raw_peer.strip()))
        except ValueError as exc:
            raise _configuration_error(
                f"{_TRUSTED_PROXIES_ENV} accepts exact IP literals only"
            ) from exc

    if bearer is None and (origins or proxies):
        raise _configuration_error(
            "remote origins/proxies require an instance bearer capability"
        )
    return HttpSecurityConfig(
        bearer_token=bearer,
        allowed_origins=frozenset(origins),
        trusted_proxy_peers=frozenset(proxies),
    )


def _header_values(headers: Any, name: str) -> list[str]:
    getall = getattr(headers, "getall", None)
    if callable(getall):
        try:
            return [str(value) for value in getall(name, [])]
        except TypeError:
            pass
    getter = getattr(headers, "get", None)
    if not callable(getter):
        return []
    value = getter(name)
    if value is None:
        return []
    return [str(value)]


def _one_header(headers: Any, name: str) -> str | None:
    values = _header_values(headers, name)
    if len(values) != 1:
        return None
    return values[0]


def _transport_value(request: Any, name: str) -> Any:
    transport = getattr(request, "transport", None)
    getter = getattr(transport, "get_extra_info", None)
    return getter(name) if callable(getter) else None


def _parse_transport_address(
    value: Any,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    candidate = value[0] if isinstance(value, (tuple, list)) and value else value
    if not isinstance(candidate, str):
        raise ValueError("transport address is unavailable")
    # IPv6 peer tuples may include a zone identifier; loopback/trusted peers do not need it.
    return ipaddress.ip_address(candidate.split("%", 1)[0])


def _parse_listen_port(value: Any) -> int:
    if not isinstance(value, (tuple, list)) or len(value) < 2:
        raise ValueError("listening socket is unavailable")
    port = value[1]
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("listening port is invalid")
    return port


def _parse_host(raw: str, *, scheme: str) -> tuple[str, int]:
    if (
        not raw
        or raw != raw.strip()
        or raw.endswith(":")
        or any(ord(character) < 32 or ord(character) == 127 for character in raw)
        or any(character in raw for character in "/?#@,\\")
    ):
        raise ValueError("Host is malformed")
    try:
        parsed = urlsplit(f"//{raw}")
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Host is malformed") from exc
    if (
        not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("Host is malformed")
    if parsed.path or parsed.query or parsed.fragment:
        raise ValueError("Host is malformed")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Host port is invalid")
    normalized_port = port if port is not None else (443 if scheme == "https" else 80)
    return parsed.hostname.lower(), normalized_port


def _is_loopback_host(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _request_facts(request: Any) -> _RequestFacts:
    headers = request.headers
    method = str(getattr(request, "method", "")).upper()
    scheme = str(getattr(request, "scheme", "")).lower()
    if method not in {"GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"}:
        raise ValueError("HTTP method is unavailable or unsupported")
    if scheme not in {"http", "https"}:
        raise ValueError("request scheme is unavailable or unsupported")
    peer = _parse_transport_address(_transport_value(request, "peername"))
    listen_port = _parse_listen_port(_transport_value(request, "sockname"))
    host_values = _header_values(headers, "Host")
    if len(host_values) != 1:
        raise ValueError("Host must occur exactly once")
    host, host_port = _parse_host(host_values[0], scheme=scheme)
    local_host = _is_loopback_host(host) and host_port == listen_port

    origin_values = _header_values(headers, "Origin")
    if len(origin_values) > 1:
        raise ValueError("Origin must occur at most once")
    raw_origin = origin_values[0] if origin_values else None
    referer_values = _header_values(headers, "Referer")
    if len(referer_values) > 1:
        raise ValueError("Referer must occur at most once")
    raw_referer = referer_values[0] if referer_values else None
    fetch_values = {name: _header_values(headers, name) for name in _FETCH_HEADERS}
    if any(len(values) > 1 for values in fetch_values.values()):
        raise ValueError("fetch metadata headers must not be repeated")
    browser = (
        raw_origin is not None or raw_referer is not None or any(fetch_values.values())
    )
    origin = None
    if raw_origin is not None:
        origin = _normalize_origin(raw_origin)
    referer_origin = None
    if raw_referer is not None:
        referer_origin = _normalize_referer_origin(raw_referer)
    fetch_site = (
        fetch_values["Sec-Fetch-Site"][0].lower()
        if fetch_values["Sec-Fetch-Site"]
        else None
    )
    fetch_mode = (
        fetch_values["Sec-Fetch-Mode"][0].lower()
        if fetch_values["Sec-Fetch-Mode"]
        else None
    )
    has_forwarded = any(_header_values(headers, name) for name in _FORWARDED_HEADERS)
    return _RequestFacts(
        method=method,
        scheme=scheme,
        peer=peer,
        listen_port=listen_port,
        host=host,
        host_port=host_port,
        local_host=local_host,
        browser=browser,
        origin=origin,
        referer_origin=referer_origin,
        fetch_site=fetch_site,
        fetch_mode=fetch_mode,
        has_forwarded_headers=has_forwarded,
    )


def _request_origin(facts: _RequestFacts) -> str:
    try:
        ip = ipaddress.ip_address(facts.host)
    except ValueError:
        rendered_host = facts.host
    else:
        rendered_host = f"[{ip.compressed}]" if ip.version == 6 else ip.compressed
    default_port = 443 if facts.scheme == "https" else 80
    suffix = "" if facts.host_port == default_port else f":{facts.host_port}"
    return f"{facts.scheme}://{rendered_host}{suffix}"


def _bearer_matches(headers: Any, expected: bytes | None) -> bool:
    values = _header_values(headers, "Authorization")
    if expected is None or len(values) != 1:
        # Keep a compare on the missing/invalid path so callers cannot infer whether
        # a capability is configured from an early secret comparison exit.
        return hmac.compare_digest(b"", expected or b"not-configured") and False
    raw = values[0]
    if not raw.startswith("Bearer ") or raw.count(" ") != 1:
        return hmac.compare_digest(b"", expected) and False
    try:
        supplied = raw[7:].encode("ascii")
    except UnicodeEncodeError:
        supplied = b""
    return hmac.compare_digest(supplied, expected)


def _csrf_matches(headers: Any) -> bool:
    values = _header_values(headers, CSRF_HEADER)
    supplied = values[0] if len(values) == 1 else ""
    try:
        supplied_bytes = supplied.encode("ascii")
    except UnicodeEncodeError:
        supplied_bytes = b""
    return hmac.compare_digest(supplied_bytes, _PROCESS_CSRF_TOKEN.encode("ascii"))


def _remote_browser_origin(
    facts: _RequestFacts,
    config: HttpSecurityConfig,
) -> tuple[str | None, str | None]:
    """Return (validated browser origin, CORS response origin)."""

    request_origin = _request_origin(facts)
    if facts.origin is not None:
        if facts.origin not in config.allowed_origins:
            return None, None
        if facts.referer_origin is not None and facts.referer_origin != facts.origin:
            return None, None
        return facts.origin, facts.origin

    if facts.fetch_site == "same-origin":
        if facts.referer_origin is not None and facts.referer_origin != request_origin:
            return None, None
        candidate = facts.referer_origin or request_origin
    elif facts.referer_origin is not None:
        candidate = facts.referer_origin
    else:
        return None, None
    if candidate not in config.allowed_origins:
        return None, None
    return candidate, None


def authorize_sensitive_request(
    request: Any,
    *,
    config: HttpSecurityConfig | None = None,
    local_only: bool = False,
) -> AuthorizationDecision:
    """Authorize one sensitive request without inspecting its body or session id."""

    # Direct unit/embedded calls that are not HTTP requests have no HTTP boundary.
    # A real aiohttp request always exposes headers and a transport; partial HTTP
    # objects fail closed below.
    if not hasattr(request, "headers") and not hasattr(request, "transport"):
        return AuthorizationDecision(True, 200, "embedded_call", "embedded")
    try:
        active_config = config or load_http_security_config()
        facts = _request_facts(request)
    except HttpSecurityConfigurationError:
        return AuthorizationDecision(False, 503, "http_security_misconfigured")
    except (TypeError, ValueError):
        return AuthorizationDecision(False, 403, "http_request_not_authorized")

    peer_is_proxy = facts.peer in active_config.trusted_proxy_peers
    if facts.has_forwarded_headers and not peer_is_proxy:
        return AuthorizationDecision(False, 403, "http_request_not_authorized")

    trusted_local = facts.peer.is_loopback and facts.local_host and not peer_is_proxy
    if trusted_local:
        if facts.browser:
            if facts.origin is not None and facts.origin != _request_origin(facts):
                return AuthorizationDecision(False, 403, "http_request_not_authorized")
            if (
                facts.referer_origin is not None
                and facts.referer_origin != _request_origin(facts)
            ):
                return AuthorizationDecision(False, 403, "http_request_not_authorized")
            if facts.fetch_site is not None and facts.fetch_site != "same-origin":
                return AuthorizationDecision(False, 403, "http_request_not_authorized")
            if facts.fetch_mode == "navigate":
                return AuthorizationDecision(False, 403, "http_request_not_authorized")
            if facts.method not in _SAFE_METHODS and not _csrf_matches(request.headers):
                return AuthorizationDecision(False, 403, "http_request_not_authorized")
        return AuthorizationDecision(True, 200, "trusted_local", "trusted_local")

    if local_only:
        return AuthorizationDecision(False, 403, "http_request_not_authorized")
    cors_origin: str | None = None
    if facts.browser:
        validated_origin, cors_origin = _remote_browser_origin(facts, active_config)
        if validated_origin is None:
            return AuthorizationDecision(False, 403, "http_request_not_authorized")
    if not _bearer_matches(request.headers, active_config.bearer_token):
        return AuthorizationDecision(
            False,
            403,
            "http_request_not_authorized",
            cors_origin=cors_origin,
        )
    if facts.browser:
        if facts.fetch_mode == "navigate":
            return AuthorizationDecision(
                False,
                403,
                "http_request_not_authorized",
                cors_origin=cors_origin,
            )
    return AuthorizationDecision(
        True,
        200,
        "remote_capability",
        "remote_capability",
        cors_origin,
    )


def _harden_response(response: Any, *, cors_origin: str | None = None) -> Any:
    headers = getattr(response, "headers", None)
    if headers is None:
        return response
    for name in (
        "Access-Control-Allow-Credentials",
        "Access-Control-Allow-Headers",
        "Access-Control-Allow-Methods",
        "Access-Control-Allow-Origin",
    ):
        headers.pop(name, None)
    headers["Cache-Control"] = "no-store"
    headers["X-Content-Type-Options"] = "nosniff"
    if cors_origin is not None:
        headers["Access-Control-Allow-Origin"] = cors_origin
        vary = headers.get("Vary")
        if not vary:
            headers["Vary"] = "Origin"
        elif "origin" not in {item.strip().casefold() for item in vary.split(",")}:
            headers["Vary"] = f"{vary}, Origin"
    return response


def _denial_response(decision: AuthorizationDecision) -> Any:
    from aiohttp import web

    response = web.json_response(
        {"ok": False, "error": decision.code},
        status=decision.status,
    )
    return _harden_response(response, cors_origin=decision.cors_origin)


def sensitive_route(
    handler: Callable[..., Any] | None = None,
    *,
    local_only: bool = False,
) -> Callable[..., Any]:
    """Decorate an aiohttp handler with the instance authorization boundary."""

    def decorate(route_handler: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(route_handler)
        async def guarded(request: Any, *args: Any, **kwargs: Any) -> Any:
            decision = authorize_sensitive_request(request, local_only=local_only)
            if not decision.allowed:
                return _denial_response(decision)
            response = await route_handler(request, *args, **kwargs)
            return _harden_response(response, cors_origin=decision.cors_origin)

        guarded.__vibecomfy_http_security__ = (
            "local_only" if local_only else "sensitive"
        )
        return guarded

    if handler is not None:
        return decorate(handler)
    return decorate


def csrf_bootstrap_response() -> Any:
    """Return the process-scoped local browser CSRF capability."""

    from aiohttp import web

    return _harden_response(
        web.json_response(
            {
                "csrf_header": CSRF_HEADER,
                "csrf_token": _PROCESS_CSRF_TOKEN,
            }
        )
    )


def _route_decorator(routes: Any, method: str, path: str) -> Callable[..., Any]:
    method_registrar = getattr(routes, method.lower(), None)
    if method == "GET" and callable(method_registrar):
        try:
            return method_registrar(path, allow_head=False)
        except TypeError:
            return method_registrar(path)
    generic = getattr(routes, "route", None)
    if callable(generic):
        return generic(method, path)
    if callable(method_registrar):
        return method_registrar(path)
    raise RuntimeError("HTTP route registry does not support the required method")


def register_http_route(
    routes: Any,
    method: str,
    path: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register one centrally inventoried route with its declared policy."""

    key = (method.upper(), path)
    access = HTTP_ROUTE_POLICIES.get(key)
    if access is None:
        raise RuntimeError(f"unclassified VibeComfy HTTP route: {key!r}")
    registrar = _route_decorator(routes, key[0], path)

    def decorate(handler: Callable[..., Any]) -> Callable[..., Any]:
        if access == _PUBLIC:
            guarded = handler
            guarded.__vibecomfy_http_security__ = _PUBLIC
        else:
            guarded = sensitive_route(handler, local_only=access == _LOCAL_ONLY)
        guarded.__vibecomfy_http_route__ = key
        return registrar(guarded)

    return decorate


def _is_vibecomfy_namespace(path: str) -> bool:
    return path.startswith("/vibecomfy/") or path == "/agent/edit"


def _path_matches_template(template: str, path: str) -> bool:
    template_parts = template.strip("/").split("/")
    path_parts = path.strip("/").split("/")
    if len(template_parts) != len(path_parts):
        return False
    return all(
        left == right or (left.startswith("{") and left.endswith("}"))
        for left, right in zip(template_parts, path_parts, strict=True)
    )


def _policy_for_path(method: str, path: str) -> tuple[tuple[str, str], str] | None:
    exact = (method.upper(), path)
    access = HTTP_ROUTE_POLICIES.get(exact)
    if access is not None:
        return exact, access
    matches = [
        (key, candidate_access)
        for key, candidate_access in HTTP_ROUTE_POLICIES.items()
        if key[0] == method.upper() and _path_matches_template(key[1], path)
    ]
    return matches[0] if len(matches) == 1 else None


def _runtime_route_path(route: Any) -> str:
    path = getattr(route, "path", None)
    if path is not None:
        return str(path)
    resource = getattr(route, "resource", None)
    canonical = getattr(resource, "canonical", None)
    return str(canonical) if canonical is not None else ""


def audit_runtime_route_table(routes: Any) -> None:
    """Fail startup when the materialized dispatcher diverges from the inventory."""

    seen: set[tuple[str, str]] = set()
    for route in routes:
        method = str(getattr(route, "method", "")).upper()
        path = _runtime_route_path(route)
        if not _is_vibecomfy_namespace(path):
            continue
        policy = HTTP_ROUTE_POLICIES.get((method, path))
        if policy is None:
            raise RuntimeError(
                f"runtime VibeComfy route is not inventoried: {method} {path}"
            )
        handler = getattr(route, "handler", None)
        if getattr(handler, "__vibecomfy_http_security__", None) != policy:
            raise RuntimeError(
                f"runtime VibeComfy route has the wrong guard: {method} {path}"
            )
        if getattr(handler, "__vibecomfy_http_route__", None) != (method, path):
            raise RuntimeError(
                f"runtime VibeComfy route has the wrong inventory key: {method} {path}"
            )
        key = (method, path)
        if key in seen:
            raise RuntimeError(
                f"runtime VibeComfy route is duplicated: {method} {path}"
            )
        seen.add(key)
    missing = set(HTTP_ROUTE_POLICIES) - seen
    if missing:
        rendered = ", ".join(f"{method} {path}" for method, path in sorted(missing))
        raise RuntimeError(
            f"inventoried VibeComfy routes were not registered: {rendered}"
        )


def _request_route_handler(request: Any) -> Any:
    match_info = getattr(request, "match_info", None)
    route = getattr(match_info, "route", None)
    return getattr(route, "handler", None)


def _parse_preflight_headers(headers: Any) -> tuple[str, ...] | None:
    values = _header_values(headers, "Access-Control-Request-Headers")
    if len(values) != 1:
        return None
    requested = tuple(
        item.strip().casefold() for item in values[0].split(",") if item.strip()
    )
    allowed = {"accept", "authorization", "content-type"}
    if (
        not requested
        or "authorization" not in requested
        or len(requested) != len(set(requested))
        or any(
            name not in allowed or not re.fullmatch(r"[a-z0-9-]+", name)
            for name in requested
        )
    ):
        return None
    return requested


def _preflight_response(request: Any) -> Any:
    from aiohttp import web

    try:
        config = load_http_security_config()
        facts = _request_facts(request)
    except HttpSecurityConfigurationError:
        return _denial_response(
            AuthorizationDecision(False, 503, "http_security_misconfigured")
        )
    except (TypeError, ValueError):
        return _denial_response(
            AuthorizationDecision(False, 403, "http_request_not_authorized")
        )
    peer_is_proxy = facts.peer in config.trusted_proxy_peers
    trusted_local = facts.peer.is_loopback and facts.local_host and not peer_is_proxy
    if trusted_local or (facts.has_forwarded_headers and not peer_is_proxy):
        return _denial_response(
            AuthorizationDecision(False, 403, "http_request_not_authorized")
        )
    requested_methods = _header_values(request.headers, "Access-Control-Request-Method")
    if len(requested_methods) != 1:
        return _denial_response(
            AuthorizationDecision(False, 403, "http_request_not_authorized")
        )
    requested_method = requested_methods[0].upper()
    policy = _policy_for_path(requested_method, str(getattr(request, "path", "")))
    requested_headers = _parse_preflight_headers(request.headers)
    if (
        config.bearer_token is None
        or facts.origin is None
        or facts.origin not in config.allowed_origins
        or (facts.referer_origin is not None and facts.referer_origin != facts.origin)
        or policy is None
        or policy[1] != _SENSITIVE
        or requested_headers is None
    ):
        return _denial_response(
            AuthorizationDecision(False, 403, "http_request_not_authorized")
        )
    rendered_headers = ", ".join(name.title() for name in requested_headers)
    response = _harden_response(web.Response(status=204), cors_origin=facts.origin)
    response.headers["Access-Control-Allow-Methods"] = requested_method
    response.headers["Access-Control-Allow-Headers"] = rendered_headers
    response.headers["Access-Control-Max-Age"] = "300"
    return response


async def http_namespace_middleware(request: Any, handler: Callable[..., Any]) -> Any:
    """Runtime namespace default-deny plus exact remote CORS preflight."""

    path = str(getattr(request, "path", ""))
    if not _is_vibecomfy_namespace(path):
        return await handler(request)
    method = str(getattr(request, "method", "")).upper()
    if method == "OPTIONS":
        return _preflight_response(request)
    policy = _policy_for_path(method, path)
    if policy is None:
        return _denial_response(
            AuthorizationDecision(False, 403, "http_route_not_authorized")
        )
    route_handler = _request_route_handler(request)
    if (
        getattr(route_handler, "__vibecomfy_http_security__", None) != policy[1]
        or getattr(route_handler, "__vibecomfy_http_route__", None) != policy[0]
    ):
        return _denial_response(
            AuthorizationDecision(False, 403, "http_route_not_authorized")
        )
    return await handler(request)


def install_http_namespace_middleware(prompt_server: Any) -> None:
    app = getattr(prompt_server, "app", None)
    middlewares = getattr(app, "middlewares", None)
    if middlewares is None:
        raise RuntimeError("ComfyUI server does not expose an HTTP middleware registry")
    if getattr(prompt_server, "_vibecomfy_http_middleware_installed", False):
        return
    from aiohttp import web

    on_startup = getattr(app, "on_startup", None)
    if on_startup is None:
        raise RuntimeError("ComfyUI server does not expose an HTTP startup registry")

    middlewares.insert(0, web.middleware(http_namespace_middleware))

    async def _audit_materialized_routes(app: Any) -> None:
        audit_runtime_route_table(app.router.routes())

    on_startup.append(_audit_materialized_routes)
    prompt_server._vibecomfy_http_middleware_installed = True


__all__ = (
    "AuthorizationDecision",
    "CSRF_BOOTSTRAP_PATH",
    "CSRF_HEADER",
    "HTTP_ROUTE_POLICIES",
    "HttpSecurityConfig",
    "HttpSecurityConfigurationError",
    "PUBLIC_HTTP_ROUTES",
    "authorize_sensitive_request",
    "audit_runtime_route_table",
    "csrf_bootstrap_response",
    "http_namespace_middleware",
    "install_http_namespace_middleware",
    "load_http_security_config",
    "register_http_route",
    "sensitive_route",
)
