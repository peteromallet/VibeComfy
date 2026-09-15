"""Bounded source snapshots and explicit installed-package execution.

The source snapshot is transport data, not an import hook.  Building a
capsule, inspecting it, and validating its manifest never imports or executes
user code.  :func:`execute_source_payload` is the deliberately explicit
runtime boundary used by ``vibecomfy.exec``.
"""

from __future__ import annotations

import ast
import asyncio
import base64
import binascii
import hashlib
import importlib
import importlib.metadata
import inspect
import io
import json
import re
import shutil
import sys
import tempfile
import types
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


CAPSULE_FORMAT = "vibecomfy.python_capsule/v1"
INSTALLED_FORMAT = "vibecomfy.python_installed/v1"
MAX_ENCODED_CAPSULE_BYTES = 4 * 1024 * 1024
MAX_EXPANDED_SOURCE_BYTES = 16 * 1024 * 1024
MAX_SOURCE_FILES = 512
MAX_PROMPT_SOURCE_BYTES = 16 * 1024 * 1024
_SAFE_COMPONENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_EXCLUDED_DIRS = frozenset(
    {".git", ".hg", ".svn", "__pycache__", ".venv", "venv", "node_modules",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "build", "dist",
}
)
_LOADED: dict[str, tuple[Path, str]] = {}


