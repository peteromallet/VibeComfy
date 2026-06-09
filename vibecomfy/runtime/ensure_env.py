from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from vibecomfy.node_packs import CustomNodePack, get_known_node_packs
from vibecomfy.node_packs_install import InstallBatchResult, install_required_packs
from vibecomfy.porting.object_info.consume import reset_cache
from vibecomfy.porting.object_info.serialize import CacheIdentity, build_cache
from vibecomfy.porting.provenance import ProvenanceReport, ProvenanceRecord, extract_provenance
from vibecomfy.schema import RuntimeSchemaProvider

CORE_CNR_ID = "comfy-core"


@dataclass(frozen=True, slots=True)
class EnsureFailure:
    code: str
    message: str
    slug: str | None = None
    pack_name: str | None = None
    node_id: str | None = None
    class_type: str | None = None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EnsurePackOutcome:
    slug: str
    pack_name: str | None = None
    install_status: str | None = None
    git_commit_sha: str | None = None
    error: str | None = None
    introspected: bool = False
    cache_written: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None and (
            self.install_status is None or self.install_status in {"installed", "refreshed"}
        )

    def to_json(self) -> dict[str, Any]:
        return asdict(self) | {"ok": self.ok}


@dataclass(frozen=True, slots=True)
class EnsureEnvResult:
    ok: bool
    provenance: ProvenanceReport
    noop: bool = False
    pack_outcomes: tuple[EnsurePackOutcome, ...] = ()
    failures: tuple[EnsureFailure, ...] = ()
    aux_only: tuple[ProvenanceRecord, ...] = ()
    unprovenanced: tuple[ProvenanceRecord, ...] = ()
    install_batch: InstallBatchResult | None = None
    introspection_result: Any = None
    cache_write_result: Any = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "noop": self.noop,
            "provenance": self.provenance.to_json(),
            "pack_outcomes": [outcome.to_json() for outcome in self.pack_outcomes],
            "failures": [failure.to_json() for failure in self.failures],
            "aux_only": [record.to_json() for record in self.aux_only],
            "unprovenanced": [record.to_json() for record in self.unprovenanced],
            "install_batch": _install_batch_to_json(self.install_batch),
            "introspection_result": self.introspection_result,
            "cache_write_result": self.cache_write_result,
            "diagnostics": self.diagnostics,
        }


Installer = Callable[[Sequence[CustomNodePack]], InstallBatchResult]
Introspector = Callable[[Sequence[CustomNodePack]], Any]
CacheWriter = Callable[[Any], Any]

_REALIZED_SIGNATURES: set[tuple[object, ...]] = set()


