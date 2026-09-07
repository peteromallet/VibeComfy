from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Mapping

from vibecomfy.comfy_nodes.agent.hivemind_feedback import (
    ANON_KEY_ENV,
    CONTRIBUTOR_KEY_ENV,
    DEFAULT_HIVEMIND_EDGE_URL,
    EDGE_URL_ENV,
    MAX_ZIP_BYTES_ENV,
    HivemindFeedbackConfig,
    ProxyHTTPResponse,
    load_hivemind_feedback_config,
    submit_hivemind_feedback,
)


def _key(hex_char: str = "a") -> str:
    return f"hm_{hex_char * 64}"


def _config(**overrides: object) -> HivemindFeedbackConfig:
    values = {
        "edge_url": "https://hivemind.example/rating",
        "contributor_key": _key(),
        "anon_key": "test-anon-key",
        "max_zip_bytes": 64,
        "timeout_seconds": 10.0,
    }
    values.update(overrides)
    return HivemindFeedbackConfig(**values)


def test_load_config_normalizes_contributor_key_and_defaults_edge_url() -> None:
    config = load_hivemind_feedback_config(
        {
            CONTRIBUTOR_KEY_ENV: f" HM_{'A' * 64} ",
            ANON_KEY_ENV: "test-anon-key",
            MAX_ZIP_BYTES_ENV: "32",
        }
    )

    assert config.edge_url == DEFAULT_HIVEMIND_EDGE_URL
    assert config.contributor_key == _key("a")
    assert config.anon_key == "test-anon-key"
    assert config.max_zip_bytes == 32


def test_load_config_rejects_invalid_contributor_key_format() -> None:
    result, status = submit_hivemind_feedback(
        {
            "response_id": "s1/t1",
            "session_id": "s1",
            "turn_id": "t1",
            "rating": 8,
            "pack_shared": False,
        },
        config=HivemindFeedbackConfig(
            edge_url="https://hivemind.example/rating",
            contributor_key="not-a-valid-key",
        ),
        transport=lambda *_args: ProxyHTTPResponse(status=201, body=b"{}"),
    )

    assert status == 503
    assert result == {
        "ok": False,
        "error": "configuration",
        "detail": f"{CONTRIBUTOR_KEY_ENV} must be hm_<64 hex chars>.",
    }


def test_load_config_rejects_empty_server_url() -> None:
    result, status = submit_hivemind_feedback(
        {
            "response_id": "s1/t1",
            "session_id": "s1",
            "turn_id": "t1",
            "rating": 8,
            "pack_shared": False,
        },
        config=HivemindFeedbackConfig(
            edge_url="",
            contributor_key=_key(),
        ),
        transport=lambda *_args: ProxyHTTPResponse(status=201, body=b"{}"),
    )

    assert status == 503
    assert result == {
        "ok": False,
        "error": "configuration",
        "detail": f"{EDGE_URL_ENV} must not be empty.",
    }


def test_missing_contributor_key_is_configuration_error_without_secret_echo(monkeypatch) -> None:
    monkeypatch.delenv(CONTRIBUTOR_KEY_ENV, raising=False)
    result, status = submit_hivemind_feedback(
        {"rating": 8},
        config=None,
        transport=lambda *_args: ProxyHTTPResponse(status=201, body=b"{}"),
    )

    assert status == 503
    assert result == {
        "ok": False,
        "error": "configuration",
        "detail": f"{CONTRIBUTOR_KEY_ENV} is required on the server.",
    }
    assert "hm_" not in result["detail"]