class PythonSourceError(ValueError):
    """A source snapshot or explicit runtime reference is invalid."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _normalize_dependencies(
    dependencies: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, str], ...]:
    """Validate the small, declarative dependency contract.

    Dependency metadata is inspected against the selected worker at queue
    time.  It is never installed implicitly by import, validation, or source
    inspection.
    """
    normalized: list[Mapping[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(dependencies):
        if not isinstance(item, Mapping):
            raise PythonSourceError(f"dependency {index} must be an object")
        distribution = item.get("distribution")
        specifier = item.get("specifier", "")
        if not isinstance(distribution, str) or not distribution.strip():
            raise PythonSourceError(f"dependency {index} needs a non-empty distribution")
        if not isinstance(specifier, str):
            raise PythonSourceError(f"dependency {index} specifier must be a string")
        name = distribution.strip()
        key = name.lower().replace("_", "-")
        if key in seen:
            raise PythonSourceError(f"duplicate dependency {name!r}")
        seen.add(key)
        normalized.append({"distribution": name, "specifier": specifier})
    return tuple(normalized)


def _dependency_failures(
    dependencies: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    failures: list[str] = []
    for item in dependencies:
        distribution = str(item["distribution"])
        specifier = str(item.get("specifier", ""))
        try:
            version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            failures.append(f"{distribution}{specifier} (missing)")
            continue
        if specifier:
            try:
                from packaging.specifiers import InvalidSpecifier, SpecifierSet

                try:
                    matches = version in SpecifierSet(specifier)
                except InvalidSpecifier as exc:
                    raise PythonSourceError(
                        f"invalid dependency specifier {specifier!r} for {distribution!r}: {exc}"
                    ) from exc
                if not matches:
                    failures.append(
                        f"{distribution}{specifier} (installed {version})"
                    )
            except ImportError:
                failures.append(
                    f"{distribution}{specifier} (cannot verify; packaging is unavailable)"
                )
    return tuple(failures)


def _dependency_readiness(
    dependencies: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    """Inspect declared distributions without importing or installing them."""
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    for item in dependencies:
        distribution = str(item["distribution"])
        specifier = str(item.get("specifier", ""))
        record: dict[str, Any] = {
            "distribution": distribution,
            "specifier": specifier,
            "installed_version": None,
            "status": "missing",
        }
        try:
            version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            failures.append(f"{distribution}{specifier} (missing)")
        else:
            record["installed_version"] = version
            if specifier:
                try:
                    from packaging.specifiers import InvalidSpecifier, SpecifierSet

                    try:
                        matches = version in SpecifierSet(specifier)
                    except InvalidSpecifier as exc:
                        record["status"] = "invalid_specifier"
                        failures.append(
                            f"{distribution}{specifier} (invalid specifier: {exc})"
                        )
                    else:
                        if not matches:
                            record["status"] = "version_mismatch"
                            failures.append(
                                f"{distribution}{specifier} (installed {version})"
                            )
                        else:
                            record["status"] = "ready"
                except ImportError:
                    record["status"] = "unverifiable"
                    failures.append(
                        f"{distribution}{specifier} (cannot verify; packaging is unavailable)"
                    )
            else:
                record["status"] = "ready"
        records.append(record)
    return records, tuple(failures)


def _safe_member_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise PythonSourceError("source member paths must be non-empty UTF-8 strings")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise PythonSourceError(f"unsafe source member path {value!r}")
    normalized = "/".join(path.parts)
    if normalized != value or "\\" in value:
        raise PythonSourceError(f"source member path is not canonical: {value!r}")
    return normalized


def _package_parts(package_root: str) -> tuple[str, ...]:
    if package_root == "":
        return ()
    if not isinstance(package_root, str) or not package_root:
        raise PythonSourceError("package_root must be a string")
    parts = tuple(part for part in package_root.replace("\\", "/").split("/") if part)
    if not parts or any(not _SAFE_COMPONENT.fullmatch(part) for part in parts):
        raise PythonSourceError(f"package_root must contain Python package names: {package_root!r}")
    return parts


def _validate_entrypoint(entrypoint: str, *, installed: bool) -> str:
    if not isinstance(entrypoint, str) or ":" not in entrypoint:
        raise PythonSourceError("entrypoint must use module:function spelling")
    module, attribute = entrypoint.split(":", 1)
    if not module or not attribute or any(not _SAFE_COMPONENT.fullmatch(part) for part in module.split(".")):
        raise PythonSourceError(f"invalid entrypoint {entrypoint!r}")
    if any(not _SAFE_COMPONENT.fullmatch(part) for part in attribute.split(".")):
        raise PythonSourceError(f"invalid entrypoint attribute {entrypoint!r}")
    if not installed and module.startswith("."):
        raise PythonSourceError("snapshot entrypoints are relative to package_root without a leading dot")
    return entrypoint


@dataclass(frozen=True, slots=True)
class SourceMember:
    path: str
    content: bytes
    sha256: str

    @classmethod
    def create(cls, path: str, content: bytes) -> "SourceMember":
        path = _safe_member_path(path)
        if not isinstance(content, bytes):
            raise TypeError("source member content must be bytes")
        return cls(path, bytes(content), _digest(content))

    def record(self) -> dict[str, Any]:
        return {"path": self.path, "bytes": len(self.content), "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class SourceCapsule:
    """Validated, deterministic source package snapshot."""

    source_id: str
    package_root: str
    entrypoint: str
    members: tuple[SourceMember, ...]
    dependencies: tuple[Mapping[str, Any], ...] = ()
    python: str | None = None
    provenance: str | None = None
    snapshot_sha256: str = ""
    archive_sha256: str = ""
    archive: bytes = b""

    def __post_init__(self) -> None:
        _package_parts(self.package_root)
        _validate_entrypoint(self.entrypoint, installed=False)
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise PythonSourceError("source_id must be non-empty")
        dependencies = _normalize_dependencies(self.dependencies)
        members = tuple(sorted(self.members, key=lambda item: item.path))
        if not members:
            raise PythonSourceError("a source capsule must contain at least one file")
        if len(members) > MAX_SOURCE_FILES:
            raise PythonSourceError(f"source capsule contains more than {MAX_SOURCE_FILES} files")
        if len({item.path for item in members}) != len(members):
            raise PythonSourceError("source capsule contains duplicate member paths")
        expanded = sum(len(item.content) for item in members)
        if expanded > MAX_EXPANDED_SOURCE_BYTES:
            raise PythonSourceError("expanded source capsule exceeds 16 MiB")
        for item in members:
            if item.sha256 != _digest(item.content):
                raise PythonSourceError(f"source member digest mismatch for {item.path!r}")
        object.__setattr__(self, "members", members)
        object.__setattr__(self, "dependencies", dependencies)
        archive = _make_archive(members)
        if len(archive) > MAX_ENCODED_CAPSULE_BYTES:
            raise PythonSourceError("encoded source capsule exceeds 4 MiB")
        manifest = self.manifest
        snapshot = _digest(_canonical_json(manifest))
        if self.snapshot_sha256 and self.snapshot_sha256 != snapshot:
            raise PythonSourceError("source snapshot digest does not match its manifest")
        archive_hash = _digest(archive)
        if self.archive and self.archive != archive:
            raise PythonSourceError("source archive is not the deterministic encoding of its members")
        if self.archive_sha256 and self.archive_sha256 != archive_hash:
            raise PythonSourceError("source archive digest mismatch")
        object.__setattr__(self, "snapshot_sha256", snapshot)
        object.__setattr__(self, "archive", archive)
        object.__setattr__(self, "archive_sha256", archive_hash)

    @property
    def manifest(self) -> dict[str, Any]:
        return {
            "package_root": self.package_root,
            "files": [item.record() for item in self.members],
            "dependencies": [dict(item) for item in self.dependencies],
            "python": self.python,
        }

    def to_payload(self) -> dict[str, Any]:
        return {
            "format": CAPSULE_FORMAT,
            "source_id": self.source_id,
            "snapshot_sha256": self.snapshot_sha256,
            "entrypoint": self.entrypoint,
            "manifest": self.manifest,
            "archive_encoding": "zip+base64",
            "archive_sha256": self.archive_sha256,
            "archive": base64.b64encode(self.archive).decode("ascii"),
            **({"provenance": self.provenance} if self.provenance else {}),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_payload(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def absolute_self_imports(self) -> tuple[str, ...]:
        """Return statically visible imports that cannot work privately."""
        root = ".".join(_package_parts(self.package_root))
        if not root:
            return ()
        found: set[str] = set()
        for member in self.members:
            if not member.path.endswith(".py"):
                continue
            try:
                tree = ast.parse(member.content.decode("utf-8"), filename=member.path)
            except (UnicodeDecodeError, SyntaxError):
                continue
            for item in ast.walk(tree):
                if isinstance(item, ast.Import):
                    for alias in item.names:
                        if alias.name == root or alias.name.startswith(root + "."):
                            found.add(alias.name)
                elif isinstance(item, ast.ImportFrom) and item.level == 0 and item.module:
                    if item.module == root or item.module.startswith(root + "."):
                        found.add(item.module)
        return tuple(sorted(found))

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SourceCapsule":
        if not isinstance(payload, Mapping) or payload.get("format") != CAPSULE_FORMAT:
            raise PythonSourceError("source payload is not a vibecomfy.python_capsule/v1 object")
        manifest = payload.get("manifest")
        if not isinstance(manifest, Mapping):
            raise PythonSourceError("source capsule manifest is required")
        package_root = manifest.get("package_root")
        _package_parts(package_root)
        records = manifest.get("files")
        if not isinstance(records, list):
            raise PythonSourceError("source capsule manifest.files must be a list")
        if payload.get("archive_encoding") != "zip+base64":
            raise PythonSourceError("source capsule archive_encoding must be 'zip+base64'")
        snapshot_sha256 = payload.get("snapshot_sha256")
        if not isinstance(snapshot_sha256, str) or not snapshot_sha256:
            raise PythonSourceError("source capsule snapshot_sha256 is required")
        archive_text = payload.get("archive")
        if not isinstance(archive_text, str):
            raise PythonSourceError("source capsule archive must be base64 text")
        try:
            archive = base64.b64decode(archive_text.encode("ascii"), validate=True)
        except (UnicodeEncodeError, binascii.Error) as exc:
            raise PythonSourceError("source capsule archive is not valid base64") from exc
        if len(archive) > MAX_ENCODED_CAPSULE_BYTES:
            raise PythonSourceError("encoded source capsule exceeds 4 MiB")
        if payload.get("archive_sha256") != _digest(archive):
            raise PythonSourceError("source archive digest mismatch")
        members = _read_archive(archive, records)
        dependencies = manifest.get("dependencies", [])
        if not isinstance(dependencies, list) or any(not isinstance(item, Mapping) for item in dependencies):
            raise PythonSourceError("manifest.dependencies must be a list of objects")
        source_id = payload.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            raise PythonSourceError("source_id must be a non-empty string")
        python = manifest.get("python")
        if python is not None and not isinstance(python, str):
            raise PythonSourceError("manifest.python must be a string when provided")
        return cls(
            source_id=source_id,
            package_root=str(package_root),
            entrypoint=_validate_entrypoint(str(payload.get("entrypoint") or ""), installed=False),
            members=tuple(members),
            dependencies=tuple(dict(item) for item in dependencies),
            python=python,
            provenance=payload.get("provenance") if isinstance(payload.get("provenance"), str) else None,
            snapshot_sha256=snapshot_sha256,
            archive_sha256=str(payload.get("archive_sha256") or ""),
            archive=archive,
        )


@dataclass(frozen=True, slots=True)
class InstalledEntrypoint:
    entrypoint: str
    revision: str | None = None
    dependencies: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        _validate_entrypoint(self.entrypoint, installed=True)
        object.__setattr__(self, "dependencies", _normalize_dependencies(self.dependencies))

    def to_payload(self) -> dict[str, Any]:
        return {
            "format": INSTALLED_FORMAT,
            "mode": "installed",
            "entrypoint": self.entrypoint,
            **({"revision": self.revision} if self.revision else {}),
            **({"dependencies": [dict(item) for item in self.dependencies]} if self.dependencies else {}),
        }


def _make_archive(members: Sequence[SourceMember]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for member in sorted(members, key=lambda item: item.path):
            info = zipfile.ZipInfo(member.path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, member.content)
    return output.getvalue()


def _read_archive(archive_bytes: bytes, records: Sequence[Any]) -> list[SourceMember]:
    if len(records) > MAX_SOURCE_FILES:
        raise PythonSourceError(f"source capsule contains more than {MAX_SOURCE_FILES} files")
    expected: dict[str, Mapping[str, Any]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            raise PythonSourceError("source manifest file records must be objects")
        path = _safe_member_path(record.get("path"))
        if path in expected:
            raise PythonSourceError(f"duplicate source member path {path!r}")
        expected[path] = record
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise PythonSourceError("source archive contains duplicate paths")
            if set(names) != set(expected):
                raise PythonSourceError("source archive paths do not match its manifest")
            members: list[SourceMember] = []
            expanded = 0
            for path in sorted(names):
                _safe_member_path(path)
                info = archive.getinfo(path)
                expanded += info.file_size
                if expanded > MAX_EXPANDED_SOURCE_BYTES:
                    raise PythonSourceError("expanded source capsule exceeds 16 MiB")
                content = archive.read(info)
                record = expected[path]
                if record.get("bytes") != len(content) or record.get("sha256") != _digest(content):
                    raise PythonSourceError(f"source member digest mismatch for {path!r}")
                members.append(SourceMember.create(path, content))
            return members
    except zipfile.BadZipFile as exc:
        raise PythonSourceError("source archive is not a valid zip") from exc


def capture_source(
    root: str | Path,
    *,
    entrypoint: str,
    source_id: str | None = None,
    include: Sequence[str] | None = None,
    dependencies: Sequence[Mapping[str, Any]] = (),
    python: str | None = None,
    provenance: str | None = None,
) -> SourceCapsule:
    """Capture a file or project directory without importing it."""
    path = Path(root).expanduser()
    if not path.exists() or path.is_symlink():
        raise PythonSourceError(f"source root does not exist or is a symlink: {path}")
    path = path.resolve()
    if path.is_file():
        root_dir = path.parent
        package_root = ""
        candidates = [(path, path.name)]
    elif path.is_dir():
        root_dir = path
        package_root = path.name
        candidates = []
        include_set = {str(item).replace("\\", "/") for item in include} if include is not None else None
        for candidate in sorted(path.rglob("*")):
            if candidate.is_dir():
                continue
            if candidate.is_symlink():
                raise PythonSourceError(f"source project contains a symlink: {candidate}")
            relative = candidate.relative_to(root_dir).as_posix()
            if any(part in _EXCLUDED_DIRS for part in PurePosixPath(relative).parts):
                continue
            if include_set is not None and relative not in include_set:
                continue
            candidates.append((candidate, f"{package_root}/{relative}"))
    else:
        raise PythonSourceError("source root must be a file or directory")
    members: list[SourceMember] = []
    for candidate, member_path in candidates:
        content = candidate.read_bytes()
        members.append(SourceMember.create(member_path, content))
    return SourceCapsule(
        source_id=source_id or package_root or path.stem,
        package_root=package_root,
        entrypoint=entrypoint,
        members=tuple(members),
        dependencies=tuple(dict(item) for item in dependencies),
        python=python,
        provenance=provenance,
    )


def installed_entrypoint(
    entrypoint: str,
    *,
    revision: str | None = None,
    dependencies: Sequence[Mapping[str, Any]] = (),
) -> InstalledEntrypoint:
    """Declare an environment-bound entrypoint; do not import it."""
    return InstalledEntrypoint(entrypoint, revision=revision, dependencies=tuple(dict(item) for item in dependencies))


def _verify_materialized(capsule: SourceCapsule, target: Path) -> None:
    """Verify a digest cache hit before allowing imports from it."""
    if target.is_symlink() or not target.is_dir():
        raise PythonSourceError(f"source cache entry is not a real directory: {target}")
    root = target / "_vibecomfy_sources" / f"s_{capsule.snapshot_sha256}"
    if root.is_symlink() or not root.is_dir():
        raise PythonSourceError(f"source cache entry is incomplete: {target}")
    expected = {member.path: member for member in capsule.members}
    actual: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise PythonSourceError(f"source cache contains a symlink: {path}")
        if path.is_file():
            relative = path.relative_to(root)
            # Importlib may leave bytecode alongside the verified source. It
            # is derived cache state, not a source member and is ignored by
            # the manifest comparison.
            if "__pycache__" in relative.parts or path.suffix == ".pyc":
                continue
            actual.add(relative.as_posix())
    if actual != set(expected):
        raise PythonSourceError("source cache files do not match the verified capsule manifest")
    for relative, member in expected.items():
        content = (root / relative).read_bytes()
        if content != member.content or _digest(content) != member.sha256:
            raise PythonSourceError(f"source cache digest mismatch for {relative!r}")


def _materialize(capsule: SourceCapsule, cache_dir: str | Path | None) -> tuple[Path, str]:
    base = Path(cache_dir).expanduser().resolve() if cache_dir else Path(tempfile.gettempdir()) / "vibecomfy-python-sources"
    base.mkdir(parents=True, exist_ok=True)
    package_name = f"s_{capsule.snapshot_sha256}"
    target = base / package_name
    cached = _LOADED.get(capsule.snapshot_sha256)
    if cached is not None and cached[0].resolve() == target.resolve():
        _verify_materialized(capsule, cached[0])
        return cached
    if target.exists():
        _verify_materialized(capsule, target)
    else:
        staging = Path(tempfile.mkdtemp(prefix=f".{package_name}-", dir=str(base)))
        try:
            private_root = staging / "_vibecomfy_sources" / package_name
            private_root.mkdir(parents=True)
            for member in capsule.members:
                destination = staging / "_vibecomfy_sources" / package_name / member.path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(member.content)
            target.parent.mkdir(parents=True, exist_ok=True)
            staging.rename(target)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        _verify_materialized(capsule, target)
    package_parts = ".".join(_package_parts(capsule.package_root))
    module_prefix = f"_vibecomfy_sources.{package_name}"
    if package_parts:
        module_prefix += f".{package_parts}"
    _LOADED[capsule.snapshot_sha256] = (target, module_prefix)
    return target, module_prefix


def _ensure_private_package(name: str, path: Path) -> None:
    """Register one digest-qualified package without changing sys.path."""
    if name in sys.modules:
        module = sys.modules[name]
        package_path = getattr(module, "__path__", None)
        if package_path is not None and str(path) not in package_path:
            package_path.append(str(path))
        return
    init_file = path / "__init__.py"
    if init_file.is_file():
        spec = importlib.util.spec_from_file_location(
            name,
            init_file,
            submodule_search_locations=[str(path)],
        )
        if spec is None or spec.loader is None:
            raise PythonSourceError(f"could not create an import spec for source package {name!r}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(name, None)
            raise
        return
    module = types.ModuleType(name)
    module.__package__ = name
    module.__path__ = [str(path)]  # type: ignore[attr-defined]
    module.__file__ = str(path)
    sys.modules[name] = module


def _prepare_private_namespace(capsule: SourceCapsule, target: Path, prefix: str) -> None:
    namespace_root = target / "_vibecomfy_sources"
    _ensure_private_package("_vibecomfy_sources", namespace_root)
    digest_name = prefix.rsplit(".", 1)[0]
    digest_path = namespace_root / digest_name.rsplit(".", 1)[-1]
    _ensure_private_package(digest_name, digest_path)
    parent_name = digest_name
    parent_path = digest_path
    for part in _package_parts(capsule.package_root):
        parent_name = f"{parent_name}.{part}"
        parent_path = parent_path / part
        _ensure_private_package(parent_name, parent_path)


def load_capsule_callable(capsule: SourceCapsule, *, cache_dir: str | Path | None = None) -> Any:
    """Import one verified snapshot at the explicit runtime boundary."""
    absolute = capsule.absolute_self_imports()
    if absolute:
        raise PythonSourceError(
            "portable source snapshot contains absolute self-import(s): "
            + ", ".join(absolute)
            + "; use relative imports or an installed entrypoint"
        )
    _target, prefix = _materialize(capsule, cache_dir)
    _prepare_private_namespace(capsule, _target, prefix)
    module, attribute = capsule.entrypoint.split(":", 1)
    full_module = f"{prefix}.{module}"
    try:
        value: Any = importlib.import_module(full_module)
        for name in attribute.split("."):
            value = getattr(value, name)
    except Exception as exc:
        raise PythonSourceError(f"source entrypoint {capsule.entrypoint!r} failed in {capsule.snapshot_sha256[:12]}") from exc
    if not callable(value):
        raise PythonSourceError(f"source entrypoint {capsule.entrypoint!r} is not callable")
    return value


def load_installed_callable(reference: InstalledEntrypoint) -> Any:
    """Import an installed entrypoint using normal worker package semantics."""
    module, attribute = reference.entrypoint.split(":", 1)
    try:
        value: Any = importlib.import_module(module)
        for name in attribute.split("."):
            value = getattr(value, name)
    except Exception as exc:
        raise PythonSourceError(
            f"installed entrypoint {reference.entrypoint!r} is unavailable in the current ComfyUI worker"
        ) from exc
    if not callable(value):
        raise PythonSourceError(f"installed entrypoint {reference.entrypoint!r} is not callable")
    return value


def _invoke(value: Any, inputs: Mapping[str, Any]) -> Any:
    signature = inspect.signature(value)
    positional: list[Any] = []
    keywords: dict[str, Any] = {}
    for parameter in signature.parameters.values():
        if parameter.kind is parameter.POSITIONAL_ONLY and parameter.name in inputs:
            positional.append(inputs[parameter.name])
        elif parameter.kind is parameter.VAR_POSITIONAL:
            extra = inputs.get(parameter.name, ())
            positional.extend(extra if isinstance(extra, (list, tuple)) else (extra,))
        elif parameter.kind is not parameter.VAR_KEYWORD and parameter.name in inputs:
            keywords[parameter.name] = inputs[parameter.name]
    result = value(*positional, **keywords)
    if inspect.isawaitable(result):
        result = asyncio.run(result)
    if inspect.isgenerator(result):
        result = list(result)
    return result


def adapt_result(result: Any, outputs: Sequence[str], mode: str = "mapping") -> dict[str, Any]:
    names = tuple(str(name) for name in outputs)
    if not names or len(set(names)) != len(names):
        raise PythonSourceError("source result adapter requires unique output names")
    if mode == "mapping":
        if not isinstance(result, Mapping):
            raise PythonSourceError("mapping result adapter requires a mapping result")
        return {name: result[name] for name in names}
    if mode == "single":
        if len(names) != 1:
            raise PythonSourceError("single result adapter requires exactly one output")
        return {names[0]: result}
    if mode in {"tuple", "list"}:
        if not isinstance(result, (tuple, list)) or len(result) != len(names):
            raise PythonSourceError("ordered result adapter requires one value per output")
        return dict(zip(names, result))
    raise PythonSourceError(f"unknown source result adapter mode {mode!r}")


def execute_source_payload(payload: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Execute a validated source payload and normalize its graph result."""
    if not isinstance(payload, Mapping):
        raise PythonSourceError("source payload must be an object")
    fmt = payload.get("format")
    if fmt == CAPSULE_FORMAT:
        reference = SourceCapsule.from_payload(payload)
        dependencies = reference.dependencies
    elif fmt == INSTALLED_FORMAT:
        reference = installed_entrypoint(
            str(payload.get("entrypoint") or ""),
            revision=payload.get("revision") if isinstance(payload.get("revision"), str) else None,
            dependencies=payload.get("dependencies", ())
            if isinstance(payload.get("dependencies", ()), list)
            else (),
        )
        dependencies = reference.dependencies
    else:
        raise PythonSourceError("unsupported Python source payload format")
    failures = _dependency_failures(dependencies)
    if failures:
        raise PythonSourceError(
            "Python source dependencies are not ready in the selected worker: "
            + ", ".join(failures)
        )
    callable_value = (
        load_capsule_callable(reference)
        if fmt == CAPSULE_FORMAT
        else load_installed_callable(reference)
    )
    result = _invoke(callable_value, inputs)
    adapter = payload.get("result", {})
    if not isinstance(adapter, Mapping):
        raise PythonSourceError("source result adapter must be an object")
    outputs = adapter.get("outputs", ())
    if isinstance(outputs, Mapping):
        outputs = list(outputs)
    if not isinstance(outputs, Sequence) or isinstance(outputs, (str, bytes)):
        raise PythonSourceError("source result adapter outputs must be a list")
    return adapt_result(result, outputs, str(adapter.get("mode", "mapping")))