def ensure_env(
    workflow: Mapping[str, Any] | str | Path,
    *,
    installer: Installer = install_required_packs,
    introspector: Introspector | None = None,
    cache_writer: CacheWriter | None = None,
    known_packs: Sequence[CustomNodePack] | None = None,
    server_url: str | None = None,
) -> EnsureEnvResult:
    """Realize custom-node environment requirements from workflow provenance.

    This entry point is intentionally offline and deterministic until injected
    seams are called. `cnr_id` is the required pack slug; `ver` remains
    provenance metadata and does not affect resolution in Sprint B.
    """

    raw = _load_raw_workflow(workflow)
    provenance = extract_provenance(raw)
    failures: list[EnsureFailure] = []
    outcomes_by_slug: dict[str, EnsurePackOutcome] = {}
    class_types_by_slug = _required_class_types_by_slug(provenance)

    for record in provenance.core_slug_non_core:
        failures.append(
            EnsureFailure(
                code="suspicious_comfy_core",
                message=f"{record.class_type} is tagged with cnr_id={CORE_CNR_ID!r} but is not a known core class",
                slug=CORE_CNR_ID,
                node_id=record.node_id,
                class_type=record.class_type,
            )
        )

    pack_by_slug = _known_pack_by_slug(known_packs)
    required_slugs = sorted(slug for slug in provenance.required_pack_slugs if slug != CORE_CNR_ID)
    packs: list[CustomNodePack] = []
    for slug in required_slugs:
        pack = pack_by_slug.get(slug)
        if pack is None:
            failures.append(
                EnsureFailure(
                    code="unresolved_pack",
                    message=f"no known custom-node pack metadata for cnr_id={slug!r}",
                    slug=slug,
                )
            )
            outcomes_by_slug[slug] = EnsurePackOutcome(
                slug=slug,
                error="unresolved pack metadata",
            )
            continue
        packs.append(pack)
        outcomes_by_slug[slug] = EnsurePackOutcome(slug=slug, pack_name=pack.name)

    core_classes = class_types_by_slug.get(CORE_CNR_ID, frozenset())
    core_outcome: EnsurePackOutcome | None = None
    if core_classes and not provenance.core_slug_non_core:
        core_outcome = EnsurePackOutcome(slug=CORE_CNR_ID, pack_name=CORE_CNR_ID)

    realization_signature = _realization_signature(
        class_types_by_slug,
        installer=installer,
        introspector=introspector,
        cache_writer=cache_writer,
        server_url=server_url,
    )
    if not failures and realization_signature in _REALIZED_SIGNATURES:
        if core_outcome is not None:
            outcomes_by_slug[CORE_CNR_ID] = core_outcome
        pack_outcomes = tuple(outcomes_by_slug[slug] for slug in sorted(outcomes_by_slug))
        return EnsureEnvResult(
            ok=True,
            noop=True,
            provenance=provenance,
            pack_outcomes=pack_outcomes,
            aux_only=tuple(provenance.aux_only),
            unprovenanced=tuple(provenance.unprovenanced),
            diagnostics={
                "aux_only_count": len(provenance.aux_only),
                "unprovenanced_count": len(provenance.unprovenanced),
                "core_slug_non_core_count": len(provenance.core_slug_non_core),
            },
        )

    install_batch: InstallBatchResult | None = None
    if packs:
        try:
            install_batch = installer(tuple(packs))
        except Exception as exc:  # pragma: no cover - defensive seam wrapper
            install_batch = None
            failures.append(
                EnsureFailure(
                    code="installer_exception",
                    message=str(exc) or exc.__class__.__name__,
                )
            )
            for pack in packs:
                outcomes_by_slug[pack.name] = EnsurePackOutcome(
                    slug=pack.name,
                    pack_name=pack.name,
                    error=str(exc) or exc.__class__.__name__,
                )
        else:
            for result in install_batch.results:
                error = result.error if result.status not in {"installed", "refreshed"} else None
                outcomes_by_slug[result.name] = EnsurePackOutcome(
                    slug=result.name,
                    pack_name=result.name,
                    install_status=result.status,
                    git_commit_sha=result.git_commit_sha,
                    error=error,
                )
                if error is not None:
                    failures.append(
                        EnsureFailure(
                            code="install_failed",
                            message=error,
                            slug=result.name,
                            pack_name=result.name,
                        )
                    )
            if install_batch.preflight.error and not install_batch.preflight.ok:
                failures.append(
                    EnsureFailure(
                        code="install_preflight_failed",
                        message=install_batch.preflight.error,
                    )
                )

    introspection_result: Any = None
    cache_write_result: Any = None
    if not failures and (packs or core_classes):
        try:
            if introspector is None:
                introspection_result = _runtime_object_info(server_url=server_url)
            else:
                introspection_result = introspector(tuple(packs))

            filtered_payloads, filter_failures = _filter_object_info_by_identity(
                introspection_result,
                class_types_by_slug=class_types_by_slug,
                custom_slugs={pack.name for pack in packs},
                include_core=bool(core_classes),
            )
            failures.extend(filter_failures)
            if filter_failures:
                raise _HandledEnsureFailure()

            outcomes_by_slug = {
                slug: _replace_outcome(outcome, introspected=True)
                for slug, outcome in outcomes_by_slug.items()
            }
            if core_outcome is not None:
                core_outcome = _replace_outcome(core_outcome, introspected=True)

            if cache_writer is not None:
                cache_write_result = cache_writer(filtered_payloads)
            else:
                cache_write_result = _write_object_info_cache(
                    filtered_payloads,
                    outcomes_by_slug=outcomes_by_slug,
                    include_core=bool(core_classes),
                )
            outcomes_by_slug = {
                slug: _replace_outcome(outcome, cache_written=True)
                for slug, outcome in outcomes_by_slug.items()
            }
            if core_outcome is not None:
                core_outcome = _replace_outcome(core_outcome, cache_written=True)

            reset_cache()
        except _HandledEnsureFailure:
            pass
        except Exception as exc:  # pragma: no cover - defensive seam wrapper
            failures.append(
                EnsureFailure(
                    code="introspection_or_cache_failed",
                    message=str(exc) or exc.__class__.__name__,
                )
            )

    if core_outcome is not None:
        outcomes_by_slug[CORE_CNR_ID] = core_outcome
    pack_outcomes = tuple(outcomes_by_slug[slug] for slug in sorted(outcomes_by_slug))
    all_pack_outcomes_ok = all(outcome.ok for outcome in pack_outcomes)
    ok = not failures and all_pack_outcomes_ok
    if ok:
        _REALIZED_SIGNATURES.add(realization_signature)
    return EnsureEnvResult(
        ok=ok,
        noop=False,
        provenance=provenance,
        pack_outcomes=pack_outcomes,
        failures=tuple(failures),
        aux_only=tuple(provenance.aux_only),
        unprovenanced=tuple(provenance.unprovenanced),
        install_batch=install_batch,
        introspection_result=introspection_result,
        cache_write_result=cache_write_result,
        diagnostics={
            "aux_only_count": len(provenance.aux_only),
            "unprovenanced_count": len(provenance.unprovenanced),
            "core_slug_non_core_count": len(provenance.core_slug_non_core),
        },
    )


