from __future__ import annotations

from collections.abc import Iterable
import re
from dataclasses import dataclass, field
from typing import Any

from vibecomfy.contracts.intent_nodes import (
    INTENT_NODE_CONTRACT_INVALID_CODE,
    INTENT_NODE_EDITOR_ONLY_CODE,
    is_intent_class_type,
    validate_intent_node_contract,
)


OPAQUE_COMPONENT_CLASS_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class ContractIssue:
    """A single issue produced by a semantic contract validation."""

    code: str
    message: str
    severity: str = "error"  # "error" | "warning"
    detail: dict[str, Any] = field(default_factory=dict)


def comfyui_node_issue_specs(
    nodes: Iterable[tuple[Any, str, dict[str, Any]] | tuple[Any, str, dict[str, Any], dict[str, Any]]],
) -> list[ContractIssue]:
    """Neutral ComfyUI-specific node validation specs.

    ``nodes`` is an iterable of ``(node_id, class_type, inputs)`` tuples. Returns
    neutral ``ContractIssue`` objects; callers convert them to their own issue
    type. This keeps ComfyUI validation policy in the contracts layer without a
    reverse dependency on the IR workflow module.
    """
    specs: list[ContractIssue] = []
    for raw_node in nodes:
        if len(raw_node) == 3:
            node_id, class_type, inputs = raw_node
            metadata: dict[str, Any] = {}
        elif len(raw_node) == 4:
            node_id, class_type, inputs, metadata = raw_node
        else:
            raise ValueError(
                "comfyui_node_issue_specs expects (node_id, class_type, inputs) "
                "or (node_id, class_type, inputs, metadata) tuples"
            )
        if is_intent_class_type(class_type):
            intent_result = validate_intent_node_contract(
                node_id=str(node_id),
                class_type=class_type,
                metadata=metadata,
            )
            detail = {
                "node_id": str(node_id),
                "class_type": class_type,
                "kind": intent_result.kind,
                "vibecomfy_uid": intent_result.vibecomfy_uid,
            }
            if intent_result.ok:
                specs.append(
                    ContractIssue(
                        code=INTENT_NODE_EDITOR_ONLY_CODE,
                        message=(
                            f"Node {node_id} ({class_type}) is an editor-only intent node; "
                            "it may stay on the canvas but must be lowered before queueing."
                        ),
                        severity="warning",
                        detail=detail,
                    )
                )
            else:
                for problem in intent_result.problems:
                    specs.append(
                        ContractIssue(
                            code=INTENT_NODE_CONTRACT_INVALID_CODE,
                            message=problem.message,
                            detail={**detail, "intent_issue_code": problem.code, **problem.detail},
                        )
                    )
        if OPAQUE_COMPONENT_CLASS_RE.match(class_type):
            specs.append(
                ContractIssue(
                    code="opaque_component_class_type",
                    message=(
                        f"Node {node_id} has opaque component class_type "
                        f"{class_type!r}; inline or replace the subgraph before runtime."
                    ),
                    severity="warning",
                    detail={"node_id": str(node_id), "class_type": class_type},
                )
            )
        if class_type == "VAELoaderKJ":
            vae_name = inputs.get("vae_name") or inputs.get("widget_0")
            if isinstance(vae_name, str):
                normalized_vae_name = vae_name.lower().replace("\\", "/")
                if "ltx" in normalized_vae_name and "audio" in normalized_vae_name:
                    specs.append(
                        ContractIssue(
                            code="ltx_audio_vae_wrong_loader",
                            message=(
                                f"Node {node_id} loads LTX audio VAE {vae_name!r} with VAELoaderKJ; "
                                "use LTXVAudioVAELoader and stage the file under checkpoints."
                            ),
                            detail={
                                "node_id": str(node_id),
                                "class_type": class_type,
                                "vae_name": vae_name,
                            },
                        )
                    )
    return specs


@dataclass
class ContractReport:
    """Report from a semantic contract validation."""

    contract_name: str
    passed: bool
    issues: list[ContractIssue] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def add(self, code: str, message: str, *, severity: str = "error", **detail: Any) -> None:
        self.issues.append(ContractIssue(code=code, message=message, severity=severity, detail=dict(detail)))
        if severity == "error":
            self.passed = False

    def summary(self) -> str:
        errors = [i for i in self.issues if i.severity == "error"]
        warnings = [i for i in self.issues if i.severity == "warning"]
        lines = [
            f"Contract: {self.contract_name}",
            f"  passed: {self.passed}",
            f"  errors: {len(errors)}",
            f"  warnings: {len(warnings)}",
        ]
        for i in self.issues:
            lines.append(f"  [{i.severity.upper()}] {i.code}: {i.message}")
        return "\n".join(lines)

    def errors(self) -> list[ContractIssue]:
        return [i for i in self.issues if i.severity == "error"]

    def warnings(self) -> list[ContractIssue]:
        return [i for i in self.issues if i.severity == "warning"]