def inspect_dependency_readiness(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return dependency/setup evidence without importing supplied source.

    The result is intentionally advisory: it reports the selected source mode,
    the worker's currently installed distributions, and whether execution may
    proceed.  It never mutates the environment and never loads an entrypoint.
    """
    if not isinstance(payload, Mapping):
        raise PythonSourceError("source payload must be an object")
    fmt = payload.get("format")
    if fmt == CAPSULE_FORMAT:
        reference = SourceCapsule.from_payload(payload)
        dependencies = reference.dependencies
        environment_bound = False
    elif fmt == INSTALLED_FORMAT:
        reference = installed_entrypoint(
            str(payload.get("entrypoint") or ""),
            revision=payload.get("revision") if isinstance(payload.get("revision"), str) else None,
            dependencies=payload.get("dependencies", ())
            if isinstance(payload.get("dependencies", ()), list)
            else (),
        )
        dependencies = reference.dependencies
        environment_bound = True
    else:
        raise PythonSourceError("unsupported Python source payload format")
    records, failures = _dependency_readiness(dependencies)
    return {
        "format": fmt,
        "environment_bound": environment_bound,
        "install_performed": False,
        "ready": not failures,
        "dependencies": records,
        "failures": list(failures),
    }


def loaded_source_stats() -> dict[str, int]:
    live = {key: value for key, value in _LOADED.items() if value[0].is_dir()}
    return {"loaded_sources": len(live), "loaded_source_bytes": sum(path.stat().st_size for path, _ in live.values() for path in path.rglob("*") if path.is_file())}


__all__ = [
    "CAPSULE_FORMAT", "INSTALLED_FORMAT", "MAX_ENCODED_CAPSULE_BYTES",
    "MAX_EXPANDED_SOURCE_BYTES", "MAX_PROMPT_SOURCE_BYTES", "MAX_SOURCE_FILES",
    "InstalledEntrypoint", "PythonSourceError", "SourceCapsule", "SourceMember",
    "adapt_result", "capture_source", "execute_source_payload", "inspect_dependency_readiness",
    "installed_entrypoint",
    "load_capsule_callable", "load_installed_callable", "loaded_source_stats",
]
