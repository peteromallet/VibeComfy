"""Hand-maintained codemod rules registry.

Lists the implicit rules that ``vibecomfy/porting/emitter.py`` applies
during Python emission.  This is a hand-maintained reference, marked
for partial coverage where appropriate.

Grouped by category: NAMING, EMISSION, METADATA, VALIDATION, PROVENANCE.

Each rule has:
* ``id`` — unique rule identifier (R-CATEGORY-NN).
* ``category`` — one of NAMING, EMISSION, METADATA, VALIDATION, PROVENANCE.
* ``description`` — short human-readable description.
* ``behavior`` — summary of what the emitter does.
* ``partial_coverage`` — True if this registry entry may be incomplete.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EmitterRule:
    """One codemod rule in the registry."""

    id: str
    category: str
    description: str
    behavior: str
    partial_coverage: bool = False
    note: str = ""


RULES: list[EmitterRule] = [
    # ------------------------------------------------------------------
    # NAMING
    # ------------------------------------------------------------------
    EmitterRule(
        id="R-NAME-01",
        category="NAMING",
        description="Variable names from class_type.lower(), integer suffix for duplicates",
        behavior=(
            "Each node variable is named by lowercasing its class_type "
            "(e.g. CLIPTextEncode → cliptextencode). When the same "
            "class_type appears multiple times, an integer suffix is "
            "appended (cliptextencode_2, cliptextencode_3, etc.)."
        ),
    ),
    EmitterRule(
        id="R-NAME-02",
        category="NAMING",
        description="UUID class types get 'n_<uuid_underscored>' fallback",
        behavior=(
            "When a node's class_type is a UUID (ComfyUI subgraph component), "
            "the variable name falls back to n_<uuid> with hyphens replaced "
            "by underscores (e.g. n_abc12345_6789_...)."
        ),
    ),
    EmitterRule(
        id="R-NAME-03",
        category="NAMING",
        description="Special-case CLIPTextEncode feeding KSampler.positive/negative",
        behavior=(
            "CLIPTextEncode nodes wired into KSampler.positive or .negative "
            "may receive special naming treatment to distinguish prompt vs "
            "negative_prompt roles."
        ),
        partial_coverage=True,
        note="Role-based naming for positive/negative is applied when edges are detectable.",
    ),

    # ------------------------------------------------------------------
    # EMISSION
    # ------------------------------------------------------------------
    EmitterRule(
        id="R-EMIT-01",
        category="EMISSION",
        description="Schema defaults stripped from kwargs",
        behavior=(
            "When a node input value matches the schema default (e.g. "
            "weight_dtype='default'), the kwarg is omitted from the emitted "
            "Python call to reduce noise."
        ),
    ),
    EmitterRule(
        id="R-EMIT-02",
        category="EMISSION",
        description="Single-output nodes pass bare handle; multi-output requires .out('NAME')",
        behavior=(
            "Nodes with exactly one output slot emit a bare variable name "
            "for wiring. Nodes with multiple outputs require .out('NAME') "
            "or .out(N) to disambiguate which output is being referenced."
        ),
    ),
    EmitterRule(
        id="R-EMIT-03",
        category="EMISSION",
        description="_outputs=(...) emitted whenever node has multiple outputs",
        behavior=(
            "When a node has more than one output slot, the emitter appends "
            "an _outputs=(...) tuple at the call site to document the "
            "multi-output contract explicitly."
        ),
    ),

    # ------------------------------------------------------------------
    # METADATA
    # ------------------------------------------------------------------
    EmitterRule(
        id="R-META-01",
        category="METADATA",
        description="READY_METADATA omits derivable template_id, source_workflow, coverage_tier",
        behavior=(
            "Certain metadata fields (template_id, source_workflow, "
            "coverage_tier) that can be derived from the conversion "
            "provenance are omitted from READY_METADATA to reduce redundancy."
        ),
    ),
    EmitterRule(
        id="R-META-02",
        category="METADATA",
        description="ModelAsset.filename omitted when URL-basename equal",
        behavior=(
            "For model assets where the URL basename matches the asset name, "
            "the filename field is omitted from READY_METADATA to reduce noise."
        ),
        partial_coverage=True,
    ),
    EmitterRule(
        id="R-META-03",
        category="METADATA",
        description="READY_REQUIREMENTS emitted with models and custom_nodes lists",
        behavior=(
            "The READY_REQUIREMENTS dict is emitted with 'models' and "
            "'custom_nodes' keys populated from workflow.requirements "
            "and metadata.model_assets."
        ),
    ),
    EmitterRule(
        id="R-META-04",
        category="METADATA",
        description="ready_template field set in READY_METADATA",
        behavior=(
            "READY_METADATA always includes a 'ready_template' key set "
            "to the kind/name ID of the ready template."
        ),
    ),

    # ------------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------------
    EmitterRule(
        id="R-VAL-01",
        category="VALIDATION",
        description="Emitted template validated for import/build/compile",
        behavior=(
            "After emission, the generated Python text is dynamically "
            "imported, built, and compiled to verify correctness before "
            "writing to disk."
        ),
    ),
    EmitterRule(
        id="R-VAL-02",
        category="VALIDATION",
        description="Canonical parity checked between source and emitted workflows",
        behavior=(
            "The source and emitted workflows are both compiled to API "
            "dicts and compared for structural equivalence (class-type "
            "counts, topology, widget values)."
        ),
    ),
    EmitterRule(
        id="R-VAL-03",
        category="VALIDATION",
        description="Model-like value preservation gated during conversion",
        behavior=(
            "Model filenames (.safetensors, .ckpt, etc.) are compared "
            "between source and emitted APIs. Changes or drops are "
            "treated as hard conversion failures."
        ),
    ),
    EmitterRule(
        id="R-VAL-04",
        category="VALIDATION",
        description="Strict-ready validation for ready-template candidates",
        behavior=(
            "Ready-template candidates are validated against strict-ready "
            "rules: all widget aliases resolved, no opaque UUID class types "
            "in materialized templates, public output contracts present."
        ),
    ),

    # ------------------------------------------------------------------
    # PROVENANCE
    # ------------------------------------------------------------------
    EmitterRule(
        id="R-PROV-01",
        category="PROVENANCE",
        description="Source provenance recorded in WorkflowSource.provenance",
        behavior=(
            "The WorkflowSource.provenance dict records source_path, "
            "source_id, source_type, source_hash, and output_mode for "
            "traceability."
        ),
    ),
    EmitterRule(
        id="R-PROV-02",
        category="PROVENANCE",
        description="Conversion provenance includes schema source metadata",
        behavior=(
            "The conversion result records which schema provider was used "
            "(local index, object_info cache, runtime) for reproducibility."
        ),
    ),
    EmitterRule(
        id="R-PROV-03",
        category="PROVENANCE",
        description="Generated header comment marks template as regeneratable",
        behavior=(
            "Each generated ready template begins with '# vibecomfy: generated' "
            "followed by a provenance summary so automated tools can identify "
            "regeneratable templates."
        ),
    ),
    EmitterRule(
        id="R-PROV-04",
        category="PROVENANCE",
        description="Protected markers prevent automatic overwrite",
        behavior=(
            "Templates beginning with '# vibecomfy: manual' or "
            "'# vibecomfy: broken-regen' are refused by "
            "port_convert_and_write() to protect hand-edited templates and "
            "known broken-regeneration shims."
        ),
    ),

    # ------------------------------------------------------------------
    # ADDITIONAL rules (partial coverage noted)
    # ------------------------------------------------------------------
    EmitterRule(
        id="R-EMIT-04",
        category="EMISSION",
        description="Scratchpad emission uses emit_scratchpad_python() path",
        behavior=(
            "When ready_id is None, the scratchpad emitter generates a "
            "standalone Python script with a build() function rather than "
            "a full ready-template module."
        ),
        partial_coverage=True,
    ),
    EmitterRule(
        id="R-EMIT-05",
        category="EMISSION",
        description="Ready template emission adds bind_input/bind_output calls",
        behavior=(
            "Ready-template emission appends bind_input() and bind_output() "
            "calls after finalize_metadata() to register PUBLIC_INPUTS and "
            "PUBLIC_OUTPUTS contracts."
        ),
        partial_coverage=True,
    ),
    EmitterRule(
        id="R-EMIT-06",
        category="EMISSION",
        description="Widget aliases applied to node inputs during emission",
        behavior=(
            "Positional widget_N inputs that have known schema aliases are "
            "converted to named kwargs in the emitted output."
        ),
        partial_coverage=True,
    ),
    EmitterRule(
        id="R-EMIT-07",
        category="EMISSION",
        description="_node() helper emitted for ID-preserving template mode",
        behavior=(
            "When node IDs must be preserved (ready-template mode with "
            "original IDs), a local _node() helper function is emitted "
            "that creates nodes and re-assigns their IDs."
        ),
        partial_coverage=True,
    ),
    EmitterRule(
        id="R-EMIT-08",
        category="EMISSION",
        description="_set_id_map(...) emitted for UUID-subgraph nodes",
        behavior=(
            "When a workflow contains UUID class-type nodes (subgraph "
            "components), a _set_id_map(...) call is emitted to "
            "register the UUID-to-class-type mapping. v2.6.2 may "
            "derive this at runtime instead."
        ),
        partial_coverage=True,
    ),
    EmitterRule(
        id="R-EMIT-09",
        category="EMISSION",
        description="custom_node_packs provenance injected for custom node classes",
        behavior=(
            "When a node class comes from a custom-node pack, the emitter "
            "adds provenance metadata linking the template to the pack name "
            "and git commit SHA."
        ),
        partial_coverage=True,
    ),
]


def rules_by_category() -> dict[str, list[EmitterRule]]:
    """Return rules grouped by category, with deterministic ordering."""
    grouped: dict[str, list[EmitterRule]] = {}
    for rule in RULES:
        grouped.setdefault(rule.category, []).append(rule)
    return grouped


def to_json() -> dict[str, Any]:
    """Export all rules as a deterministic JSON-serializable dict."""
    return {
        "partial_coverage": True,
        "note": (
            "Hand-maintained registry. Read vibecomfy/porting/emitter.py "
            "for the canonical implementation."
        ),
        "rules_by_category": {
            cat: [
                {
                    "id": rule.id,
                    "description": rule.description,
                    "behavior": rule.behavior,
                    "partial_coverage": rule.partial_coverage,
                    "note": rule.note or None,
                }
                for rule in rules
            ]
            for cat, rules in sorted(rules_by_category().items())
        },
        "total_rules": len(RULES),
    }


__all__ = [
    "EmitterRule",
    "RULES",
    "rules_by_category",
    "to_json",
]
