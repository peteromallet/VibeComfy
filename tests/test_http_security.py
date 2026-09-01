from __future__ import annotations

import asyncio
import importlib
import logging
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from vibecomfy.comfy_nodes import http_security as security


ROOT = Path(__file__).resolve().parents[1]
TOKEN = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-"


class _Headers:
    def __init__(self, pairs: list[tuple[str, str]] | None = None) -> None:
        self._pairs = [(name.casefold(), value) for name, value in (pairs or [])]

    def getall(self, name: str, default: Any = None) -> list[str]:
        values = [value for key, value in self._pairs if key == name.casefold()]
        return values if values else ([] if default is None else default)

    def get(self, name: str, default: Any = None) -> Any:
        values = self.getall(name, [])
        return values[0] if values else default


class _Transport:
    def __init__(self, peer: str, port: int = 8188) -> None:
        self._peer = peer
        self._port = port

    def get_extra_info(self, name: str) -> Any:
        if name == "peername":
            return (self._peer, 43123)
        if name == "sockname":
            return ("0.0.0.0", self._port)
        return None


def _request(
    *,
    peer: str = "127.0.0.1",
    host: str | None = "127.0.0.1:8188",
    method: str = "GET",
    scheme: str = "http",
    headers: list[tuple[str, str]] | None = None,
    port: int = 8188,
) -> SimpleNamespace:
    pairs = list(headers or [])
    if host is not None:
        pairs.insert(0, ("Host", host))
    return SimpleNamespace(
        headers=_Headers(pairs),
        method=method,
        scheme=scheme,
        transport=_Transport(peer, port),
    )


def _config(
    *,
    token: str | None = None,
    origins: str = "",
    proxies: str = "",
) -> security.HttpSecurityConfig:
    env: dict[str, str] = {}
    if token is not None:
        env["VIBECOMFY_HTTP_BEARER_TOKEN"] = token
    if origins:
        env["VIBECOMFY_HTTP_ALLOWED_ORIGINS"] = origins
    if proxies:
        env["VIBECOMFY_HTTP_TRUSTED_PROXY_PEERS"] = proxies
    return security.load_http_security_config(env)


@pytest.mark.parametrize(
    ("peer", "host"),
    [
        ("127.0.0.1", "127.0.0.1:8188"),
        ("127.82.19.4", "localhost:8188"),
        ("::1", "[::1]:8188"),
    ],
)
def test_trusted_local_cli_accepts_loopback_peer_and_exact_host(
    peer: str, host: str
) -> None:
    decision = security.authorize_sensitive_request(
        _request(peer=peer, host=host, method="POST"),
        config=_config(),
    )

    assert decision.allowed is True
    assert decision.mode == "trusted_local"


@pytest.mark.parametrize(
    "host",
    [
        None,
        "example.com:8188",
        "127.0.0.1.example.com:8188",
        "localhost:9999",
        "localhost:8188/path",
        "localhost:bad-port",
        "localhost,example.com:8188",
        "localhost:",
        "127.0.0.1:",
        "[::1]:",
        "local\thost:8188",
        "local\nhost:8188",
    ],
)
def test_local_peer_rejects_missing_malformed_rebound_or_wrong_port_host(
    host: str | None,
) -> None:
    decision = security.authorize_sensitive_request(
        _request(host=host, method="POST"),
        config=_config(),
    )

    assert decision.allowed is False
    assert decision.status == 403


@pytest.mark.parametrize("host", ["localhost:0", "127.0.0.1:0", "[::1]:0"])
def test_local_peer_rejects_explicit_port_zero_on_default_port_socket(
    host: str,
) -> None:
    decision = security.authorize_sensitive_request(
        _request(host=host, method="POST", port=80),
        config=_config(),
    )

    assert decision.allowed is False
    assert decision.status == 403


def test_local_browser_requires_same_origin_fetch_metadata_and_csrf() -> None:
    base_headers = [
        ("Origin", "http://localhost:8188"),
        ("Sec-Fetch-Site", "same-origin"),
        ("Sec-Fetch-Mode", "cors"),
    ]
    missing = security.authorize_sensitive_request(
        _request(host="localhost:8188", method="POST", headers=base_headers),
        config=_config(),
    )
    supplied = security.authorize_sensitive_request(
        _request(
            host="localhost:8188",
            method="POST",
            headers=[
                *base_headers,
                (security.CSRF_HEADER, security._PROCESS_CSRF_TOKEN),
            ],
        ),
        config=_config(),
    )

    assert missing.allowed is False
    assert supplied.allowed is True


