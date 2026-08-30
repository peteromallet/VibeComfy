from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from vibecomfy.porting.convert import (
    ManualTemplateRefusal,
    ConversionWriteError,
    PortConvertResult,
    PortConvertValidation,
    port_convert_and_write,
    port_convert_workflow,
)
from vibecomfy.porting.layout_store import write_layout
from vibecomfy.porting.workbench import analyze_source, load_port_source

from ._shared import (
    _attach_contract_fields,
    _attach_report_strict_ready,
    _attach_top_level_strict_ready,
    _emit_convert_payload,
    _emit_strict_ready_load_failure,
    _inject_schema_source_metadata,
)


_CONVERT_ALL_MAX_DEPTH = 32
_CONVERT_ALL_MAX_ITEMS = 100_000
_CONVERT_ALL_MAX_STRING_BYTES = 1 << 20
_CONVERT_ALL_MAX_NUMBER_BYTES = 4_000
_CONVERT_ALL_MAX_AGGREGATE_BYTES = 16 << 20
# Machine-mode aggregate limits: depth, items, per-string bytes, integer bytes,
# and total scalar/container bytes.


class AggregateNormalizationError(ValueError):
    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"{reason} at {path}")


class _BoundedJsonNormalizer:
    """Copy only exact builtin JSON values under explicit resource limits."""

    def __init__(self) -> None:
        self.item_count = 0
        self.aggregate_bytes = 0
        self._active: set[int] = set()

    def normalize(self, value: object, *, path: str = "$", depth: int = 0) -> object:
        if depth > _CONVERT_ALL_MAX_DEPTH:
            self._fail(path, "maximum nesting depth exceeded")

        value_type = type(value)
        if value is None:
            self._charge(4, path)
            return None
        if value_type is bool:
            self._charge(5 if value else 4, path)
            return value
        if value_type is int:
            estimated_bytes = max(1, (int.bit_length(value) + 2) // 3)
            if estimated_bytes > _CONVERT_ALL_MAX_NUMBER_BYTES:
                self._fail(path, "integer exceeds maximum scalar bytes")
            self._charge(estimated_bytes, path)
            return value
        if value_type is float:
            if not math.isfinite(value):
                self._fail(path, "non-finite float is not JSON-native")
            self._charge(24, path)
            return value
        if value_type is str:
            byte_count = self._string_bytes(value, path)
            self._charge(byte_count, path)
            return value

        if value_type is dict:
            return self._normalize_dict(value, path, depth)
        if value_type is list:
            return self._normalize_list(value, path, depth)
        if value_type is tuple:
            return self._normalize_tuple(value, path, depth)

        self._fail(path, "value must use an exact builtin JSON type")

    @staticmethod
    def _string_bytes(value: str, path: str) -> int:
        if len(value) > _CONVERT_ALL_MAX_STRING_BYTES:
            raise AggregateNormalizationError(path, "string exceeds maximum bytes")
        if str.isascii(value):
            byte_count = len(value)
        else:
            byte_count = len(str.encode(value, "utf-8"))
        if byte_count > _CONVERT_ALL_MAX_STRING_BYTES:
            raise AggregateNormalizationError(path, "string exceeds maximum bytes")
        return byte_count

    def _normalize_dict(self, value: dict[object, object], path: str, depth: int) -> dict[str, object]:
        value_id = id(value)
        active = self._active
        if value_id in active:
            self._fail(path, "cyclic value")
        active.add(value_id)
        try:
            result: dict[str, object] = {}
            self._charge(2, path)
            for index, (key, item) in enumerate(dict.items(value)):
                self._count_item(f"{path}.<key:{index}>")
                if type(key) is not str:
                    self._fail(f"{path}.<key:{index}>", "object key must be exact builtin str")
                self._charge(self._string_bytes(key, path), path)
                result[key] = self.normalize(item, path=f"{path}.{key}", depth=depth + 1)
            return result
        finally:
            active.remove(value_id)

    def _normalize_list(self, value: list[object], path: str, depth: int) -> list[object]:
        value_id = id(value)
        active = self._active
        if value_id in active:
            self._fail(path, "cyclic value")
        active.add(value_id)
        try:
            result: list[object] = []
            self._charge(2, path)
            for index, item in enumerate(list.__iter__(value)):
                self._count_item(f"{path}[{index}]")
                result.append(self.normalize(item, path=f"{path}[{index}]", depth=depth + 1))
            return result
        finally:
            active.remove(value_id)

    def _normalize_tuple(self, value: tuple[object, ...], path: str, depth: int) -> list[object]:
        value_id = id(value)
        active = self._active
        if value_id in active:
            self._fail(path, "cyclic value")
        active.add(value_id)
        try:
            result: list[object] = []
            self._charge(2, path)
            for index, item in enumerate(tuple.__iter__(value)):
                self._count_item(f"{path}[{index}]")
                result.append(self.normalize(item, path=f"{path}[{index}]", depth=depth + 1))
            return result
        finally:
            active.remove(value_id)

    def _count_item(self, path: str) -> None:
        self.item_count += 1
        if self.item_count > _CONVERT_ALL_MAX_ITEMS:
            self._fail(path, "maximum item count exceeded")

    def _charge(self, amount: int, path: str) -> None:
        self.aggregate_bytes += amount
        if self.aggregate_bytes > _CONVERT_ALL_MAX_AGGREGATE_BYTES:
            self._fail(path, "maximum aggregate bytes exceeded")

    @staticmethod
    def _fail(path: str, reason: str) -> None:
        raise AggregateNormalizationError(path, reason)


def _truncate_exact_text(value: str, max_bytes: int = _CONVERT_ALL_MAX_STRING_BYTES) -> str:
    if max_bytes <= 0:
        return ""
    try:
        if str.isascii(value) and len(value) <= max_bytes:
            return value
        encoded = str.encode(value, "utf-8")
    except BaseException:
        return ""
    if len(encoded) <= max_bytes:
        return value
    end = max_bytes
    while end > 0 and encoded[end - 1] & 0xC0 == 0x80:
        end -= 1
    try:
        return bytes.decode(encoded[:end], "utf-8")
    except BaseException:
        return ""


def _bounded_text(
    value: object,
    fallback: str | None,
    *,
    max_bytes: int = _CONVERT_ALL_MAX_STRING_BYTES,
) -> str | None:
    candidate = value if type(value) is str else fallback
    if candidate is None:
        return None
    if type(candidate) is not str:
        candidate = fallback
    if candidate is None:
        return None
    return _truncate_exact_text(candidate, max_bytes)


def _safe_exception_type(exc: BaseException, max_bytes: int = _CONVERT_ALL_MAX_STRING_BYTES) -> str:
    try:
        exc_type = type(exc)
        name = type.__getattribute__(exc_type, "__name__")
        if type(name) is str:
            return _truncate_exact_text(name, max_bytes)
    except BaseException:
        pass
    return "Exception"


def _safe_error_message(
    exc: BaseException,
    fallback: str = "conversion failed",
    *,
    max_bytes: int = _CONVERT_ALL_MAX_STRING_BYTES,
) -> str:
    try:
        args = BaseException.__getattribute__(exc, "args")
    except BaseException:
        return _truncate_exact_text(fallback, max_bytes)
    if type(args) is tuple:
        try:
            for arg in tuple.__iter__(args):
                if type(arg) is str:
                    return _truncate_exact_text(arg, max_bytes)
        except BaseException:
            pass
    return _truncate_exact_text(fallback, max_bytes)


def _cmd_port_convert(args: argparse.Namespace) -> int:
    from vibecomfy.commands import port as _port

    dry_run = getattr(args, "dry_run", False)
    diff_mode = getattr(args, "diff", False)
    all_mode = getattr(args, "all", False)

    # --all mode: refuse any mode that would write files
    if all_mode:
        if not dry_run and not diff_mode:
            print("--all requires --dry-run (or --diff). Refusing to write files in bulk.", file=sys.stderr)
            return 1
        if args.out:
            print("--all with --out is not supported. Use --dry-run --diff for corpus-wide preview.", file=sys.stderr)
            return 1
        return _run_convert_all(args)

    if not getattr(args, "workflow", None):
        print("workflow is required unless using --all.", file=sys.stderr)
        return 1

    # --out is required for write mode
    if not args.out and not dry_run and not diff_mode:
        print("--out is required for write mode. Use --dry-run for read-only preview.", file=sys.stderr)
        return 1

    schema_provider = _port._build_conversion_provider(args)
    port_mode: str = (
        "strict_ready"
        if getattr(args, "strict_ready_template", False)
        else "auto"
    )
    try:
        report = analyze_source(
            args.workflow,
            schema_provider=schema_provider,
            head_check_models=args.head_check_models,
            mode=port_mode,
        )
        _inject_schema_source_metadata(report, args)
        if getattr(args, "strict_ready_template", False):
            _port._apply_strict_ready_template_gate(report)
        if report.has_errors:
            payload = {
                "status": "error",
                "report": report.to_json(),
                "message": "port convert stopped because port check found hard errors.",
            }
            _attach_contract_fields(payload["report"])
            _attach_report_strict_ready(payload["report"])
            _emit_convert_payload(payload, json_output=args.json)
            return 1

        loaded = load_port_source(args.workflow, schema_provider=schema_provider)
        result = port_convert_workflow(
            loaded.workflow,
            ready_id=args.ready_id,
            source_path=loaded.source_path,
            provenance=report.provenance,
            source_hash=report.source_hash,
            workflow_shape=report.workflow_shape,
            schema_provider=schema_provider,
            raw_workflow=loaded.raw_workflow,
            keep_virtual_wires=bool(getattr(args, "keep_virtual_wires", False)),
        )
    except Exception as exc:
        return _emit_strict_ready_load_failure(
            args,
            exc,
            operation="convert",
            strict_enabled=bool(getattr(args, "strict_ready_template", False) or args.ready_id),
        )

    # Derive target path for dry-run diff mode
    if args.out:
        out = Path(args.out)
    elif dry_run or diff_mode:
        # Derive target from ready-template argument
        loaded = load_port_source(args.workflow, schema_provider=schema_provider)
        out = Path(loaded.source_path) if loaded.source_path else Path(args.workflow)
    else:
        print("--out is required for write mode.", file=sys.stderr)
        return 1

    try:
        write_result = port_convert_and_write(
            result,
            out,
            dry_run=dry_run,
            diff=diff_mode,
        )
    except ManualTemplateRefusal as exc:
        # In dry-run mode, skip manual refusal and show the diff anyway
        if dry_run:
            print(f"port convert note: {exc} (showing dry-run diff anyway)")
            # Compute diff directly
            original = out.read_text(encoding="utf-8") if out.exists() else ""
            import difflib
            diff_lines = difflib.unified_diff(
                original.splitlines(keepends=True) if original else [],
                result.text.splitlines(keepends=True),
                fromfile=str(out),
                tofile=f"{out} (emitted)",
            )
            parity = "ok" if result.validation and result.validation.parity_ok is True else (
                "failed" if result.validation and result.validation.parity_ok is False else "unknown"
            )
            print(f"parity: {parity}")
            print(f"LOC: {len(original.splitlines()) if original else 0} → {len(result.text.splitlines())} ({'+' if not original or len(result.text.splitlines()) >= len(original.splitlines()) else ''}{len(result.text.splitlines()) - (len(original.splitlines()) if original else 0)})")
            print("".join(diff_lines))
            return 0

        print(f"port convert refused: {exc}", file=sys.stderr)
        payload = {
            "status": "refused",
            "out": str(out),
            "message": str(exc),
            "conversion": result.to_json(),
            "report": report.to_json(),
        }
        _attach_contract_fields(payload["report"])
        _attach_report_strict_ready(payload["report"])
        _emit_convert_payload(payload, json_output=args.json)
        return 1
    except ConversionWriteError as exc:
        print(f"port convert failed: {exc}", file=sys.stderr)
        payload = {
            "status": "error",
            "out": str(out),
            "message": str(exc),
            "conversion": result.to_json(),
            "report": report.to_json(),
        }
        _attach_top_level_strict_ready(payload)
        _attach_contract_fields(payload["report"])
        _emit_convert_payload(payload, json_output=args.json)
        return 1

    # Emit layout sidecar alongside the .py (skip in dry-run/diff)
    if not dry_run and not diff_mode:
        try:
            write_layout(out, loaded.workflow)
        except Exception:
            pass  # Sidecar write is best-effort; never block the main convert

    payload = {
        "status": "ok" if write_result["written"] or write_result["dry_run"] else "error",
        "out": str(out),
        "conversion": result.to_json(),
        "report": report.to_json(),
        "write": write_result,
    }
    _attach_top_level_strict_ready(payload)
    _attach_contract_fields(payload["report"])
    _attach_report_strict_ready(payload["report"])
    _emit_convert_payload(payload, json_output=args.json)
    return 0


def _run_convert_all(args: argparse.Namespace) -> int:
    """Run bounded conversion across all ready templates."""
    from vibecomfy.analysis.corpus import CorpusSnapshot, build_corpus_snapshot
    from vibecomfy.commands import port as _port
    from vibecomfy.porting.workbench import LoadedPortSource

    diff_mode = getattr(args, "diff", False) is True
    json_output = getattr(args, "json", False) is True
    template_results: list[dict[str, Any]] = []
    missing = object()

    def _field(value: object, name: str, default: object = missing) -> object:
        value_type = type(value)
        if value_type is dict:
            return dict.get(value, name, default)
        if value_type is SimpleNamespace:
            fields = object.__getattribute__(value, "__dict__")
            if type(fields) is not dict:
                raise TypeError("object fields must use an exact builtin dict")
            return dict.get(fields, name, default)
        if value_type in (
            CorpusSnapshot,
            LoadedPortSource,
            PortConvertResult,
            PortConvertValidation,
        ):
            try:
                return object.__getattribute__(value, name)
            except AttributeError:
                return default
        raise TypeError("aggregate object has an unsupported result type")

    def _exact_text(value: object, *, field_name: str) -> str:
        if type(value) is not str:
            raise TypeError(f"{field_name} must be exact builtin str")
        return value

    def _display_text(
        value: object,
        fallback: str | None,
        *,
        max_bytes: int = _CONVERT_ALL_MAX_STRING_BYTES,
    ) -> str | None:
        return _bounded_text(value, fallback, max_bytes=max_bytes)

    def _failure_result(
        template_id: object,
        tpl_path: object,
        exc: BaseException,
        *,
        fallback_id: str,
    ) -> dict[str, Any]:
        return {
            "id": _display_text(template_id, fallback_id),
            "path": _display_text(tpl_path, None),
            "status": "error",
            "parity": None,
            "original_loc": None,
            "emitted_loc": None,
            "line_count_delta": None,
            "changed": None,
            "error": {
                "type": _safe_exception_type(exc),
                "message": _safe_error_message(exc),
            },
        }

    def _normalize_row(
        row: dict[str, object],
        *,
        template_id: object,
        tpl_path: object,
        fallback_id: str,
    ) -> dict[str, Any]:
        try:
            normalized = _BoundedJsonNormalizer().normalize(row)
            if type(normalized) is not dict:
                raise TypeError("normalized row must be exact builtin dict")
            return normalized
        except BaseException as exc:
            return _failure_result(
                template_id,
                tpl_path,
                exc,
                fallback_id=fallback_id,
            )

    def _compact_row(row: object, index: int, max_bytes: int) -> dict[str, object]:
        fallback_id = f"<row-{index}>"
        if type(row) is not dict:
            return _failure_result(
                fallback_id,
                None,
                TypeError("aggregate row must be an exact builtin dict"),
                fallback_id=fallback_id,
            )
        status = _display_text(dict.get(row, "status"), "error", max_bytes=max_bytes) or "error"
        error_value = dict.get(row, "error", None)
        if type(error_value) is dict:
            error: object = {
                "type": _display_text(dict.get(error_value, "type"), "Exception", max_bytes=max_bytes)
                or "Exception",
                "message": _display_text(
                    dict.get(error_value, "message"),
                    "conversion failed",
                    max_bytes=max_bytes,
                )
                or "conversion failed",
            }
        else:
            error = None
        return {
            "id": _display_text(dict.get(row, "id"), fallback_id, max_bytes=max_bytes) or fallback_id,
            "path": _display_text(dict.get(row, "path"), None, max_bytes=max_bytes),
            "status": status,
            "parity": _display_text(dict.get(row, "parity"), None, max_bytes=max_bytes),
            "original_loc": dict.get(row, "original_loc") if type(dict.get(row, "original_loc")) is int else None,
            "emitted_loc": dict.get(row, "emitted_loc") if type(dict.get(row, "emitted_loc")) is int else None,
            "line_count_delta": (
                dict.get(row, "line_count_delta")
                if type(dict.get(row, "line_count_delta")) is int
                else None
            ),
            "changed": dict.get(row, "changed") if type(dict.get(row, "changed")) is bool else None,
            "error": error,
        }

    def _machine_error(exc: BaseException, rows: list[dict[str, Any]]) -> dict[str, Any]:
        raw_rows: list[object] = []
        if type(rows) is list:
            for index, row in enumerate(list.__iter__(rows)):
                if index >= 1_000:
                    break
                raw_rows.append(row)
        aggregate_row = _failure_result("<aggregate>", None, exc, fallback_id="<aggregate>")

        def _payload(max_bytes: int) -> dict[str, object]:
            safe_rows = [
                _compact_row(row, index, max_bytes)
                for index, row in enumerate(raw_rows)
            ]
            safe_rows.append(_compact_row(aggregate_row, len(safe_rows), max_bytes))
            error_count = sum(
                1
                for item in safe_rows
                if dict.get(item, "status") == "error"
            )
            return {
                "status": "error",
                "mode": "convert_all",
                "dry_run": True,
                "templates": safe_rows,
                "summary": {
                    "template_count": len(safe_rows),
                    "ok_count": len(safe_rows) - error_count,
                    "error_count": error_count,
                    "changed_count": sum(
                        1
                        for item in safe_rows
                        if dict.get(item, "status") == "ok"
                        and dict.get(item, "changed") is True
                    ),
                },
                "error": {
                    "type": "AggregateNormalizationError",
                    "message": _safe_error_message(
                        exc,
                        "aggregate serialization failed",
                        max_bytes=max_bytes,
                    ),
                },
            }

        for max_bytes in (1_024, 256, 64, 16, 0):
            try:
                payload = _BoundedJsonNormalizer().normalize(_payload(max_bytes))
                if type(payload) is dict:
                    return payload
            except BaseException:
                continue
        return {
            "status": "error",
            "mode": "convert_all",
            "dry_run": True,
            "templates": [
                {
                    "id": "<aggregate>",
                    "path": None,
                    "status": "error",
                    "parity": None,
                    "original_loc": None,
                    "emitted_loc": None,
                    "line_count_delta": None,
                    "changed": None,
                    "error": {
                        "type": "AggregateNormalizationError",
                        "message": "aggregate serialization failed",
                    },
                }
            ],
            "summary": {
                "template_count": 1,
                "ok_count": 0,
                "error_count": 1,
                "changed_count": 0,
            },
            "error": {
                "type": "AggregateNormalizationError",
                "message": "aggregate serialization failed",
            },
        }

    try:
        snapshot = build_corpus_snapshot()
        templates = _field(snapshot, "templates_list")
        if type(templates) is not list:
            raise TypeError("templates_list must be an exact builtin list")
        template_limit = min(len(templates), _CONVERT_ALL_MAX_ITEMS)
    except BaseException as exc:
        if not json_output:
            print(f"<aggregate>: error: {_safe_exception_type(exc)}: {_safe_error_message(exc)}")
            return 0
        payload = _machine_error(exc, template_results)
        print(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))
        return 1

    for row_index in range(template_limit):
        fallback_id = f"<row-{row_index}>"
        template_id: object = fallback_id
        tpl_path: object = None
        try:
            tpl = list.__getitem__(templates, row_index)
            if type(tpl) is not dict:
                raise TypeError("template row must be an exact builtin dict")
            raw_id = dict.get(tpl, "id", missing)
            if raw_id is missing:
                raise KeyError("id")
            template_id = _exact_text(raw_id, field_name="template id")
            raw_path = dict.get(tpl, "path", missing)
            if raw_path is missing:
                raise KeyError("path")
            tpl_path = _exact_text(raw_path, field_name="template path")
            source_path = Path(tpl_path)
            if not source_path.is_file():
                raise FileNotFoundError(f"template source does not exist: {tpl_path}")
            original = source_path.read_text(encoding="utf-8")
            original = _exact_text(original, field_name="source text")
            schema_provider = _port._build_conversion_provider(args)
            loaded = load_port_source(tpl_path, schema_provider=schema_provider)
            workflow = _field(loaded, "workflow")
            raw_workflow = _field(loaded, "raw_workflow", None)
            result = port_convert_workflow(
                workflow,
                source_path=tpl_path,
                schema_provider=schema_provider,
                raw_workflow=raw_workflow,
            )

            result_text = _field(result, "text")
            result_text = _exact_text(result_text, field_name="conversion result text")
            validation = _field(result, "validation", None)
            if validation is None:
                parity = "no-validation"
                validation_failed = True
                validation_error: object = "conversion produced no validation result"
            else:
                parity_ok = _field(validation, "parity_ok", None)
                if parity_ok is not None and type(parity_ok) is not bool:
                    raise TypeError("validation parity_ok must be exact builtin bool or None")
                if parity_ok is True:
                    parity = "ok"
                elif parity_ok is False:
                    parity = "failed"
                else:
                    parity = "unknown"
                validation_ok = _field(validation, "ok", True)
                if type(validation_ok) is not bool:
                    raise TypeError("validation ok must be exact builtin bool")
                validation_failed = validation_ok is False or parity_ok is False
                validation_error = _field(validation, "error", None)
                if validation_error is None:
                    validation_error = _field(validation, "parity_error", None)
                if validation_error is None:
                    validation_error = "conversion validation failed"

            original_lines = str.splitlines(original)
            emitted_lines = str.splitlines(result_text)
            original_loc = sum(1 for line in original_lines if str.strip(line))
            emitted_loc = sum(1 for line in emitted_lines if str.strip(line))
            changed = result_text != original
            row: dict[str, object] = {
                "id": template_id,
                "path": tpl_path,
                "status": "error" if validation_failed else "ok",
                "parity": parity,
                "original_loc": original_loc,
                "emitted_loc": emitted_loc,
                "line_count_delta": emitted_loc - original_loc,
                "changed": changed,
                "error": (
                    {
                        "type": "ValidationError",
                        "message": validation_error,
                    }
                    if validation_failed
                    else None
                ),
            }
            if json_output:
                template_results.append(
                    _normalize_row(
                        row,
                        template_id=template_id,
                        tpl_path=tpl_path,
                        fallback_id=fallback_id,
                    )
                )
            else:
                delta = emitted_loc - original_loc
                print(
                    f"{template_id}: parity={parity} LOC "
                    f"{original_loc}→{emitted_loc} "
                    f"({'+' if delta >= 0 else ''}{delta})"
                )
                if diff_mode and changed:
                    import difflib

                    diff_lines = difflib.unified_diff(
                        str.splitlines(original, keepends=True),
                        str.splitlines(result_text, keepends=True),
                        fromfile=tpl_path,
                        tofile=f"{tpl_path} (emitted)",
                    )
                    diff_text = "".join(diff_lines)
                    if diff_text:
                        print(diff_text[:2000])
        except BaseException as exc:
            if json_output:
                template_results.append(
                    _normalize_row(
                        _failure_result(
                            template_id,
                            tpl_path,
                            exc,
                            fallback_id=fallback_id,
                        ),
                        template_id=template_id,
                        tpl_path=tpl_path,
                        fallback_id=fallback_id,
                    )
                )
            else:
                print(
                    f"{_display_text(template_id, fallback_id)}: error: "
                    f"{_safe_exception_type(exc)}: "
                    f"{_safe_error_message(exc)}"
                )

    if template_limit < len(templates):
        overflow = AggregateNormalizationError(
            "$.templates",
            "maximum template row count exceeded",
        )
        if json_output:
            template_results.append(
                _normalize_row(
                    _failure_result(
                        f"<row-{template_limit}>",
                        None,
                        overflow,
                        fallback_id=f"<row-{template_limit}>",
                    ),
                    template_id=f"<row-{template_limit}>",
                    tpl_path=None,
                    fallback_id=f"<row-{template_limit}>",
                )
            )
        else:
            print("<aggregate>: error: maximum template row count exceeded")

    if not json_output:
        return 0

    error_count = sum(
        1
        for item in template_results
        if dict.get(item, "status") == "error"
    )
    payload = {
        "status": "error" if error_count else "ok",
        "mode": "convert_all",
        "dry_run": True,
        "templates": template_results,
        "summary": {
            "template_count": len(template_results),
            "ok_count": len(template_results) - error_count,
            "error_count": error_count,
            "changed_count": sum(
                1
                for item in template_results
                if dict.get(item, "status") == "ok"
                and dict.get(item, "changed") is True
            ),
        },
    }
    try:
        normalized_payload = _BoundedJsonNormalizer().normalize(payload)
        print(json.dumps(normalized_payload, indent=2, sort_keys=True, allow_nan=False))
    except BaseException as exc:
        print(json.dumps(_machine_error(exc, template_results), indent=2, sort_keys=True, allow_nan=False))
        return 1
    return 1 if error_count else 0
