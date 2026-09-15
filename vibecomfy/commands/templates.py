"""Curated ready-template promotion from an existing canonical bundle."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from vibecomfy.cli_loader import load_bundle
from vibecomfy.security.provenance import Provenance
from vibecomfy.workflow_bundle import emit_bundle_with_candidate


def _template_id(value: str) -> str:
    value = str(value).strip()
    parts = value.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError("template id must have the form <media>/<name>")
    return value


def _payload(*, status: str, bundle: str, template_id: str, out: Path, **extra: Any) -> dict[str, Any]:
    return {
        "status": status,
        "bundle": bundle,
        "template_id": template_id,
        "out": str(out),
        **extra,
    }


def _emit(payload: dict[str, Any], *, json_output: bool) -> int:
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    elif payload.get("status") == "error":
        print(f"Template creation failed: {payload.get('message', 'unknown error')}")
    else:
        action = "Would create" if payload.get("status") == "preview" else "Created"
        print(f"{action} ready template {payload['template_id']} at {payload['out']}")
        if payload.get("companion"):
            print(f"  Companion: {payload['companion']}")
        print("  Source JSON is not regenerated or copied; the input bundle remains the source evidence.")
    return 1 if payload.get("status") == "error" else 0


def _cmd_create(args: argparse.Namespace) -> int:
    template_id = str(args.template_id)
    out = Path(args.out).expanduser()
    bundle_path = Path(args.bundle).expanduser()
    try:
        template_id = _template_id(template_id)
        if not bundle_path.exists():
            raise FileNotFoundError(f"bundle does not exist: {bundle_path}")
        if out.is_dir():
            raise FileExistsError(f"output is a directory: {out}")
        if out.exists() and not args.dry_run:
            raise FileExistsError(f"output already exists: {out}; choose another --out path")

        bundle = load_bundle(bundle_path, trust=Provenance.USER_CONFIRMED)
        bundle.require_canonical_authority("ready-template creation")
        workflow = bundle.workflow.copy()
        workflow.id = template_id
        workflow.source.id = template_id
        workflow.metadata["ready_template"] = template_id
        workflow.metadata["workflow_template"] = template_id.rsplit("/", 1)[-1]
        workflow.metadata["ready_id"] = template_id
        workflow.metadata["capability"] = template_id.split("/", 1)[0]
        # The candidate is a new authored identity. Preserve the imported
        # source as provenance evidence, while updating every executable
        # identity witness to the promoted template id.
        workflow.metadata["source_id"] = template_id
        workflow.metadata["workflow_source_id"] = template_id
        existing_provenance = workflow.metadata.get("provenance")
        provenance = dict(existing_provenance) if isinstance(existing_provenance, dict) else {}
        provenance.update({
            "source_id": template_id,
            "ready_id": template_id,
        })
        workflow.metadata["provenance"] = provenance

        bundle_provenance = dict(bundle.provenance)
        bundle_provenance.update({
            "operation": "authored",
            "artifact_class": "execution_ready_candidate",
            "execution_ready": False,
            "origin_kind": bundle_provenance.get("origin_kind", "local_bundle"),
            "origin_uri": bundle_provenance.get("origin_uri", str(bundle_path)),
        })
        source_provenance = {
            "ready_id": template_id,
            "source_kind": "canonical_bundle",
            "output_mode": "ready_template",
        }

        if args.dry_run:
            with tempfile.TemporaryDirectory(prefix="vibecomfy-template-create-") as temporary:
                candidate = emit_bundle_with_candidate(
                    workflow,
                    Path(temporary) / out.name,
                    bundle_provenance,
                    None,
                    operation="authored",
                    source_provenance=source_provenance,
                    source_format="ready_template",
                )
        else:
            candidate = emit_bundle_with_candidate(
                workflow,
                out,
                bundle_provenance,
                None,
                operation="authored",
                source_provenance=source_provenance,
                source_format="ready_template",
            )
    except Exception as exc:  # command boundary renders a stable error payload
        return _emit(
            _payload(
                status="error",
                bundle=str(bundle_path),
                template_id=str(args.template_id),
                out=out,
                message=f"{type(exc).__name__}: {exc}",
            ),
            json_output=args.json,
        )

    return _emit(
        _payload(
            status="preview" if args.dry_run else "ok",
            bundle=str(bundle_path),
            template_id=template_id,
            out=out,
            companion=str(out.with_suffix(".vibe.json")),
            candidate_status="preview" if args.dry_run else "created",
            static_validation="not_run",
            dependency_resolution="not_run",
            runtime_verification="not_run",
            ready_eligible=False,
            revision_id=candidate.revision_id,
            semantic_digest=candidate.semantic_digest,
            ui_digest=candidate.ui_digest,
        ),
        json_output=args.json,
    )


def register(subparsers) -> None:
    templates = subparsers.add_parser(
        "templates",
        help="Create and inspect curated ready templates.",
    )
    verbs = templates.add_subparsers(dest="templates_cmd", required=True)
    create = verbs.add_parser(
        "create",
        help="Promote an existing canonical workflow bundle to a ready template.",
        description=(
            "Create a curated ready-template Python/companion pair from an existing "
            "canonical bundle. This consumes the authored bundle and does not read "
            "or regenerate source.json. Run validate/doctor first for readiness diagnostics."
        ),
    )
    create.add_argument("bundle", help="Canonical workflow bundle directory or workflow.py.")
    create.add_argument("--id", dest="template_id", required=True, help="Ready-template id: <media>/<name>.")
    create.add_argument("--out", required=True, help="Destination ready-template Python file.")
    create.add_argument("--dry-run", action="store_true", help="Validate and preview without writing files.")
    create.add_argument("--json", action="store_true", help="Print machine-readable output.")
    create.set_defaults(func=_cmd_create)


__all__ = ["register"]
