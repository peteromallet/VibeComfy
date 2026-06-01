"""Opt-in live ComfyUI smoke for the durable VibeComfy agent panel.

This is intentionally excluded from the normal hard gate. When a real ComfyUI
frontend is available, set ``VIBECOMFY_COMFY_SMOKE=1`` and point
``VIBECOMFY_COMFYUI_URL`` at the running server to verify that the shipped
extension loads in the live editor, opens the durable panel, talks to a stubbed
backend, applies a tiny candidate graph, and logs no uncaught JavaScript
errors.
"""

from __future__ import annotations

import json
import os

import pytest

pw = pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright

pytestmark = [pytest.mark.comfy, pytest.mark.info]

_BASE_URL = os.getenv("VIBECOMFY_COMFYUI_URL", "http://127.0.0.1:8188/")


def _require_live_smoke() -> None:
    if os.getenv("VIBECOMFY_COMFY_SMOKE") != "1":
        pytest.skip(
            "Set VIBECOMFY_COMFY_SMOKE=1 and VIBECOMFY_COMFYUI_URL=http://host:port to run the live ComfyUI smoke."
        )


def _json_clone(value):
    return json.loads(json.dumps(value))


def _candidate_graph_from(graph: dict) -> dict:
    candidate = _json_clone(graph)
    extra = candidate.get("extra")
    if not isinstance(extra, dict):
        extra = {}
    extra["vibecomfy_live_smoke"] = {"applied": True}
    candidate["extra"] = extra
    return candidate


def _open_panel(page) -> str:
    return page.evaluate(
        """() => {
          const commandId = "VibeComfy.AgentEdit";
          const roots = [
            window.comfyAPI?.app?.app,
            window.comfyAPI?.app,
            window.app,
          ].filter(Boolean);

          const tryContainer = (container) => {
            if (!container) return null;
            if (Array.isArray(container)) {
              for (const entry of container) {
                if (entry?.id === commandId && typeof entry.function === "function") {
                  entry.function();
                  return "array";
                }
              }
              return null;
            }
            if (container instanceof Map) {
              const entry = container.get(commandId);
              if (entry && typeof entry.function === "function") {
                entry.function();
                return "map";
              }
              return null;
            }
            if (typeof container === "object") {
              if (container[commandId] && typeof container[commandId].function === "function") {
                container[commandId].function();
                return "object";
              }
              for (const entry of Object.values(container)) {
                if (entry?.id === commandId && typeof entry.function === "function") {
                  entry.function();
                  return "object-values";
                }
              }
            }
            return null;
          };

          for (const root of roots) {
            const mode = tryContainer(root.commands)
              || tryContainer(root.extensionManager?.commands)
              || tryContainer(root.extensionManager?.commandManager?.commands)
              || tryContainer(root.extensions)
              || tryContainer(root.extensionManager?.extensions);
            if (mode) return `command:${mode}`;
          }

          const panelRoot = document.getElementById("vibecomfy-agent-panel-root");
          if (panelRoot) {
            panelRoot.dataset.open = "1";
            panelRoot.style.transform = "translateX(0px)";
            return "dom-fallback";
          }
          return null;
        }"""
    )