@pytest.mark.parametrize(
    "headers",
    [
        [("Origin", "https://attacker.example"), ("Sec-Fetch-Site", "cross-site")],
        [("Origin", "null"), ("Sec-Fetch-Site", "same-origin")],
        [("Origin", "http://localhost:8188"), ("Sec-Fetch-Site", "cross-site")],
        [
            ("Origin", "http://localhost:8188"),
            ("Sec-Fetch-Site", "same-origin"),
            ("Sec-Fetch-Mode", "navigate"),
        ],
    ],
)
def test_local_browser_rejects_hostile_null_cross_site_and_navigation(
    headers: list[tuple[str, str]],
) -> None:
    decision = security.authorize_sensitive_request(
        _request(
            host="localhost:8188",
            headers=[*headers, (security.CSRF_HEADER, security._PROCESS_CSRF_TOKEN)],
        ),
        config=_config(),
    )

    assert decision.allowed is False


@pytest.mark.parametrize(
    "browser_header",
    [
        ("Origin", "http://localhost:0"),
        ("Referer", "http://localhost:0/panel"),
        ("Origin", "http://127.0.0.1:0"),
        ("Referer", "http://[::1]:0/panel"),
    ],
)
def test_local_browser_rejects_explicit_port_zero_before_mutation(
    browser_header: tuple[str, str],
) -> None:
    decision = security.authorize_sensitive_request(
        _request(
            host="localhost",
            method="POST",
            port=80,
            headers=[
                browser_header,
                ("Sec-Fetch-Site", "same-origin"),
                ("Sec-Fetch-Mode", "cors"),
                (security.CSRF_HEADER, security._PROCESS_CSRF_TOKEN),
            ],
        ),
        config=_config(),
    )

    assert decision.allowed is False
    assert decision.status == 403


@pytest.mark.parametrize(
    "headers",
    [
        [("Referer", "https://attacker.example/path")],
        [("Referer", "null")],
        [("Referer", "about:client")],
        [("Referer", "http://localhost:/path")],
        [("Referer", "http://local\thost:8188/path")],
        [("Referer", "http://localhost:8188/#fragment")],
        [
            ("Referer", "http://localhost:8188/path"),
            ("Referer", "http://localhost:8188/other"),
        ],
    ],
)
def test_referer_browser_evidence_fails_closed_before_local_mutation(
    headers: list[tuple[str, str]],
) -> None:
    calls: list[str] = []

    @security.sensitive_route
    async def _handler(_request: Any) -> web.Response:
        calls.append("mutated")
        return web.json_response({"ok": True})

    response = asyncio.run(
        _handler(_request(host="localhost:8188", method="POST", headers=headers))
    )

    assert response.status == 403
    assert calls == []


def test_same_origin_referer_is_browser_evidence_and_requires_csrf() -> None:
    referer = [("Referer", "http://localhost:8188/panel?view=agent")]
    missing = security.authorize_sensitive_request(
        _request(host="localhost:8188", method="POST", headers=referer),
        config=_config(),
    )
    supplied = security.authorize_sensitive_request(
        _request(
            host="localhost:8188",
            method="POST",
            headers=[*referer, (security.CSRF_HEADER, security._PROCESS_CSRF_TOKEN)],
        ),
        config=_config(),
    )

    assert missing.allowed is False
    assert supplied.allowed is True


def test_local_cli_without_browser_headers_does_not_need_csrf() -> None:
    decision = security.authorize_sensitive_request(
        _request(host="localhost:8188", method="POST"),
        config=_config(),
    )

    assert decision.allowed is True


def test_untrusted_forwarded_headers_never_create_local_authority() -> None:
    decision = security.authorize_sensitive_request(
        _request(
            host="localhost:8188",
            headers=[("X-Forwarded-For", "127.0.0.1")],
        ),
        config=_config(),
    )

    assert decision.allowed is False


def test_untrusted_proxy_spoof_is_rejected_even_with_valid_remote_bearer() -> None:
    decision = security.authorize_sensitive_request(
        _request(
            peer="198.51.100.87",
            host="remote.example:8188",
            headers=[
                ("Authorization", f"Bearer {TOKEN}"),
                ("Forwarded", "for=127.0.0.1;host=localhost:8188;proto=http"),
            ],
        ),
        config=_config(token=TOKEN),
    )

    assert decision.allowed is False