def _load_raw_workflow(workflow: Mapping[str, Any] | str | Path) -> Mapping[str, Any]:
    if isinstance(workflow, Mapping):
        return workflow
    return json.loads(Path(workflow).read_text(encoding="utf-8"))


def _known_pack_by_slug(known_packs: Sequence[CustomNodePack] | None) -> dict[str, CustomNodePack]:
    packs = tuple(known_packs) if known_packs is not None else get_known_node_packs()
    by_slug: dict[str, CustomNodePack] = {}
    for pack in packs:
        by_slug.setdefault(pack.name, pack)
    return by_slug


def _required_class_types_by_slug(provenance: ProvenanceReport) -> dict[str, frozenset[str]]:
    by_slug: dict[str, set[str]] = {}
    for record in provenance.records:
        if not record.cnr_id or not record.execution_looking:
            continue
        by_slug.setdefault(record.cnr_id, set()).add(record.class_type)
    return {slug: frozenset(class_types) for slug, class_types in by_slug.items()}


def _realization_signature(
    class_types_by_slug: Mapping[str, frozenset[str]],
    *,
    installer: Installer,
    introspector: Introspector | None,
    cache_writer: CacheWriter | None,
    server_url: str | None,
) -> tuple[object, ...]:
    return (
        tuple(
            (slug, tuple(sorted(class_types)))
            for slug, class_types in sorted(class_types_by_slug.items())
        ),
        id(installer),
        id(introspector),
        id(cache_writer),
        server_url,
    )


def _runtime_object_info(*, server_url: str | None) -> dict[str, Any]:
    provider = RuntimeSchemaProvider(server_url=server_url)
    return provider.object_info()


class _HandledEnsureFailure(Exception):
    pass


