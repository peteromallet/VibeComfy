"""Compact evidence contracts for typed executor stage handoffs.

Ledger entries intentionally contain conclusions and evidence identifiers only.
Potentially large source bodies are retained in :class:`EvidenceArtifact` values
and are resolved by ``evidence_id`` when a consumer needs to inspect them.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


MAX_LEDGER_DECISION_CHARS = 1_000
MAX_LEDGER_CONCLUSION_CHARS = 4_000
MAX_LEDGER_UNCERTAINTY_CHARS = 2_000


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"`{field_name}` must be a non-empty string.")
    if value != value.strip():
        raise ValueError(f"`{field_name}` must not have leading or trailing whitespace.")
    return value


def _bounded_text(value: Any, field_name: str, max_chars: int, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"`{field_name}` must be a string.")
    normalized = value.strip()
    if not allow_empty and not normalized:
        raise ValueError(f"`{field_name}` must be a non-empty string.")
    if value != normalized:
        raise ValueError(f"`{field_name}` must not have leading or trailing whitespace.")
    if len(normalized) > max_chars:
        raise ValueError(
            f"`{field_name}` exceeds the compact ledger limit of {max_chars} characters; "
            "store full source bodies as evidence artifacts."
        )
    return normalized


def _text_tuple(value: Any, field_name: str, *, non_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"`{field_name}` must be a list of strings.")
    result = tuple(_required_text(item, f"{field_name}[]") for item in value)
    if non_empty and not result:
        raise ValueError(f"`{field_name}` must contain at least one item.")
    if len(set(result)) != len(result):
        raise ValueError(f"`{field_name}` must not contain duplicate values.")
    return result


def _freeze_json(value: Any, field_name: str = "value") -> Any:
    """Validate JSON safety and return an immutable, detached representation."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"`{field_name}` must not contain NaN or infinity.")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"`{field_name}` object keys must be strings.")
            frozen[key] = _freeze_json(item, f"{field_name}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item, f"{field_name}[]") for item in value)
    raise ValueError(
        f"`{field_name}` must be JSON-safe; got {type(value).__name__}."
    )


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    """Return the deterministic wire representation used by these contracts."""
    if hasattr(value, "to_dict") and callable(value.to_dict):
        value = value.to_dict()
    return json.dumps(
        _thaw_json(_freeze_json(value)),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _check_keys(
    payload: Mapping[str, Any],
    *,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
    contract: str,
) -> None:
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"{contract} is missing required field(s): {', '.join(missing)}.")
    extra = sorted(payload.keys() - required - optional)
    if extra:
        raise ValueError(f"{contract} contains unknown field(s): {', '.join(extra)}.")


@dataclass(frozen=True)
class EvidenceArtifact:
    """A full evidence body stored behind a stable identifier."""

    evidence_id: str
    kind: str
    body: Any
    source: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", _required_text(self.evidence_id, "evidence_id"))
        object.__setattr__(self, "kind", _required_text(self.kind, "kind"))
        if self.source is not None:
            object.__setattr__(self, "source", _required_text(self.source, "source"))
        object.__setattr__(self, "body", _freeze_json(self.body, "body"))
        if not isinstance(self.metadata, Mapping):
            raise ValueError("`metadata` must be an object.")
        object.__setattr__(self, "metadata", _freeze_json(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "evidence_id": self.evidence_id,
            "kind": self.kind,
            "body": _thaw_json(self.body),
            "metadata": _thaw_json(self.metadata),
        }
        if self.source is not None:
            result["source"] = self.source
        return result

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EvidenceArtifact":
        if not isinstance(payload, Mapping):
            raise ValueError("EvidenceArtifact must be an object.")
        _check_keys(
            payload,
            required=frozenset({"evidence_id", "kind", "body", "metadata"}),
            optional=frozenset({"source"}),
            contract="EvidenceArtifact",
        )
        return cls(
            evidence_id=payload["evidence_id"],
            kind=payload["kind"],
            body=payload["body"],
            source=payload.get("source"),
            metadata=payload.get("metadata", {}),
        )


@dataclass(frozen=True)
class EvidenceLedgerEntry:
    """Compact agent judgment: no source body fields are part of this shape.

    ``tool_status`` (T4.1) is the typed per-entry outcome of an EXECUTED
    evidence tool call (the :class:`~vibecomfy.executor.tool_contracts.ToolStatus`
    vocabulary, plus ``projection_failed``). It is ``None`` for non-tool
    entries (question/synthesis/policy markers) and for legacy serialized
    entries; the status-prefixed conclusion string remains the human-readable
    form and is not replaced.
    """

    decision: str
    conclusion: str
    evidence_ids: tuple[str, ...]
    uncertainty: str
    tool_status: str | None = None

    def __post_init__(self) -> None:
        if self.tool_status is not None:
            status = str(self.tool_status).strip().casefold()
            if not status:
                raise ValueError("`tool_status` must be a non-empty string or None.")
            object.__setattr__(self, "tool_status", status)
        object.__setattr__(
            self,
            "decision",
            _bounded_text(self.decision, "decision", MAX_LEDGER_DECISION_CHARS),
        )
        object.__setattr__(
            self,
            "conclusion",
            _bounded_text(self.conclusion, "conclusion", MAX_LEDGER_CONCLUSION_CHARS),
        )
        object.__setattr__(
            self,
            "evidence_ids",
            _text_tuple(self.evidence_ids, "evidence_ids"),
        )
        object.__setattr__(
            self,
            "uncertainty",
            _bounded_text(
                self.uncertainty,
                "uncertainty",
                MAX_LEDGER_UNCERTAINTY_CHARS,
                allow_empty=True,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "decision": self.decision,
            "conclusion": self.conclusion,
            "evidence_ids": list(self.evidence_ids),
            "uncertainty": self.uncertainty,
        }
        # Additive-with-omission (T4.1): entries without a typed tool status
        # keep the exact legacy serialized shape.
        if self.tool_status is not None:
            payload["tool_status"] = self.tool_status
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EvidenceLedgerEntry":
        if not isinstance(payload, Mapping):
            raise ValueError("EvidenceLedgerEntry must be an object.")
        _check_keys(
            payload,
            required=frozenset({"decision", "conclusion", "evidence_ids", "uncertainty"}),
            optional=frozenset({"tool_status"}),
            contract="EvidenceLedgerEntry",
        )
        return cls(
            decision=payload["decision"],
            conclusion=payload["conclusion"],
            evidence_ids=payload["evidence_ids"],
            uncertainty=payload["uncertainty"],
            tool_status=payload.get("tool_status"),
        )


@dataclass(frozen=True)
class EvidenceLedger:
    entries: tuple[EvidenceLedgerEntry, ...] = ()

    def __post_init__(self) -> None:
        normalized: list[EvidenceLedgerEntry] = []
        if not isinstance(self.entries, (list, tuple)):
            raise ValueError("`entries` must be a list of evidence ledger entries.")
        for entry in self.entries:
            normalized.append(
                entry
                if isinstance(entry, EvidenceLedgerEntry)
                else EvidenceLedgerEntry.from_dict(entry)
            )
        object.__setattr__(self, "entries", tuple(normalized))

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(
            evidence_id
            for entry in self.entries
            for evidence_id in entry.evidence_ids
        )

    def validate_references(self, available_evidence_ids: set[str] | frozenset[str]) -> None:
        unresolved = sorted(set(self.evidence_ids) - set(available_evidence_ids))
        if unresolved:
            raise ValueError(
                "EvidenceLedger contains unresolved evidence ID(s): " + ", ".join(unresolved) + "."
            )

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [entry.to_dict() for entry in self.entries]}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EvidenceLedger":
        if not isinstance(payload, Mapping):
            raise ValueError("EvidenceLedger must be an object.")
        _check_keys(
            payload,
            required=frozenset({"entries"}),
            contract="EvidenceLedger",
        )
        return cls(entries=payload["entries"])


def normalize_artifacts(value: Any) -> Mapping[str, EvidenceArtifact]:
    if not isinstance(value, Mapping):
        raise ValueError("`artifacts` must be an object keyed by evidence_id.")
    normalized: dict[str, EvidenceArtifact] = {}
    for raw_key, raw_artifact in value.items():
        evidence_id = _required_text(raw_key, "artifacts key")
        artifact = (
            raw_artifact
            if isinstance(raw_artifact, EvidenceArtifact)
            else EvidenceArtifact.from_dict(raw_artifact)
        )
        if artifact.evidence_id != evidence_id:
            raise ValueError(
                f"Artifact key {evidence_id!r} does not match its evidence_id "
                f"{artifact.evidence_id!r}."
            )
        normalized[evidence_id] = artifact
    return MappingProxyType(dict(sorted(normalized.items())))


@dataclass(frozen=True)
class EvidencePack:
    """Serializable artifact store plus its compact decision ledger."""

    artifacts: Mapping[str, EvidenceArtifact] = field(default_factory=dict)
    ledger: EvidenceLedger = field(default_factory=EvidenceLedger)

    def __post_init__(self) -> None:
        artifacts = normalize_artifacts(self.artifacts)
        ledger = (
            self.ledger
            if isinstance(self.ledger, EvidenceLedger)
            else EvidenceLedger.from_dict(self.ledger)
        )
        ledger.validate_references(set(artifacts))
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "ledger", ledger)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts": {
                evidence_id: artifact.to_dict()
                for evidence_id, artifact in self.artifacts.items()
            },
            "ledger": self.ledger.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EvidencePack":
        if not isinstance(payload, Mapping):
            raise ValueError("EvidencePack must be an object.")
        _check_keys(
            payload,
            required=frozenset({"artifacts", "ledger"}),
            contract="EvidencePack",
        )
        return cls(
            artifacts=payload["artifacts"],
            ledger=EvidenceLedger.from_dict(payload["ledger"]),
        )


__all__ = [
    "EvidenceArtifact",
    "EvidenceLedger",
    "EvidenceLedgerEntry",
    "EvidencePack",
    "MAX_LEDGER_CONCLUSION_CHARS",
    "MAX_LEDGER_DECISION_CHARS",
    "MAX_LEDGER_UNCERTAINTY_CHARS",
    "canonical_json",
]