def test_configured_proxy_peer_is_remote_and_still_requires_bearer() -> None:
    config = _config(token=TOKEN, proxies="127.0.0.1")
    forwarded = [("Forwarded", "for=198.51.100.9;proto=https")]
    missing = security.authorize_sensitive_request(
        _request(host="service.example:8188", headers=forwarded),
        config=config,
    )
    supplied = security.authorize_sensitive_request(
        _request(
            host="service.example:8188",
            headers=[*forwarded, ("Authorization", f"Bearer {TOKEN}")],
        ),
        config=config,
    )

    assert missing.allowed is False
    assert supplied.allowed is True
    assert supplied.mode == "remote_capability"


def test_runpod_style_remote_route_is_closed_without_bearer_and_open_with_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_HTTP_BEARER_TOKEN", TOKEN)
    monkeypatch.delenv("VIBECOMFY_HTTP_BEARER_TOKEN_FILE", raising=False)
    monkeypatch.delenv("VIBECOMFY_HTTP_ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("VIBECOMFY_HTTP_TRUSTED_PROXY_PEERS", raising=False)
    calls: list[str] = []

    @security.sensitive_route
    async def _handler(_request: Any) -> web.Response:
        calls.append("remote mutation")
        return web.json_response({"ok": True})

    request = _request(peer="198.51.100.23", host="pod.example:8188", method="POST")
    wrong = _request(
        peer="198.51.100.23",
        host="pod.example:8188",
        method="POST",
        headers=[("Authorization", "Bearer definitely-not-the-token-000000")],
    )
    right = _request(
        peer="198.51.100.23",
        host="pod.example:8188",
        method="POST",
        headers=[("Authorization", f"Bearer {TOKEN}")],
    )

    assert asyncio.run(_handler(request)).status == 403
    assert asyncio.run(_handler(wrong)).status == 403
    assert calls == []
    assert asyncio.run(_handler(right)).status == 200
    assert calls == ["remote mutation"]


def test_remote_browser_requires_bearer_and_exact_allowlisted_origin() -> None:
    config = _config(token=TOKEN, origins="https://panel.example")
    common = [
        ("Authorization", f"Bearer {TOKEN}"),
        ("Sec-Fetch-Site", "cross-site"),
        ("Sec-Fetch-Mode", "cors"),
    ]
    allowed = _request(
        peer="203.0.113.8",
        host="api.example:8188",
        method="POST",
        headers=[*common, ("Origin", "https://panel.example")],
    )
    hostile = _request(
        peer="203.0.113.8",
        host="api.example:8188",
        method="POST",
        headers=[*common, ("Origin", "https://panel.example.attacker")],
    )

    assert security.authorize_sensitive_request(allowed, config=config).allowed is True
    assert security.authorize_sensitive_request(hostile, config=config).allowed is False


@pytest.mark.parametrize(
    "env",
    [
        {"VIBECOMFY_HTTP_BEARER_TOKEN": "short"},
        {"VIBECOMFY_HTTP_BEARER_TOKEN": "a" * 64},
        {
            "VIBECOMFY_HTTP_BEARER_TOKEN": TOKEN,
            "VIBECOMFY_HTTP_BEARER_TOKEN_FILE": "/unused/duplicate-source",
        },
        {"VIBECOMFY_HTTP_ALLOWED_ORIGINS": "*"},
        {"VIBECOMFY_HTTP_ALLOWED_ORIGINS": "https://panel.example"},
        {"VIBECOMFY_HTTP_TRUSTED_PROXY_PEERS": "127.0.0.1"},
        {
            "VIBECOMFY_HTTP_BEARER_TOKEN": TOKEN,
            "VIBECOMFY_HTTP_ALLOWED_ORIGINS": "https://example.com/path",
        },
        {
            "VIBECOMFY_HTTP_BEARER_TOKEN": TOKEN,
            "VIBECOMFY_HTTP_ALLOWED_ORIGINS": "http://panel.example:0",
        },
        {
            "VIBECOMFY_HTTP_BEARER_TOKEN": TOKEN,
            "VIBECOMFY_HTTP_ALLOWED_ORIGINS": "http://127.0.0.1:0",
        },
        {
            "VIBECOMFY_HTTP_BEARER_TOKEN": TOKEN,
            "VIBECOMFY_HTTP_ALLOWED_ORIGINS": "http://[::1]:0",
        },
        {
            "VIBECOMFY_HTTP_BEARER_TOKEN": TOKEN,
            "VIBECOMFY_HTTP_TRUSTED_PROXY_PEERS": "10.0.0.0/8",
        },
    ],
)
def test_configuration_rejects_short_default_ambiguous_or_inexact_values(
    env: dict[str, str],
) -> None:
    with pytest.raises(security.HttpSecurityConfigurationError):
        security.load_http_security_config(env)


def test_secret_file_requires_absolute_private_regular_file(tmp_path: Path) -> None:
    secret_file = tmp_path / "http-bearer"
    secret_file.write_text(TOKEN + "\n", encoding="ascii")
    secret_file.chmod(0o600)

    with pytest.raises(security.HttpSecurityConfigurationError, match="absolute"):
        security.load_http_security_config(
            {"VIBECOMFY_HTTP_BEARER_TOKEN_FILE": secret_file.name}
        )

    config = security.load_http_security_config(
        {"VIBECOMFY_HTTP_BEARER_TOKEN_FILE": str(secret_file)}
    )
    assert config.bearer_token == TOKEN.encode("ascii")

    secret_file.chmod(0o644)
    with pytest.raises(security.HttpSecurityConfigurationError, match="permissions"):
        security.load_http_security_config(
            {"VIBECOMFY_HTTP_BEARER_TOKEN_FILE": str(secret_file)}
        )

    secret_file.chmod(0o600)
    symlink = tmp_path / "http-bearer-link"
    symlink.symlink_to(secret_file)
    with pytest.raises(security.HttpSecurityConfigurationError, match="non-symlink"):
        security.load_http_security_config(
            {"VIBECOMFY_HTTP_BEARER_TOKEN_FILE": str(symlink)}
        )


def test_bearer_comparison_uses_constant_time_primitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[bytes, bytes]] = []

    def _compare(left: bytes, right: bytes) -> bool:
        calls.append((left, right))
        return left == right

    monkeypatch.setattr(security.hmac, "compare_digest", _compare)
    decision = security.authorize_sensitive_request(
        _request(
            peer="198.51.100.10",
            host="remote.example:8188",
            headers=[("Authorization", f"Bearer {TOKEN}")],
        ),
        config=_config(token=TOKEN),
    )

    assert decision.allowed is True
    assert calls == [(TOKEN.encode("ascii"), TOKEN.encode("ascii"))]


