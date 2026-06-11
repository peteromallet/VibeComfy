from __future__ import annotations

"""Contract doctor diagnostics for VibeWorkflow runtime readiness.

.. note::

   The SageAttention and LTX headless-preview compatibility rules
   (PathchSageAttentionKJ, LTX2MemoryEfficientSageAttentionPatch,
   LTX2SamplingPreviewOverride) are intentionally duplicated from
   :mod:`vibecomfy.porting.workbench`.  This duplication is **accepted v1
   debt** per the plan assumptions.  Future runtime-contract fixes must
   update both locations or refactor into a shared helper module.
"""

from dataclasses import dataclass, field
from typing import Any

from vibecomfy.contracts.model import WorkflowRuntimeContract
from vibecomfy.workflow import VibeWorkflow


@dataclass(slots=True)
class ContractDoctorDiagnostic:
    """A single diagnostic produced by contract doctor."""

    code: str
    severity: str  # "error" | "warning" | "info"
    message: str
    node_id: str | None = None
    class_type: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""


@dataclass(slots=True)
class ContractDoctorReport:
    """Report from contract doctor: overall status + diagnostics + contract payload."""

    status: str  # "ok" | "error"
    diagnostics: list[ContractDoctorDiagnostic] = field(default_factory=list)
    contract: dict[str, Any] = field(default_factory=dict)


def _declares_sageattention(runtime_packages: list[dict[str, Any]]) -> bool:
    """Check if any runtime_packages entry declares sageattention."""
    return any(
        isinstance(package, dict) and package.get("name") == "sageattention"
        for package in runtime_packages
    )