def test_live_comfyui_agent_panel_smoke() -> None:
    _require_live_smoke()

    console_errors: list[str] = []
    page_errors: list[str] = []
    captured: dict[str, object] = {}

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        except Exception as exc:
            if "Executable doesn't exist" in str(exc):
                pytest.skip(
                    "Playwright browsers not installed. Run: python -m playwright install chromium"
                )
            raise
        context = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = context.new_page()

        page.on(
            "console",
            lambda msg: console_errors.append(f"[{msg.type}] {msg.text}")
            if msg.type == "error"
            else None,
        )
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        def _handle_status(route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "ok": True,
                        "requested_route": "deepseek",
                        "route": "deepseek",
                        "provider_available": True,
                        "model": "deepseek-chat",
                        "route_options": {
                            "auto": {
                                "requested_route": "auto",
                                "normalized_route": "arnold",
                                "browser_api_key_allowed": False,
                                "guidance": "Arnold/Hermes guidance",
                                "tos_acknowledgement_required": False,
                            },
                            "deepseek": {
                                "requested_route": "deepseek",
                                "normalized_route": "deepseek",
                                "browser_api_key_allowed": True,
                                "guidance": "DeepSeek browser key supported",
                                "tos_acknowledgement_required": False,
                            },
                            "anthropic": {
                                "requested_route": "anthropic",
                                "normalized_route": "arnold",
                                "browser_api_key_allowed": False,
                                "guidance": "Anthropic guidance",
                                "tos_acknowledgement_required": True,
                            },
                            "openai-codex": {
                                "requested_route": "openai-codex",
                                "normalized_route": "arnold",
                                "browser_api_key_allowed": False,
                                "guidance": "Codex guidance",
                                "tos_acknowledgement_required": False,
                            },
                        },
                    }
                ),
            )

        def _handle_credentials(route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"ok": True, "stored": True}),
            )

        def _handle_submit(route, request):
            payload = request.post_data_json or {}
            captured["submit"] = payload
            candidate = _candidate_graph_from(payload["graph"])
            captured["candidate"] = candidate
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "ok": True,
                        "session_id": "live-smoke-session",
                        "turn_id": "0001",
                        "baseline_turn_id": "0000",
                        "canvas_apply_allowed": True,
                        "apply_allowed": True,
                        "queue_allowed": True,
                        "message": "Stubbed live smoke candidate ready.",
                        "graph": candidate,
                        "report": {
                            "change": {
                                "content_edits": {
                                    "preserved": [],
                                    "edited": [],
                                    "new_auto_placed": [],
                                    "removed": [],
                                    "removed_named": [],
                                    "virtual_wires_degraded": [],
                                    "stripped_helpers": [],
                                },
                                "identity_stabilization": {"preserved_count": 0},
                            },
                            "recovery": [],
                            "felt": {"ok": True},
                        },
                        "artifacts": {},
                        "audit_ref": {"path": "out/live-smoke/audit.json"},
                        "version": 1,
                    }
                ),
            )

        def _handle_accept(route, request):
            payload = request.post_data_json or {}
            captured["accept"] = payload
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "ok": True,
                        "action": "accept",
                        "session_id": payload.get("session_id") or "live-smoke-session",
                        "turn_id": payload.get("turn_id") or "0001",
                        "baseline_turn_id": "0001",
                        "queue_allowed": True,
                        "audit_ref": {"path": "out/live-smoke/audit.json"},
                    }
                ),
            )

        def _handle_reject(route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "ok": True,
                        "action": "reject",
                        "session_id": "live-smoke-session",
                        "turn_id": "0001",
                        "baseline_turn_id": "0000",
                    }
                ),
            )

        page.route("**/vibecomfy/agent/status**", _handle_status)
        page.route("**/vibecomfy/agent/credentials", _handle_credentials)
        page.route("**/vibecomfy/agent-edit/accept", _handle_accept)
        page.route("**/vibecomfy/agent-edit/reject", _handle_reject)
        page.route("**/vibecomfy/agent-edit", _handle_submit)

        page.goto(_BASE_URL, wait_until="networkidle", timeout=60000)
        page.wait_for_function(
            """() => !!(
              document.getElementById("vibecomfy-agent-panel-root") &&
              (window.comfyAPI?.app?.app?.loadGraphData || window.app?.loadGraphData)
            )""",
            timeout=60000,
        )
        page.evaluate(
            """() => {
              const app = window.comfyAPI?.app?.app || window.app;
              window.__vibecomfyLiveSmoke = { loadGraphDataCalls: [] };
              if (!app.__vibecomfyLiveSmokeWrapped) {
                const original = app.loadGraphData.bind(app);
                app.loadGraphData = (graph) => {
                  window.__vibecomfyLiveSmoke.loadGraphDataCalls.push(JSON.parse(JSON.stringify(graph)));
                  return original(graph);
                };
                app.__vibecomfyLiveSmokeWrapped = true;
              }
            }"""
        )

        open_mode = _open_panel(page)
        assert open_mode, "could not open the live VibeComfy panel"
        page.wait_for_function(
            """() => document.getElementById("vibecomfy-agent-panel-root")?.dataset.open === "1" """,
            timeout=15000,
        )

        page.locator("#vibecomfy-agent-panel-prompt").fill("live smoke stub candidate")
        page.locator("#vibecomfy-agent-panel-submit").click()
        page.wait_for_function(
            """() => document.getElementById("vibecomfy-agent-panel-status")?.textContent === "AWAITING_REVIEW" """,
            timeout=30000,
        )
        page.locator("#vibecomfy-agent-panel-apply").click()
        page.wait_for_function(
            """() => (window.__vibecomfyLiveSmoke?.loadGraphDataCalls?.length || 0) >= 1 """,
            timeout=30000,
        )

        submit_payload = captured["submit"]
        assert isinstance(submit_payload, dict)
        assert "baseline_turn_id" not in submit_payload

        accept_payload = captured["accept"]
        assert isinstance(accept_payload, dict)
        assert accept_payload["session_id"] == "live-smoke-session"
        assert accept_payload["turn_id"] == "0001"

        load_calls = page.evaluate("() => window.__vibecomfyLiveSmoke.loadGraphDataCalls")
        assert len(load_calls) == 1
        assert load_calls[0] == captured["candidate"]

        actionable_console_errors = [
            entry
            for entry in console_errors
            if "VibeComfy" in entry or "Uncaught" in entry or "TypeError" in entry or "ReferenceError" in entry
        ]
        assert not page_errors, f"uncaught page errors: {page_errors}"
        assert not actionable_console_errors, (
            "unexpected live smoke console errors: "
            f"{actionable_console_errors}"
        )

        context.close()
        browser.close()