def test_denied_handler_has_no_side_effect_and_never_leaks_credentials(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls: list[str] = []

    @security.sensitive_route
    async def _handler(_request: Any) -> web.Response:
        calls.append("downstream")
        return web.json_response({"ok": True})

    supplied = "wrong-but-sensitive-value-1234567890"
    request = _request(
        peer="198.51.100.44",
        host="remote.example:8188",
        method="POST",
        headers=[("Authorization", f"Bearer {supplied}")],
    )
    with caplog.at_level(logging.DEBUG):
        response = asyncio.run(_handler(request))

    assert response.status == 403
    assert calls == []
    assert supplied not in response.text
    assert supplied not in caplog.text
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "Access-Control-Allow-Origin" not in response.headers


def test_denied_sensitive_route_families_invoke_no_downstream_side_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "VIBECOMFY_HTTP_ALLOWED_ORIGINS",
        "VIBECOMFY_HTTP_BEARER_TOKEN",
        "VIBECOMFY_HTTP_BEARER_TOKEN_FILE",
        "VIBECOMFY_HTTP_TRUSTED_PROXY_PEERS",
    ):
        monkeypatch.delenv(name, raising=False)
    registered: dict[tuple[str, str], Any] = {}

    class _Routes:
        def get(self, path: str) -> Any:
            return self._decorator("GET", path)

        def post(self, path: str) -> Any:
            return self._decorator("POST", path)

        def _decorator(self, method: str, path: str) -> Any:
            def _register(handler: Any) -> Any:
                registered[(method, path)] = handler
                return handler

            return _register

    prompt_server = types.ModuleType("server")
    prompt_server.PromptServer = SimpleNamespace(
        instance=SimpleNamespace(routes=_Routes())
    )
    monkeypatch.setitem(sys.modules, "server", prompt_server)
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "0")

    from vibecomfy.comfy_nodes.agent import routes as route_module

    route_module = importlib.reload(route_module)
    calls: list[str] = []

    def _side_effect(name: str) -> Any:
        def _record(*_args: Any, **_kwargs: Any) -> Any:
            calls.append(name)
            raise AssertionError(f"denied request invoked {name}")

        return _record

    monkeypatch.setattr(
        route_module, "_handle_agent_executor_submit", _side_effect("submit")
    )
    monkeypatch.setattr(
        route_module, "_handle_node_pack_install", _side_effect("install")
    )
    monkeypatch.setattr(
        route_module, "_handle_agent_credentials", _side_effect("credentials")
    )
    monkeypatch.setattr(
        route_module, "_handle_agent_settings_post", _side_effect("settings")
    )
    monkeypatch.setattr(
        route_module,
        "_handle_research_contribution_run",
        _side_effect("research_subprocess"),
    )

    targets = (
        ("POST", "/vibecomfy/agent-executor"),
        ("POST", "/vibecomfy/node-packs/install"),
        ("POST", "/vibecomfy/agent/credentials"),
        ("POST", "/vibecomfy/agent/settings"),
        ("POST", "/vibecomfy/agent/research-contribution/run"),
    )
    denied = _request(peer="198.51.100.61", host="public.example:8188", method="POST")
    for target in targets:
        assert target in registered
        response = asyncio.run(registered[target](denied))
        assert response.status == 403

    assert calls == []


