from __future__ import annotations

import dataclasses
from typing import Any


def _handle_roundtrip(
    payload: dict[str, Any], *, schema_provider: Any = None
) -> dict[str, Any]:
    """Torch-free core: convert UI graph + emit, return enriched graph + change report.

    All engine imports are lazy so this function is importable without ComfyUI or torch.
    Call from tests directly; the aiohttp wrapper below delegates to this.
    """
    from vibecomfy.ingest.normalize import convert_to_vibe_format  # noqa: PLC0415
    from vibecomfy.porting.ui_emitter import emit_ui_json  # noqa: PLC0415
    from vibecomfy.schema import get_schema_provider  # noqa: PLC0415

    try:
        if schema_provider is None:
            schema_provider = get_schema_provider("local")
        recovery_report: list = []
        change_report_out: list = []
        wf = convert_to_vibe_format(payload["graph"])
        emitted_ui = emit_ui_json(
            wf,
            schema_provider=schema_provider,
            recovery_report=recovery_report,
            change_report_out=change_report_out,
            guard_original_ui=payload["graph"],
        )
        change_dict = dataclasses.asdict(change_report_out[0]) if change_report_out else {}
        return {
            "graph": emitted_ui,
            "report": {"change": change_dict, "recovery": recovery_report},
            "version": 1,
        }
    except Exception as exc:
        return {"error": str(exc), "kind": type(exc).__name__}


try:
    from aiohttp import web as _web  # noqa: PLC0415
    from server import PromptServer as _PromptServer  # noqa: PLC0415

    @_PromptServer.instance.routes.post("/vibecomfy/roundtrip")
    async def roundtrip_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _web.json_response(
                {"error": str(exc), "kind": type(exc).__name__}, status=400
            )
        result = _handle_roundtrip(payload)
        if "error" in result:
            return _web.json_response(result, status=400)
        return _web.json_response(result)

except ImportError:
    pass