def test_submit_forwards_metadata_only_payload() -> None:
    seen: dict[str, object] = {}
    payload = {
        "response_id": "session-1/turn_2",
        "session_id": "session-1",
        "turn_id": "turn_2",
        "rating": 7,
        "comment": "helped",
        "pack_shared": False,
    }

    def transport(
        url: str,
        body: bytes,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> ProxyHTTPResponse:
        seen["url"] = url
        seen["body"] = json.loads(body.decode("utf-8"))
        seen["headers"] = dict(headers)
        seen["timeout_seconds"] = timeout_seconds
        return ProxyHTTPResponse(status=201, body=b'{"id":"rating-meta"}')

    result, status = submit_hivemind_feedback(
        payload,
        config=_config(edge_url="https://hivemind.example/metadata", contributor_key=_key("d")),
        transport=transport,
    )

    assert status == 201
    assert result == {"ok": True, "id": "rating-meta"}
    assert seen["url"] == "https://hivemind.example/metadata"
    assert seen["body"] == payload
    assert seen["headers"] == {
        "content-type": "application/json",
        "authorization": "Bearer test-anon-key",
        "x-contributor-key": _key("d"),
    }
    assert seen["timeout_seconds"] == 10.0


def test_submit_forwards_json_contributor_header_and_timeout_without_logging_zip() -> None:
    seen: dict[str, object] = {}
    zip_base64 = base64.b64encode(b"PK\x03\x04debug").decode("ascii")
    payload = {
        "response_id": "s1/t1",
        "session_id": "s1",
        "turn_id": "t1",
        "rating": 9,
        "comment": "useful",
        "pack_shared": True,
        "pack_zip_base64": zip_base64,
    }
    config = _config(
        edge_url="https://hivemind.example/functions/v1/submit-vibecomfy-rating",
        contributor_key=_key("b"),
        max_zip_bytes=64,
        timeout_seconds=2.5,
    )

    def transport(
        url: str,
        body: bytes,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> ProxyHTTPResponse:
        seen["url"] = url
        seen["body"] = json.loads(body.decode("utf-8"))
        seen["headers"] = dict(headers)
        seen["timeout_seconds"] = timeout_seconds
        return ProxyHTTPResponse(
            status=201,
            body=b'{"id":"rating-1","status":"ok","report_url":"https://cdn.example/report.zip"}',
        )

    result, status = submit_hivemind_feedback(payload, config=config, transport=transport)

    assert status == 201
    assert result == {
        "ok": True,
        "id": "rating-1",
        "status": "ok",
        "report_url": "https://cdn.example/report.zip",
    }
    assert seen["url"] == config.edge_url
    assert seen["body"] == payload
    assert seen["headers"] == {
        "content-type": "application/json",
        "authorization": "Bearer test-anon-key",
        "x-contributor-key": _key("b"),
    }
    assert seen["timeout_seconds"] == 2.5


def test_submit_rejects_oversized_zip_before_transport() -> None:
    called = False
    payload = {
        "response_id": "s1/t1",
        "session_id": "s1",
        "turn_id": "t1",
        "rating": 8,
        "pack_shared": True,
        "pack_zip_base64": base64.b64encode(b"PK\x03\x0412345").decode("ascii"),
    }

    def transport(*_args) -> ProxyHTTPResponse:
        nonlocal called
        called = True
        return ProxyHTTPResponse(status=201, body=b"{}")

    result, status = submit_hivemind_feedback(
        payload,
        config=_config(max_zip_bytes=4),
        transport=transport,
    )

    assert status == 413
    assert result == {
        "ok": False,
        "error": "validation",
        "detail": "field 'pack_zip_base64' decodes to more than 4 bytes.",
    }
    assert called is False


def test_submit_rejects_pack_zip_without_pack_opt_in_before_transport() -> None:
    called = False
    payload = {
        "response_id": "s1/t1",
        "session_id": "s1",
        "turn_id": "t1",
        "rating": 8,
        "pack_shared": False,
        "pack_zip_base64": base64.b64encode(b"PK\x03\x04debug").decode("ascii"),
    }

    def transport(*_args) -> ProxyHTTPResponse:
        nonlocal called
        called = True
        return ProxyHTTPResponse(status=201, body=b"{}")

    result, status = submit_hivemind_feedback(
        payload,
        config=_config(),
        transport=transport,
    )

    assert status == 400
    assert result == {
        "ok": False,
        "error": "validation",
        "detail": "field 'pack_zip_base64' is only allowed when pack_shared is true.",
    }
    assert called is False


def test_submit_rejects_invalid_rating_metadata_before_transport() -> None:
    called = False

    def transport(*_args) -> ProxyHTTPResponse:
        nonlocal called
        called = True
        return ProxyHTTPResponse(status=201, body=b"{}")

    result, status = submit_hivemind_feedback(
        {
            "response_id": "s1/t1",
            "session_id": "s1",
            "turn_id": "t1",
            "rating": 11,
            "pack_shared": False,
        },
        config=_config(),
        transport=transport,
    )

    assert status == 400
    assert result == {
        "ok": False,
        "error": "validation",
        "detail": "field 'rating' must be between 1 and 10.",
    }
    assert called is False


def test_submit_rejects_non_zip_base64_before_transport() -> None:
    called = False

    def transport(*_args) -> ProxyHTTPResponse:
        nonlocal called
        called = True
        return ProxyHTTPResponse(status=201, body=b"{}")

    result, status = submit_hivemind_feedback(
        {
            "response_id": "s1/t1",
            "session_id": "s1",
            "turn_id": "t1",
            "rating": 8,
            "pack_shared": True,
            "pack_zip_base64": base64.b64encode(b"not a zip").decode("ascii"),
        },
        config=_config(),
        transport=transport,
    )

    assert status == 400
    assert result == {
        "ok": False,
        "error": "validation",
        "detail": "field 'pack_zip_base64' must decode to a ZIP file.",
    }
    assert called is False


def test_submit_rejects_malformed_pack_base64_before_transport() -> None:
    called = False

    def transport(*_args) -> ProxyHTTPResponse:
        nonlocal called
        called = True
        return ProxyHTTPResponse(status=201, body=b"{}")

    result, status = submit_hivemind_feedback(
        {
            "response_id": "s1/t1",
            "session_id": "s1",
            "turn_id": "t1",
            "rating": 8,
            "pack_shared": True,
            "pack_zip_base64": "not-base64!",
        },
        config=_config(),
        transport=transport,
    )

    assert status == 400
    assert result == {
        "ok": False,
        "error": "validation",
        "detail": "field 'pack_zip_base64' must be valid base64.",
    }
    assert called is False


def test_submit_propagates_hivemind_structured_error() -> None:
    def transport(*_args) -> ProxyHTTPResponse:
        return ProxyHTTPResponse(
            status=422,
            body=b'{"error":"validation","detail":"duplicate response_id"}',
        )

    result, status = submit_hivemind_feedback(
        {
            "response_id": "s1/t1",
            "session_id": "s1",
            "turn_id": "t1",
            "rating": 8,
            "pack_shared": False,
        },
        config=_config(),
        transport=transport,
    )

    assert status == 422
    assert result == {
        "ok": False,
        "error": "validation",
        "detail": "duplicate response_id",
    }


def test_submit_rating_route_maps_hivemind_success_to_created(monkeypatch) -> None:
    from vibecomfy.comfy_nodes.agent import routes

    def fake_submit(payload: object) -> tuple[dict[str, object], int]:
        assert payload == {"response_id": "s1/t1"}
        return {"ok": True, "rating_id": "rating-1"}, 200

    monkeypatch.setattr(routes, "submit_hivemind_feedback", fake_submit)

    result, status = routes._handle_vibecomfy_submit_rating({"response_id": "s1/t1"})

    assert status == 201
    assert result == {"ok": True, "rating_id": "rating-1"}


def test_submit_rating_route_propagates_structured_errors(monkeypatch) -> None:
    from vibecomfy.comfy_nodes.agent import routes

    def fake_submit(_payload: object) -> tuple[dict[str, object], int]:
        return {"ok": False, "error": "validation", "detail": "bad rating"}, 400

    monkeypatch.setattr(routes, "submit_hivemind_feedback", fake_submit)

    result, status = routes._handle_vibecomfy_submit_rating({"rating": 99})

    assert status == 400
    assert result == {"ok": False, "error": "validation", "detail": "bad rating"}


def test_load_config_uses_server_side_env_values_only(monkeypatch) -> None:
    monkeypatch.setenv(CONTRIBUTOR_KEY_ENV, _key("c"))
    monkeypatch.setenv(ANON_KEY_ENV, "configured-anon-key")
    monkeypatch.setenv(EDGE_URL_ENV, "https://configured.example/rating")
    monkeypatch.setenv(MAX_ZIP_BYTES_ENV, "128")

    config = load_hivemind_feedback_config()

    assert config.contributor_key == _key("c")
    assert config.anon_key == "configured-anon-key"
    assert config.edge_url == "https://configured.example/rating"
    assert config.max_zip_bytes == 128


def test_contributor_key_env_name_is_not_referenced_from_browser_sources() -> None:
    repo = Path(__file__).resolve().parents[1]
    secret_env_name = "HIVEMIND_" + "CONTRIBUTOR_KEY"
    allowed_paths = {
        Path(".env.example"),
        Path("vibecomfy/comfy_nodes/agent/hivemind_feedback.py"),
        # Exact backend CLI consumers and their credential-configuration tests.
        # Browser sources and every other repository path remain covered.
        Path("scripts/upload_external_workflows_to_hivemind.py"),
        Path("scripts/upload_ready_templates_to_hivemind.py"),
        Path("tests/test_upload_external_workflows_to_hivemind.py"),
        Path("tests/test_upload_ready_templates_to_hivemind.py"),
    }
    searched_suffixes = {
        ".html",
        ".js",
        ".jsx",
        ".mjs",
        ".py",
        ".ts",
        ".tsx",
        ".vue",
    }
    violations: list[str] = []

    for path in repo.rglob("*"):
        relative = path.relative_to(repo)
        if ".git" in relative.parts or path.is_dir():
            continue
        if path.name != ".env.example" and path.suffix not in searched_suffixes:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if secret_env_name in text and relative not in allowed_paths:
            violations.append(str(relative))

    assert violations == []