def _filter_object_info_by_identity(
    object_info: Any,
    *,
    class_types_by_slug: Mapping[str, frozenset[str]],
    custom_slugs: set[str],
    include_core: bool,
) -> tuple[dict[str, dict[str, dict[str, Any]]], list[EnsureFailure]]:
    if not isinstance(object_info, Mapping):
        return {}, [
            EnsureFailure(
                code="introspection_invalid",
                message="runtime object_info payload must be a mapping",
            )
        ]

    wanted_slugs = set(custom_slugs)
    if include_core:
        wanted_slugs.add(CORE_CNR_ID)

    filtered: dict[str, dict[str, dict[str, Any]]] = {}
    failures: list[EnsureFailure] = []
    for slug in sorted(wanted_slugs):
        entries: dict[str, dict[str, Any]] = {}
        for class_type in sorted(class_types_by_slug.get(slug, ())):
            info = object_info.get(class_type)
            if not isinstance(info, dict):
                failures.append(
                    EnsureFailure(
                        code="introspection_missing_class",
                        message=f"runtime object_info did not include required class {class_type!r}",
                        slug=slug,
                        class_type=class_type,
                    )
                )
                continue
            entries[class_type] = dict(info)
        if entries:
            filtered[slug] = entries
    return filtered, failures


def _write_object_info_cache(
    payloads_by_slug: Mapping[str, Mapping[str, dict[str, Any]]],
    *,
    outcomes_by_slug: Mapping[str, EnsurePackOutcome],
    include_core: bool,
) -> dict[str, Any]:
    written: dict[str, dict[str, int]] = {}
    for slug, payload in sorted(payloads_by_slug.items()):
        if slug == CORE_CNR_ID:
            if not include_core:
                continue
            identity = CacheIdentity(
                pack_slug=CORE_CNR_ID,
                pack_version="runtime-core",
                evidence_identity="ensure-env:comfy-core",
                source_kind="runtime_core_object_info",
            )
            version = "runtime-core"
        else:
            outcome = outcomes_by_slug.get(slug)
            git_commit = outcome.git_commit_sha if outcome is not None else None
            if not git_commit:
                raise RuntimeError(f"cannot write object_info cache for {slug!r} without git commit identity")
            identity = CacheIdentity(
                pack_slug=slug,
                pack_version=git_commit,
                git_commit=git_commit,
                source_kind="runtime_object_info",
            )
            version = git_commit

        classes, packs = _build_cache_from_payload(slug, payload, identity=identity, version=version)
        written[slug] = {"classes": classes, "packs": packs}
    return {"written": written}


def _build_cache_from_payload(
    slug: str,
    payload: Mapping[str, dict[str, Any]],
    *,
    identity: CacheIdentity,
    version: str,
) -> tuple[int, int]:
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        prefix=f"vibecomfy-ensure-{_safe_cache_name(slug)}-",
        suffix=".object_info.json",
        delete=False,
    ) as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        source_path = Path(fh.name)
    try:
        return build_cache(
            source_path,
            version=version,
            identity=identity,
            full_pack_refresh={identity.pack_slug or slug},
        )
    finally:
        source_path.unlink(missing_ok=True)


def _safe_cache_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)


def _replace_outcome(
    outcome: EnsurePackOutcome,
    *,
    introspected: bool | None = None,
    cache_written: bool | None = None,
) -> EnsurePackOutcome:
    return EnsurePackOutcome(
        slug=outcome.slug,
        pack_name=outcome.pack_name,
        install_status=outcome.install_status,
        git_commit_sha=outcome.git_commit_sha,
        error=outcome.error,
        introspected=outcome.introspected if introspected is None else introspected,
        cache_written=outcome.cache_written if cache_written is None else cache_written,
    )


def _install_batch_to_json(batch: InstallBatchResult | None) -> dict[str, Any] | None:
    if batch is None:
        return None
    return {
        "ok": batch.ok,
        "results": [asdict(result) for result in batch.results],
        "preflight": asdict(batch.preflight),
        "preflight_unsupported": batch.preflight_unsupported,
    }


__all__ = [
    "EnsureEnvResult",
    "EnsureFailure",
    "EnsurePackOutcome",
    "ensure_env",
]
