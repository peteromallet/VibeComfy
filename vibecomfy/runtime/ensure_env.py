from __future__ import annotations

import json
import re
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from vibecomfy.node_packs import CustomNodePack, get_known_node_packs
from vibecomfy.node_packs import find_installed_pack_ref
from vibecomfy.node_packs import DEFAULT_INSTALL_ROOT, InstallBatchResult, install_required_packs
from vibecomfy.porting.object_info.consume import reset_cache
from vibecomfy.porting.object_info.serialize import CacheIdentity, build_cache
from vibecomfy.porting.provenance import (
    ProvenanceReport,
    ProvenanceRecord,
    ProvenanceRequirement,
    ProvenanceWarning,
    extract_provenance,
)
from vibecomfy.registry.pack_resolver import PackNotFoundError, PackRef, PackResolution
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
class EnsureWarning:
    code: str
    message: str
    slug: str | None = None
    pack_name: str | None = None
    node_ids: tuple[str, ...] = ()
    class_types: tuple[str, ...] = ()
    cnr_id: str | None = None
    aux_id: str | None = None
    version: str | None = None
    low_confidence: bool = False

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
    warnings: tuple[EnsureWarning, ...] = ()
    low_confidence: bool = False
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
            "warnings": [warning.to_json() for warning in self.warnings],
            "low_confidence": self.low_confidence,
            "aux_only": [record.to_json() for record in self.aux_only],
            "unprovenanced": [record.to_json() for record in self.unprovenanced],
            "install_batch": _install_batch_to_json(self.install_batch),
            "introspection_result": self.introspection_result,
            "cache_write_result": self.cache_write_result,
            "diagnostics": self.diagnostics,
        }


Installer = Callable[..., InstallBatchResult]
Introspector = Callable[[Sequence[CustomNodePack]], Any]
CacheWriter = Callable[[Any], Any]


class PackResolver(Protocol):
    def __call__(
        self,
        class_name_or_slug: str,
        *,
        version_pin: str | None = None,
        aux_id: str | None = None,
        local_metadata: PackRef | dict[str, Any] | None = None,
        allow_remote_lookup: bool = True,
    ) -> PackResolution:
        ...

_REALIZED_SIGNATURES: set[tuple[object, ...]] = set()