@pytest.mark.asyncio
async def test_live_loopback_browser_bootstrap_and_mutation_smoke(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "VIBECOMFY_HTTP_ALLOWED_ORIGINS",
        "VIBECOMFY_HTTP_BEARER_TOKEN",
        "VIBECOMFY_HTTP_BEARER_TOKEN_FILE",
        "VIBECOMFY_HTTP_TRUSTED_PROXY_PEERS",
    ):
        monkeypatch.delenv(name, raising=False)
    calls: list[str] = []
    routes = web.RouteTableDef()

    @security.register_http_route(routes, "GET", security.CSRF_BOOTSTRAP_PATH)
    async def _csrf(_request: web.Request) -> web.Response:
        return security.csrf_bootstrap_response()

    @security.register_http_route(routes, "POST", "/vibecomfy/agent/settings")
    async def _mutation(_request: web.Request) -> web.Response:
        calls.append("mutated")
        return web.json_response({"ok": True})

    app = web.Application(
        middlewares=[web.middleware(security.http_namespace_middleware)]
    )
    app.add_routes(routes)
    server = TestServer(app, host="127.0.0.1")
    client = TestClient(server)
    await client.start_server()
    try:
        origin = str(client.make_url("/")).rstrip("/")
        browser_headers = {
            "Origin": origin,
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        denied = await client.post("/vibecomfy/agent/settings", headers=browser_headers)
        assert denied.status == 403
        assert calls == []

        bootstrap = await client.get(
            security.CSRF_BOOTSTRAP_PATH, headers=browser_headers
        )
        assert bootstrap.status == 200
        payload = await bootstrap.json()
        assert payload["csrf_header"] == security.CSRF_HEADER
        assert bootstrap.headers["Cache-Control"] == "no-store"
        assert bootstrap.headers["X-Content-Type-Options"] == "nosniff"
        assert "Access-Control-Allow-Origin" not in bootstrap.headers

        authorized = await client.post(
            "/vibecomfy/agent/settings",
            headers={**browser_headers, security.CSRF_HEADER: payload["csrf_token"]},
        )
        assert authorized.status == 200
        assert calls == ["mutated"]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_live_remote_browser_preflight_get_and_mutation_cors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_HTTP_BEARER_TOKEN", TOKEN)
    monkeypatch.delenv("VIBECOMFY_HTTP_BEARER_TOKEN_FILE", raising=False)
    monkeypatch.delenv("VIBECOMFY_HTTP_TRUSTED_PROXY_PEERS", raising=False)
    calls: list[str] = []
    routes = web.RouteTableDef()

    @security.register_http_route(routes, "GET", "/vibecomfy/agent/settings")
    async def _settings_get(_request: web.Request) -> web.Response:
        calls.append("get")
        return web.json_response({"ok": True})

    @security.register_http_route(routes, "POST", "/vibecomfy/agent/settings")
    async def _settings_post(_request: web.Request) -> web.Response:
        calls.append("post")
        return web.json_response({"ok": True})

    app = web.Application(
        middlewares=[web.middleware(security.http_namespace_middleware)]
    )
    app.add_routes(routes)
    server = TestServer(app, host="127.0.0.1")
    client = TestClient(server)
    await client.start_server()
    try:
        port = client.make_url("/").port
        assert port is not None
        monkeypatch.setenv(
            "VIBECOMFY_HTTP_ALLOWED_ORIGINS",
            f"http://panel.example,http://panel.example:{port}",
        )
        preflight_headers = {
            "Host": f"api.example:{port}",
            "Origin": "http://panel.example",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type",
        }
        preflight = await client.options(
            "/vibecomfy/agent/settings", headers=preflight_headers
        )
        assert preflight.status == 204
        assert (
            preflight.headers["Access-Control-Allow-Origin"] == "http://panel.example"
        )
        assert preflight.headers["Access-Control-Allow-Methods"] == "POST"
        assert "Authorization" in preflight.headers["Access-Control-Allow-Headers"]
        assert calls == []

        hostile = await client.options(
            "/vibecomfy/agent/settings",
            headers={**preflight_headers, "Origin": "https://attacker.example"},
        )
        assert hostile.status == 403
        assert "Access-Control-Allow-Origin" not in hostile.headers
        assert calls == []

        browser_headers = {
            "Host": f"api.example:{port}",
            "Origin": "http://panel.example",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "Content-Type": "application/json",
        }
        denied = await client.post(
            "/vibecomfy/agent/settings",
            headers={
                **browser_headers,
                "Authorization": "Bearer wrong-capability-000000000000000",
            },
            json={},
        )
        assert denied.status == 403
        assert denied.headers["Access-Control-Allow-Origin"] == "http://panel.example"
        assert calls == []

        authorized = await client.post(
            "/vibecomfy/agent/settings",
            headers={**browser_headers, "Authorization": f"Bearer {TOKEN}"},
            json={},
        )
        assert authorized.status == 200
        assert (
            authorized.headers["Access-Control-Allow-Origin"] == "http://panel.example"
        )
        assert calls == ["post"]

        same_origin_get = await client.get(
            "/vibecomfy/agent/settings",
            headers={
                "Host": f"panel.example:{port}",
                "Authorization": f"Bearer {TOKEN}",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            },
        )
        assert same_origin_get.status == 200
        assert "Access-Control-Allow-Origin" not in same_origin_get.headers
        assert calls == ["post", "get"]
    finally:
        await client.close()


def test_runtime_route_inventory_is_complete_guarded_and_exact_get_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = web.RouteTableDef()

    for method, path in (
        ("GET", "/vibecomfy/ping"),
        ("GET", "/vibecomfy/info"),
        ("GET", security.CSRF_BOOTSTRAP_PATH),
    ):

        async def _entrypoint_handler(_request: Any) -> web.Response:
            return web.json_response({"ok": True})

        security.register_http_route(routes, method, path)(_entrypoint_handler)

    prompt_server = types.ModuleType("server")
    prompt_server.PromptServer = SimpleNamespace(
        instance=SimpleNamespace(routes=routes)
    )
    monkeypatch.setitem(sys.modules, "server", prompt_server)
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "0")

    from vibecomfy.comfy_nodes.agent import routes as route_module

    importlib.reload(route_module)
    app = web.Application()
    prompt_server_instance = SimpleNamespace(app=app)
    security.install_http_namespace_middleware(prompt_server_instance)
    app.add_routes(routes)
    materialized_routes = list(app.router.routes())
    asyncio.run(app.on_startup[-1](app))

    actual = {
        (route.method, route.resource.canonical) for route in materialized_routes
    }
    assert actual == set(security.HTTP_ROUTE_POLICIES)
    assert security.PUBLIC_HTTP_ROUTES == {
        ("GET", "/vibecomfy/info"),
        ("GET", "/vibecomfy/ping"),
    }
    assert ("HEAD", "/vibecomfy/info") not in actual
    assert ("HEAD", "/vibecomfy/ping") not in actual