def _sage_attention_disabled(value: Any) -> bool:
    """Case-insensitive check for disabled sage_attention value.

    ComfyUI widget schema consistently emits lowercase 'disabled', but we
    accept both casing variants as a defensive measure.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() == "disabled"
    return False


_HINT_KEY_NAMES = frozenset({"source", "install", "install_command", "verify", "probe"})


def _runtime_package_hint_diagnostics(
    runtime_packages: list[dict[str, Any]],
) -> list[ContractDoctorDiagnostic]:
    """Produce info diagnostics for runtime_packages entries missing hint keys.

    Each entry must have a 'name' key plus at least one of source/install/
    install_command/verify/probe. This is a structural-only check; no
    execution-time probes.
    """
    diagnostics: list[ContractDoctorDiagnostic] = []
    for idx, pkg in enumerate(runtime_packages):
        if not isinstance(pkg, dict):
            continue
        name = pkg.get("name")
        if not name:
            diagnostics.append(
                ContractDoctorDiagnostic(
                    code="runtime_package_missing_name",
                    severity="info",
                    message=(
                        f"Runtime package entry {idx} has no 'name' key; "
                        "install/source hints cannot be associated."
                    ),
                    detail={"package_index": idx, "package": pkg},
                    recommendation="Add a 'name' key to each runtime_packages entry.",
                )
            )
            continue
        hint_keys = set(pkg) & _HINT_KEY_NAMES
        if not hint_keys:
            diagnostics.append(
                ContractDoctorDiagnostic(
                    code="runtime_package_missing_install_hint",
                    severity="info",
                    message=(
                        f"Runtime package {name!r} has no install/source/probe hint keys; "
                        "automated environment provisioning cannot install it."
                    ),
                    detail={
                        "package_name": name,
                        "hint_keys_found": sorted(set(pkg) - {"name"}),
                        "expected_keys": sorted(_HINT_KEY_NAMES),
                    },
                    recommendation=(
                        f"Add at least one of {sorted(_HINT_KEY_NAMES)} to "
                        f"the {name!r} runtime_packages entry."
                    ),
                )
            )
    return diagnostics


def doctor_contract(
    workflow: VibeWorkflow,
    contract: WorkflowRuntimeContract,
) -> ContractDoctorReport:
    """Run diagnostics against a workflow and its runtime contract.

    Covers:
      (a) PathchSageAttentionKJ with sage_attention not None/disabled
          without runtime_packages sageattention entry → error
      (b) LTX2MemoryEfficientSageAttentionPatch without sageattention → error
      (c) LTX2SamplingPreviewOverride → headless-unsupported error
      (d) Declared runtime packages missing install/source/probe hint keys → info

    No package installation, no environment mutation, no --apply.

    .. note::

       The SageAttention and LTX headless-preview compatibility rules in this
       module (PathchSageAttentionKJ, LTX2MemoryEfficientSageAttentionPatch,
       LTX2SamplingPreviewOverride) are intentionally duplicated from
       :mod:`vibecomfy.porting.workbench`.  This duplication is **accepted v1
       debt** per the plan assumptions.  Future runtime-contract fixes must
       update both locations or refactor into a shared helper module.
    """
    diagnostics: list[ContractDoctorDiagnostic] = []

    # Look up sageattention declaration from the contract (derived from metadata)
    runtime_packages: list[dict[str, Any]] = contract.runtime_packages
    declares_sage = _declares_sageattention(runtime_packages)

    # Compile the API prompt for node-level inspection
    try:
        api = workflow.compile("api")
    except Exception:
        api = {}

    # Walk all nodes in the compiled API
    for node_id, node in sorted(api.items(), key=lambda item: item[0]):
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")

        # (b) LTX2MemoryEfficientSageAttentionPatch — always an error if
        #     sageattention is not declared, regardless of widget state.
        if class_type == "LTX2MemoryEfficientSageAttentionPatch":
            if not declares_sage:
                diagnostics.append(
                    ContractDoctorDiagnostic(
                        code="optional_acceleration_requires_unavailable_package",
                        severity="error",
                        message=(
                            f"Node {node_id} (LTX2MemoryEfficientSageAttentionPatch) "
                            "requires a sageattention-capable CUDA environment; the "
                            "standard RunPod image does not provide that contract."
                        ),
                        node_id=str(node_id),
                        class_type="LTX2MemoryEfficientSageAttentionPatch",
                        detail={
                            "category": "runtime_contract",
                            "missing_package": "sageattention",
                            "capability": "ltx2_memory_efficient_sage_attention",
                        },
                        recommendation=(
                            "Remove this patch for portable 4090 RunPod validation, "
                            "or declare and install a sageattention-capable environment explicitly."
                        ),
                    )
                )
            continue

        # (c) LTX2SamplingPreviewOverride — always a headless-incompatible error.
        if class_type == "LTX2SamplingPreviewOverride":
            diagnostics.append(
                ContractDoctorDiagnostic(
                    code="headless_preview_override_not_supported",
                    severity="error",
                    message=(
                        f"Node {node_id} (LTX2SamplingPreviewOverride) installs a "
                        "live preview callback that depends on ComfyUI frontend server "
                        "state; headless RunPod execution can crash when that state is absent."
                    ),
                    node_id=str(node_id),
                    class_type="LTX2SamplingPreviewOverride",
                    detail={
                        "category": "runtime_contract",
                        "capability": "ltx2_live_sampling_preview",
                    },
                    recommendation=(
                        "Remove this preview override for headless validation and route "
                        "the model directly to the downstream sampling/NAG nodes."
                    ),
                )
            )
            continue

        # (a) PathchSageAttentionKJ — only flag if sage_attention is active
        #     (not None/disabled) and sageattention is not declared.
        if class_type == "PathchSageAttentionKJ":
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            sage_attention = inputs.get("sage_attention", inputs.get("widget_0"))
            if _sage_attention_disabled(sage_attention):
                continue
            if declares_sage:
                continue
            diagnostics.append(
                ContractDoctorDiagnostic(
                    code="optional_acceleration_requires_unavailable_package",
                    severity="error",
                    message=(
                        f"Node {node_id} (PathchSageAttentionKJ) enables sageattention "
                        f"mode {sage_attention!r}; the standard RunPod image does not "
                        "install sageattention."
                    ),
                    node_id=str(node_id),
                    class_type="PathchSageAttentionKJ",
                    detail={
                        "category": "runtime_contract",
                        "input": "sage_attention",
                        "value": sage_attention,
                        "missing_package": "sageattention",
                    },
                    recommendation=(
                        "Set sage_attention to 'disabled' for portable 4090 RunPod validation."
                    ),
                )
            )

    # (d) Runtime package hint diagnostics
    diagnostics.extend(_runtime_package_hint_diagnostics(runtime_packages))

    # Determine overall status: error if any diagnostic has severity "error"
    has_errors = any(d.severity == "error" for d in diagnostics)
    status = "error" if has_errors else "ok"

    return ContractDoctorReport(
        status=status,
        diagnostics=diagnostics,
        contract=contract.to_dict(),
    )
