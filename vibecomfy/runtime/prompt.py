from __future__ import annotations

import os
from typing import Any

from vibecomfy.errors import VibeComfyError, WorkflowBuildError, WorkflowValidationError
from vibecomfy.workflow import VibeWorkflow


def emit_schema_unavailable_once(owner: Any, logger: Any, msg: str) -> None:
    if getattr(owner, "_schema_warning_emitted", False):
        return
    logger.warning("vibecomfy schema gate: %s", msg)
    owner._schema_warning_emitted = True


def _schema_validate_disabled() -> bool:
    return os.environ.get("VIBECOMFY_SCHEMA_VALIDATE", "1").strip() in {"0", "false", "False", "no", "off"}


def _build_schema_provider(server_url: str | None) -> Any | None:
    if _schema_validate_disabled():
        return None
    from vibecomfy.schema import RuntimeSchemaProvider

    return RuntimeSchemaProvider(server_url=server_url)


async def _warm_schema_provider(
    provider: Any | None,
    *,
    on_unavailable,
    cache_only: bool = False,
) -> Any | None:
    if provider is None:
        return None
    try:
        if getattr(provider, "_object_info", None) is not None:
            return provider
        if cache_only:
            from vibecomfy.schema.cache import load_object_info_cache, validate_object_info_cache

            cached = load_object_info_cache(provider.cache_path)
            if cached is None:
                on_unavailable(f"object_info cache unavailable at {provider.cache_path}; using structural validation only")
                return None
            expected = (
                provider._cache_validation_expected()
                if callable(getattr(provider, "_cache_validation_expected", None))
                else {}
            )
            result = validate_object_info_cache(
                cached,
                expected=expected,
                policy="strict",
                cache_path=provider.cache_path,
            )
            if not result.ok:
                on_unavailable(
                    f"object_info cache rejected at {provider.cache_path}: {result.reason}; "
                    "using structural validation only"
                )
                return None
            setter = getattr(provider, "_set_object_info", None)
            if callable(setter):
                setter(cached)
            else:
                provider._object_info = cached
            return provider

        provider._object_info = await provider.object_info_async()
        return provider
    except (OSError, RuntimeError, TimeoutError) as exc:
        on_unavailable(f"{type(exc).__name__}: {exc}; using structural validation only")
        return None


def _prepare_prompt(
    workflow: VibeWorkflow,
    *,
    backend: str,
    schema_provider: Any | None = None,
) -> dict[str, Any]:
    # Schema validation: cache-hit on every submit after the first per-runtime; first-fetch latency acceptable.
    report = workflow.validate(schema_provider=schema_provider)
    if not report.ok:
        messages = "; ".join(issue.message for issue in report.issues)
        raise WorkflowValidationError(
            f"Workflow validation failed: {messages}",
            next_action="Fix the reported workflow validation issues before queueing this workflow.",
        )

    try:
        return workflow.compile(backend=backend)
    except VibeComfyError:
        raise
    except ValueError as exc:
        raise WorkflowBuildError(
            f"Workflow build failed: {exc}",
            next_action="Check the compile backend and workflow graph, then rebuild the workflow.",
        ) from exc
    except RuntimeError as exc:
        raise WorkflowBuildError(
            f"Workflow build failed: {exc}",
            next_action="Check the workflow graph and any generated scratchpad code before retrying.",
        ) from exc
    except Exception as exc:
        raise WorkflowBuildError(
            f"Workflow build failed: {exc}",
            next_action="Check the workflow graph and any generated scratchpad code before retrying.",
        ) from exc


async def _prepare_prompt_async(
    workflow: VibeWorkflow,
    *,
    backend: str,
    schema_provider: Any | None,
    on_unavailable,
    cache_only: bool = False,
) -> dict[str, Any]:
    effective = await _warm_schema_provider(
        schema_provider,
        on_unavailable=on_unavailable,
        cache_only=cache_only,
    )
    report = workflow.validate(schema_provider=effective)
    if not report.ok:
        raise WorkflowValidationError(
            _validation_failed_message(report),
            next_action="Fix the reported workflow validation issues before queueing this workflow.",
        )

    try:
        return workflow.compile(backend=backend)
    except VibeComfyError:
        raise
    except ValueError as exc:
        raise WorkflowBuildError(
            f"Workflow build failed: {exc}",
            next_action="Check the compile backend and workflow graph, then rebuild the workflow.",
        ) from exc
    except RuntimeError as exc:
        raise WorkflowBuildError(
            f"Workflow build failed: {exc}",
            next_action="Check the workflow graph and any generated scratchpad code before retrying.",
        ) from exc
    except Exception as exc:
        raise WorkflowBuildError(
            f"Workflow build failed: {exc}",
            next_action="Check the workflow graph and any generated scratchpad code before retrying.",
        ) from exc


def _validation_failed_message(report: Any) -> str:
    from vibecomfy.schema.validate import format_issue

    return "Workflow validation failed:\n  - " + "\n  - ".join(
        format_issue(issue) for issue in report.issues if issue.severity == "error"
    )