def test_exact_get_routes_can_be_copied_by_comfyui_api_prefixer() -> None:
    routes = web.RouteTableDef()

    @security.register_http_route(routes, "GET", "/vibecomfy/info")
    async def _handler(_request: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    api_routes = web.RouteTableDef()
    original = next(route for route in routes if isinstance(route, web.RouteDef))
    assert "allow_head" not in original.kwargs

    # Mirrors PromptServer.add_routes in current ComfyUI.
    api_routes.route(
        original.method,
        "/api" + original.path,
    )(original.handler, **original.kwargs)

    app = web.Application()
    app.add_routes(api_routes)
    app.add_routes(routes)
    actual = {(route.method, route.resource.canonical) for route in app.router.routes()}
    assert actual == {
        ("GET", "/api/vibecomfy/info"),
        ("GET", "/vibecomfy/info"),
    }


@pytest.mark.parametrize("registration", ["head", "alternate_method", "view"])
def test_materialized_route_audit_rejects_late_and_alternate_registrations(
    registration: str,
) -> None:
    routes = web.RouteTableDef()

    for method, path in security.HTTP_ROUTE_POLICIES:
        async def _route_handler(_request: web.Request) -> web.Response:
            return web.json_response({"ok": True})

        security.register_http_route(routes, method, path)(_route_handler)

    async def _handler(_request: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    app = web.Application()
    app.add_routes(routes)
    if registration == "head":
        app.router.add_route("HEAD", "/vibecomfy/info", _handler)
    elif registration == "alternate_method":
        app.router.add_route("POST", "/vibecomfy/ping", _handler)
    else:

        class _LateView(web.View):
            async def get(self) -> web.Response:
                return web.json_response({"ok": True})

        app.router.add_view("/vibecomfy/late-view", _LateView)

    with pytest.raises(RuntimeError, match="not inventoried"):
        security.audit_runtime_route_table(app.router.routes())


@pytest.mark.asyncio
async def test_runtime_namespace_denies_uninventoried_aliases_and_unguarded_routes() -> (
    None
):
    calls: list[str] = []

    async def _unguarded(_request: web.Request) -> web.Response:
        calls.append("unguarded")
        return web.json_response({"ok": True})

    class _UnguardedView(web.View):
        async def get(self) -> web.Response:
            calls.append("unguarded view")
            return web.json_response({"ok": True})

    app = web.Application(
        middlewares=[web.middleware(security.http_namespace_middleware)]
    )
    app.router.add_route("GET", "/vibecomfy/agent/settings", _unguarded)
    app.router.add_view("/vibecomfy/uninventoried", _UnguardedView)
    server = TestServer(app, host="127.0.0.1")
    client = TestClient(server)
    await client.start_server()
    try:
        guarded_path = await client.get("/vibecomfy/agent/settings")
        unknown_path = await client.get("/vibecomfy/uninventoried")
        implicit_method = await client.head("/vibecomfy/info")
        legacy_alias = await client.get("/agent/edit")

        assert guarded_path.status == 403
        assert unknown_path.status == 403
        assert implicit_method.status == 403
        assert legacy_alias.status == 403
        assert calls == []
    finally:
        await client.close()


def test_namespace_middleware_installation_is_required_and_idempotent() -> None:
    prompt_server = SimpleNamespace(app=web.Application())
    original_startup_handlers = len(prompt_server.app.on_startup)

    security.install_http_namespace_middleware(prompt_server)
    security.install_http_namespace_middleware(prompt_server)

    assert len(prompt_server.app.middlewares) == 1
    assert len(prompt_server.app.on_startup) == original_startup_handlers + 1
    assert prompt_server._vibecomfy_http_middleware_installed is True
    with pytest.raises(RuntimeError, match="middleware registry"):
        security.install_http_namespace_middleware(SimpleNamespace())


def test_no_vibecomfy_websocket_or_sse_route_is_in_scope() -> None:
    route_source = (
        ROOT / "vibecomfy" / "comfy_nodes" / "agent" / "routes.py"
    ).read_text(encoding="utf-8")
    assert "WebSocketResponse" not in route_source
    assert "text/event-stream" not in route_source


def test_local_launch_helper_does_not_enable_permissive_cors() -> None:
    source = (ROOT / "scripts" / "run_local_agent_comfy.sh").read_text(encoding="utf-8")
    assert "--enable-cors-header" not in source