def ensure_env(
    workflow: Mapping[str, Any] | str | Path,
    *,
    installer: Installer = install_required_packs,
    introspector: Introspector | None = None,
    cache_writer: CacheWriter | None = None,
    known_packs: Sequence[CustomNodePack] | None = None,
    server_url: str | None = None,
    install_roots: Sequence[Path] = (DEFAULT_INSTALL_ROOT,),
    resolver: PackResolver | None = None,
) -> EnsureEnvResult:
    """Realize custom-node environment requirements from workflow provenance.

    This entry point is intentionally offline and deterministic until injected
    seams are called. Provenance requirements are grouped by authored identity,
    so `cnr_id`, `aux_id`, and `ver` can influence install refs without coupling
    ensure-env to conversion.
    """

    raw = _load_raw_workflow(workflow)
    provenance = extract_provenance(raw)
    failures: list[EnsureFailure] = []
    warnings = _ensure_warnings_from_provenance(provenance)
    outcomes_by_slug: dict[str, EnsurePackOutcome] = {}
    requirement_plan = _plan_requirements(provenance)
    class_types_by_slug = requirement_plan.class_types_by_slug

    for conflict in provenance.conflicts:
        if conflict.code == "conflicting_authored_versions":
            failures.append(
                EnsureFailure(
                    code=conflict.code,
                    message=conflict.message,
                    slug=_slug_from_locator_key(conflict.locator_key),
                    node_id=conflict.node_ids[0] if conflict.node_ids else None,
                    class_type=conflict.class_types[0] if conflict.class_types else None,
                )
            )

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
    packs: list[CustomNodePack] = []
    resolved_refs_by_slug: dict[str, PackRef] = {}
    for slug, requirement in _ordered_requirements(requirement_plan.requirements_by_slug):
        if slug == CORE_CNR_ID:
            continue
        pack, ref, resolve_warnings, resolve_failures = _resolve_requirement_pack(
            slug,
            requirement,
            known_pack=pack_by_slug.get(slug),
            synthetic_pack=requirement_plan.synthetic_packs.get(slug),
            install_roots=install_roots,
            resolver=resolver,
        )
        warnings.extend(resolve_warnings)
        failures.extend(resolve_failures)
        if pack is None:
            failures.append(
                EnsureFailure(
                    code="unresolved_pack",
                    message=f"no known custom-node pack metadata for {requirement.locator_key}",
                    slug=slug,
                    node_id=requirement.node_ids[0] if requirement.node_ids else None,
                    class_type=requirement.class_types[0] if requirement.class_types else None,
                )
            )
            outcomes_by_slug[slug] = EnsurePackOutcome(
                slug=slug,
                error="unresolved pack metadata",
            )
            continue
        if ref is not None:
            resolved_refs_by_slug[slug] = ref
            requirement_plan.install_refs_by_slug[slug] = ref
        packs.append(pack)
        outcomes_by_slug[slug] = EnsurePackOutcome(slug=slug, pack_name=pack.name)

    fallback_packs, fallback_refs, fallback_warnings, fallback_failures = _resolve_unprovenanced_fallbacks(
        provenance,
        known_packs=pack_by_slug,
        install_roots=install_roots,
        resolver=resolver,
    )
    warnings.extend(fallback_warnings)
    failures.extend(fallback_failures)
    for slug, pack in sorted(fallback_packs.items()):
        if slug in outcomes_by_slug:
            continue
        packs.append(pack)
        class_types_by_slug.setdefault(slug, frozenset())
        class_types_by_slug[slug] = frozenset(
            set(class_types_by_slug.get(slug, frozenset()))
            | {record.class_type for record in provenance.unprovenanced if record.class_type in pack.classes}
        )
        outcomes_by_slug[slug] = EnsurePackOutcome(slug=slug, pack_name=pack.name)
    for slug, ref in fallback_refs.items():
        resolved_refs_by_slug[slug] = ref
        requirement_plan.install_refs_by_slug.setdefault(slug, ref)

    core_classes = class_types_by_slug.get(CORE_CNR_ID, frozenset())
    core_outcome: EnsurePackOutcome | None = None
    if core_classes and not provenance.core_slug_non_core:
        core_outcome = EnsurePackOutcome(slug=CORE_CNR_ID, pack_name=CORE_CNR_ID)

    realization_signature = _realization_signature(
        class_types_by_slug,
        requirements_by_slug=requirement_plan.requirements_by_slug,
        resolved_refs_by_slug=resolved_refs_by_slug,
        install_refs_by_slug=requirement_plan.install_refs_by_slug,
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
            warnings=tuple(warnings),
            low_confidence=provenance.low_confidence,
            aux_only=tuple(provenance.aux_only),
            unprovenanced=tuple(provenance.unprovenanced),
            diagnostics={
                "aux_only_count": len(provenance.aux_only),
                "unprovenanced_count": len(provenance.unprovenanced),
                "core_slug_non_core_count": len(provenance.core_slug_non_core),
            },
        )

    install_batch: InstallBatchResult | None = None
    if packs and not _has_blocking_preinstall_failures(failures):
        try:
            install_batch = _call_installer(
                installer,
                tuple(packs),
                install_refs_by_name=requirement_plan.install_refs_by_slug,
            )
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
                written_slugs = set(outcomes_by_slug)
                if core_outcome is not None:
                    written_slugs.add(CORE_CNR_ID)
            else:
                cache_write_result, cache_warnings = _write_object_info_cache(
                    filtered_payloads,
                    outcomes_by_slug=outcomes_by_slug,
                    refs_by_slug=resolved_refs_by_slug | requirement_plan.install_refs_by_slug,
                    low_confidence_slugs={
                        warning.slug for warning in warnings if warning.low_confidence and warning.slug
                    },
                    include_core=bool(core_classes),
                )
                warnings.extend(cache_warnings)
                written_slugs = (
                    set(cache_write_result.get("written", {}))
                    if isinstance(cache_write_result, Mapping)
                    else set()
                )
            outcomes_by_slug = {
                slug: _replace_outcome(outcome, cache_written=(slug in written_slugs))
                for slug, outcome in outcomes_by_slug.items()
            }
            if core_outcome is not None:
                core_outcome = _replace_outcome(
                    core_outcome,
                    cache_written=CORE_CNR_ID in written_slugs,
                )

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
        if len(_REALIZED_SIGNATURES) > 256:
            _REALIZED_SIGNATURES.clear()
    return EnsureEnvResult(
        ok=ok,
        noop=False,
        provenance=provenance,
        pack_outcomes=pack_outcomes,
        failures=tuple(failures),
        warnings=tuple(warnings),
        low_confidence=provenance.low_confidence or any(warning.low_confidence for warning in warnings),
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


@dataclass(frozen=True, slots=True)
class _RequirementPlan:
    requirements_by_slug: dict[str, ProvenanceRequirement]
    class_types_by_slug: dict[str, frozenset[str]]
    install_refs_by_slug: dict[str, PackRef]
    synthetic_packs: dict[str, CustomNodePack]


def _plan_requirements(provenance: ProvenanceReport) -> _RequirementPlan:
    requirements_by_slug: dict[str, ProvenanceRequirement] = {}
    class_types_by_slug: dict[str, set[str]] = {}
    install_refs_by_slug: dict[str, PackRef] = {}
    synthetic_packs: dict[str, CustomNodePack] = {}
    for requirement in provenance.requirements:
        slug = _install_slug(requirement)
        if slug is None:
            continue
        requirements_by_slug.setdefault(slug, requirement)
        class_types_by_slug.setdefault(slug, set()).update(requirement.class_types)
        if slug != CORE_CNR_ID:
            ref = _pack_ref_from_requirement(slug, requirement)
            if ref is not None:
                install_refs_by_slug[slug] = ref
            if requirement.resolver_kind == "aux_git" and requirement.aux_id:
                synthetic_packs.setdefault(
                    slug,
                    CustomNodePack(
                        name=slug,
                        repo=_git_url_from_aux_id(requirement.aux_id),
                        classes=frozenset(requirement.class_types),
                    ),
                )
    return _RequirementPlan(
        requirements_by_slug=requirements_by_slug,
        class_types_by_slug={slug: frozenset(class_types) for slug, class_types in class_types_by_slug.items()},
        install_refs_by_slug=install_refs_by_slug,
        synthetic_packs=synthetic_packs,
    )


def _resolve_requirement_pack(
    slug: str,
    requirement: ProvenanceRequirement,
    *,
    known_pack: CustomNodePack | None,
    synthetic_pack: CustomNodePack | None,
    install_roots: Sequence[Path],
    resolver: PackResolver | None,
) -> tuple[CustomNodePack | None, PackRef | None, list[EnsureWarning], list[EnsureFailure]]:
    warnings: list[EnsureWarning] = []
    failures: list[EnsureFailure] = []
    version = requirement.version_pin.version if requirement.version_pin is not None else None

    local = find_installed_pack_ref(
        slug,
        install_roots=install_roots,
        aux_id=requirement.aux_id,
        version_pin=version,
    )
    if local is not None:
        return (
            known_pack or synthetic_pack or _pack_from_ref(local.pack_ref, class_types=requirement.class_types),
            local.pack_ref,
            warnings,
            failures,
        )

    if requirement.aux_id:
        ref = _resolve_with_resolver(
            resolver,
            slug,
            version_pin=version,
            aux_id=requirement.aux_id,
            allow_remote_lookup=False,
        )
        if ref is None:
            ref = _pack_ref_from_requirement(slug, requirement)
        return (
            known_pack or synthetic_pack or _pack_from_ref(ref, class_types=requirement.class_types),
            ref,
            warnings,
            failures,
        )

    ref = _resolve_with_resolver(resolver, slug, version_pin=version, aux_id=None)
    if ref is not None:
        return (
            known_pack or _pack_from_ref(ref, class_types=requirement.class_types),
            ref,
            warnings,
            failures,
        )
    return known_pack, _pack_ref_from_requirement(slug, requirement), warnings, failures


def _ordered_requirements(
    requirements_by_slug: Mapping[str, ProvenanceRequirement],
) -> list[tuple[str, ProvenanceRequirement]]:
    def key(item: tuple[str, ProvenanceRequirement]) -> tuple[int, str]:
        slug, requirement = item
        if slug == CORE_CNR_ID:
            return (3, slug)
        if requirement.aux_id:
            return (0, slug)
        if requirement.cnr_id:
            return (1, slug)
        return (2, slug)

    return sorted(requirements_by_slug.items(), key=key)


def _has_blocking_preinstall_failures(failures: Sequence[EnsureFailure]) -> bool:
    non_blocking = {"unresolved_pack"}
    return any(failure.code not in non_blocking for failure in failures)


def _resolve_unprovenanced_fallbacks(
    provenance: ProvenanceReport,
    *,
    known_packs: Mapping[str, CustomNodePack],
    install_roots: Sequence[Path],
    resolver: PackResolver | None,
) -> tuple[dict[str, CustomNodePack], dict[str, PackRef], list[EnsureWarning], list[EnsureFailure]]:
    packs: dict[str, CustomNodePack] = {}
    refs: dict[str, PackRef] = {}
    warnings: list[EnsureWarning] = []
    failures: list[EnsureFailure] = []
    for record in provenance.unprovenanced:
        local = find_installed_pack_ref(record.class_type, install_roots=install_roots)
        ref = local.pack_ref if local is not None else _resolve_with_resolver(resolver, record.class_type)
        if ref is None:
            continue
        slug = ref.slug
        pack = known_packs.get(slug) or _pack_from_ref(ref, class_types=(record.class_type,))
        packs.setdefault(slug, pack)
        refs.setdefault(slug, ref)
        warnings.append(
            EnsureWarning(
                code="class_to_pack_fallback",
                message=f"{record.class_type} was resolved by class-name fallback without authored provenance",
                slug=slug,
                pack_name=pack.name,
                node_ids=(record.node_id,),
                class_types=(record.class_type,),
                low_confidence=True,
            )
        )
    return packs, refs, warnings, failures


def _resolve_with_resolver(
    resolver: PackResolver | None,
    query: str,
    *,
    version_pin: str | None = None,
    aux_id: str | None = None,
    allow_remote_lookup: bool = True,
) -> PackRef | None:
    if resolver is None:
        return None
    try:
        return resolver(
            query,
            version_pin=version_pin,
            aux_id=aux_id,
            allow_remote_lookup=allow_remote_lookup,
        ).ref
    except PackNotFoundError:
        return None


def _pack_from_ref(ref: PackRef | None, *, class_types: Sequence[str]) -> CustomNodePack | None:
    if ref is None or not ref.url:
        return None
    return CustomNodePack(
        name=ref.slug,
        repo=ref.url,
        classes=frozenset(class_types),
    )


def _install_slug(requirement: ProvenanceRequirement) -> str | None:
    if requirement.cnr_id:
        return requirement.cnr_id
    if requirement.aux_id:
        return _slug_from_aux_id(requirement.aux_id)
    return None


def _pack_ref_from_requirement(slug: str, requirement: ProvenanceRequirement) -> PackRef | None:
    version = requirement.version_pin.version if requirement.version_pin is not None else None
    commit = version if _looks_like_commit(version) else None
    if requirement.aux_id:
        return PackRef(
            slug=slug,
            source="aux-git",
            version=version,
            commit=commit,
            url=_git_url_from_aux_id(requirement.aux_id),
            name=slug,
        )
    if requirement.cnr_id:
        return PackRef(
            slug=requirement.cnr_id,
            source="provenance",
            version=version,
            commit=commit,
            name=requirement.cnr_id,
        )
    return None


def _ensure_warnings_from_provenance(provenance: ProvenanceReport) -> list[EnsureWarning]:
    return [_ensure_warning_from_provenance_warning(warning) for warning in provenance.warnings]


def _ensure_warning_from_provenance_warning(warning: ProvenanceWarning) -> EnsureWarning:
    cnr_id, aux_id, version = _parse_identity_key(warning.identity_key)
    return EnsureWarning(
        code=warning.code,
        message=warning.message,
        slug=cnr_id or (_slug_from_aux_id(aux_id) if aux_id else None),
        pack_name=cnr_id or (_slug_from_aux_id(aux_id) if aux_id else None),
        node_ids=warning.node_ids,
        class_types=warning.class_types,
        cnr_id=cnr_id,
        aux_id=aux_id,
        version=version,
        low_confidence=warning.low_confidence,
    )


def _parse_identity_key(identity_key: str | None) -> tuple[str | None, str | None, str | None]:
    if not identity_key:
        return None, None, None
    parts: dict[str, str] = {}
    for part in identity_key.split("|"):
        key, _, value = part.partition(":")
        if key:
            parts[key] = value
    return (
        _none_if_dash(parts.get("cnr")),
        _none_if_dash(parts.get("aux")),
        _none_if_dash(parts.get("ver")),
    )


def _none_if_dash(value: str | None) -> str | None:
    return None if value in {None, "-", ""} else value


def _slug_from_locator_key(locator_key: str) -> str | None:
    cnr_id, aux_id, _version = _parse_identity_key(locator_key)
    return cnr_id or (_slug_from_aux_id(aux_id) if aux_id else None)


def _slug_from_aux_id(aux_id: str) -> str:
    cleaned = aux_id.strip().rstrip("/")
    name = cleaned.rsplit("/", 1)[-1]
    return name[:-4] if name.endswith(".git") else name


def _git_url_from_aux_id(aux_id: str) -> str:
    cleaned = aux_id.strip()
    if cleaned.startswith(("http://", "https://", "git@")):
        return cleaned
    return f"https://github.com/{cleaned}.git"


def _looks_like_commit(value: str | None) -> bool:
    return bool(value is not None and re.fullmatch(r"[0-9a-fA-F]{7,40}", value))


def _call_installer(
    installer: Installer,
    packs: Sequence[CustomNodePack],
    *,
    install_refs_by_name: Mapping[str, PackRef],
) -> InstallBatchResult:
    if not install_refs_by_name:
        return installer(packs)
    try:
        return installer(packs, install_refs_by_name=install_refs_by_name)
    except TypeError as exc:
        if "install_refs_by_name" not in str(exc):
            raise
        return installer(packs)


def _realization_signature(
    class_types_by_slug: Mapping[str, frozenset[str]],
    *,
    requirements_by_slug: Mapping[str, ProvenanceRequirement],
    resolved_refs_by_slug: Mapping[str, PackRef],
    install_refs_by_slug: Mapping[str, PackRef],
    installer: Installer,
    introspector: Introspector | None,
    cache_writer: CacheWriter | None,
    server_url: str | None,
) -> tuple[object, ...]:
    # Authored pack identity per slug: (slug, cnr_id, aux_id, version)
    authored_identity = tuple(
        (slug, req.cnr_id, req.aux_id, req.version_pin.version if req.version_pin else None)
        for slug, req in sorted(requirements_by_slug.items())
    )
    # Merged refs: resolved takes priority over planned/fallback
    merged_refs: dict[str, PackRef] = {}
    for slug, ref in install_refs_by_slug.items():
        merged_refs[slug] = ref
    for slug, ref in resolved_refs_by_slug.items():
        merged_refs[slug] = ref
    # Resolved/fallback ref identity per slug:
    #   (slug, source, version, commit, url, path, registry_id)
    ref_identity = tuple(
        (slug, ref.source, ref.version, ref.commit, ref.url, ref.path, ref.registry_id)
        for slug, ref in sorted(merged_refs.items())
    )
    return (
        tuple(
            (slug, tuple(sorted(class_types)))
            for slug, class_types in sorted(class_types_by_slug.items())
        ),
        authored_identity,
        ref_identity,
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
    refs_by_slug: Mapping[str, PackRef],
    low_confidence_slugs: set[str],
    include_core: bool,
) -> tuple[dict[str, Any], list[EnsureWarning]]:
    written: dict[str, dict[str, int]] = {}
    warnings: list[EnsureWarning] = []
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
            if slug in low_confidence_slugs:
                raise RuntimeError(f"cannot write object_info cache for low-confidence fallback pack {slug!r}")
            outcome = outcomes_by_slug.get(slug)
            git_commit = outcome.git_commit_sha if outcome is not None else None
            ref = refs_by_slug.get(slug)
            authored_version = ref.version if ref is not None else None
            authored_commit = ref.commit if ref is not None else None
            if not git_commit:
                if authored_version and not authored_commit:
                    warnings.append(
                        EnsureWarning(
                            code="cache_identity_unverified",
                            message=(
                                f"skipped object_info cache write for {slug!r}: authored version "
                                f"{authored_version!r} could not be verified to an installed HEAD"
                            ),
                            slug=slug,
                            pack_name=slug,
                            version=authored_version,
                        )
                    )
                    continue
                raise RuntimeError(f"cannot write object_info cache for {slug!r} without git commit identity")
            if authored_commit and git_commit.lower() != authored_commit.lower():
                raise RuntimeError(
                    f"cannot write object_info cache for {slug!r}: installed HEAD {git_commit} "
                    f"does not match authored commit {authored_commit}"
                )
            version = authored_version or git_commit
            identity = CacheIdentity(
                pack_slug=slug,
                pack_version=version,
                git_commit=git_commit,
                source_kind="runtime_object_info",
            )

        classes, packs = _build_cache_from_payload(slug, payload, identity=identity, version=version)
        written[slug] = {"classes": classes, "packs": packs}
    return {"written": written}, warnings


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
            version=identity.pack_version or version,
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
    "EnsureWarning",
    "ensure_env",
]
