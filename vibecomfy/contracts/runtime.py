"""The small typed runtime declaration embedded in workflow requirements."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


class RuntimeDependencyError(ValueError):
    """A runtime declaration is malformed."""


@dataclass(frozen=True, slots=True)
class RuntimeRequirements:
    comfy_source: str | None = None
    comfy_ref: str | None = None
    comfy_commit: str | None = None
    comfy_version: str | None = None
    python_version: str | None = None
    packages: tuple[tuple[str, str], ...] = ()
    package_indexes: tuple[str, ...] = ()
    launch_flags: tuple[str, ...] = ()
    models: tuple[dict[str, Any], ...] = ()
    custom_nodes: tuple[dict[str, Any], ...] = ()
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def python_packages(self) -> dict[str, str]:
        return dict(self.packages)

    @property
    def python_env(self) -> dict[str, str]:
        result = dict(self.packages)
        if self.python_version:
            result["python"] = self.python_version
        return result

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.comfy_source is not None:
            result["comfy_source"] = self.comfy_source
        if self.comfy_ref is not None:
            result["comfy_ref"] = self.comfy_ref
        if self.comfy_commit is not None:
            result["comfy_commit"] = self.comfy_commit
        if self.comfy_version is not None:
            result["comfy_version"] = self.comfy_version
        if self.python_version is not None:
            result["python_version"] = self.python_version
        if self.packages:
            result["packages"] = dict(self.packages)
        if self.package_indexes:
            result["package_indexes"] = list(self.package_indexes)
        if self.launch_flags:
            result["launch_flags"] = list(self.launch_flags)
        if self.models:
            result["models"] = [dict(item) for item in self.models]
        if self.custom_nodes:
            result["custom_nodes"] = [dict(item) for item in self.custom_nodes]
        result.update({key: value for key, value in self.extras.items() if key not in result})
        return result

    @classmethod
    def from_dict(
        cls,
        raw: Mapping[str, Any] | None,
        *,
        legacy_python_env: Mapping[str, Any] | None = None,
        legacy_comfy_commit: str | None = None,
    ) -> "RuntimeRequirements | None":
        if raw is None and legacy_python_env is None and legacy_comfy_commit is None:
            return None
        if raw is not None and not isinstance(raw, Mapping):
            raise RuntimeDependencyError("requirements.runtime must be a mapping")
        value = dict(raw or {})
        comfy = value.get("comfyui", value.get("comfy", {}))
        if comfy is not None and not isinstance(comfy, Mapping):
            raise RuntimeDependencyError("requirements.runtime.comfyui must be a mapping")
        comfy_source = _optional_string(
            value.get("comfy_source", value.get("comfy_url")),
            "requirements.runtime.comfy_source",
        )
        nested_comfy_source = (
            _optional_string(
                comfy.get("source", comfy.get("url")),
                "requirements.runtime.comfyui.source",
            )
            if isinstance(comfy, Mapping)
            else None
        )
        if comfy_source and nested_comfy_source and comfy_source != nested_comfy_source:
            raise RuntimeDependencyError(
                "requirements.runtime.comfy_source contradicts requirements.runtime.comfyui.source"
            )
        comfy_source = comfy_source or nested_comfy_source
        comfy_ref = _optional_string(
            value.get("comfy_ref"), "requirements.runtime.comfy_ref"
        )
        nested_comfy_ref = (
            _optional_string(
                comfy.get("ref", comfy.get("branch")),
                "requirements.runtime.comfyui.ref",
            )
            if isinstance(comfy, Mapping)
            else None
        )
        if comfy_ref and nested_comfy_ref and comfy_ref != nested_comfy_ref:
            raise RuntimeDependencyError(
                "requirements.runtime.comfy_ref contradicts requirements.runtime.comfyui.ref"
            )
        comfy_ref = comfy_ref or nested_comfy_ref
        comfy_commit = _optional_string(value.get("comfy_commit"), "requirements.runtime.comfy_commit")
        nested_comfy_commit = (
            _optional_string(comfy.get("commit"), "requirements.runtime.comfyui.commit")
            if isinstance(comfy, Mapping)
            else None
        )
        if comfy_commit and nested_comfy_commit and comfy_commit != nested_comfy_commit:
            raise RuntimeDependencyError(
                "requirements.runtime.comfy_commit contradicts requirements.runtime.comfyui.commit"
            )
        if comfy_commit is None:
            comfy_commit = nested_comfy_commit
        if legacy_comfy_commit and comfy_commit and legacy_comfy_commit != comfy_commit:
            raise RuntimeDependencyError("runtime comfy_commit contradicts legacy metadata.comfy_commit")
        comfy_commit = comfy_commit or legacy_comfy_commit
        comfy_version = _optional_string(value.get("comfy_version"), "requirements.runtime.comfy_version")
        nested_comfy_version = (
            _optional_string(comfy.get("version"), "requirements.runtime.comfyui.version")
            if isinstance(comfy, Mapping)
            else None
        )
        if comfy_version and nested_comfy_version and comfy_version != nested_comfy_version:
            raise RuntimeDependencyError(
                "requirements.runtime.comfy_version contradicts requirements.runtime.comfyui.version"
            )
        if comfy_version is None:
            comfy_version = nested_comfy_version
        python = value.get("python", {})
        if python is not None and not isinstance(python, Mapping):
            raise RuntimeDependencyError("requirements.runtime.python must be a mapping")
        python_version = _optional_string(value.get("python_version"), "requirements.runtime.python_version")
        nested_python_version = (
            _optional_string(python.get("version"), "requirements.runtime.python.version")
            if isinstance(python, Mapping)
            else None
        )
        if python_version and nested_python_version and python_version != nested_python_version:
            raise RuntimeDependencyError(
                "requirements.runtime.python_version contradicts requirements.runtime.python.version"
            )
        if python_version is None:
            python_version = nested_python_version
        packages = _merge_package_constraints(value)
        indexes_raw = value.get(
            "package_indexes",
            value.get("pip_indexes", value.get("indexes", value.get("package_index", []))),
        )
        if indexes_raw is None:
            indexes_raw = []
        if isinstance(indexes_raw, str):
            indexes_raw = [indexes_raw]
        if not isinstance(indexes_raw, (list, tuple)) or not all(
            isinstance(item, str) and item.strip() for item in indexes_raw
        ):
            raise RuntimeDependencyError(
                "requirements.runtime.package_indexes must be an array of nonblank strings"
            )
        if legacy_python_env is not None:
            for name, constraint in legacy_python_env.items():
                if not isinstance(name, str) or not isinstance(constraint, str) or not constraint.strip():
                    raise RuntimeDependencyError("metadata.python_env entries must be string constraints")
                if name == "python":
                    if python_version and python_version != constraint.strip():
                        raise RuntimeDependencyError("runtime python_version contradicts legacy metadata.python_env.python")
                    python_version = python_version or constraint.strip()
                else:
                    old = constraint.strip()
                    if name in packages and packages[name] != old:
                        raise RuntimeDependencyError(f"runtime package {name!r} contradicts legacy metadata.python_env")
                    packages.setdefault(name.strip(), old)
        flags_raw = value.get("launch_flags", value.get("launch", []))
        if isinstance(flags_raw, Mapping):
            flags_raw = flags_raw.get("flags", [])
        if flags_raw is None:
            flags_raw = []
        if not isinstance(flags_raw, (list, tuple)) or not all(isinstance(item, str) and item.strip() for item in flags_raw):
            raise RuntimeDependencyError("requirements.runtime.launch_flags must be an array of nonblank strings")
        known = {
            "comfyui", "comfy", "comfy_source", "comfy_url", "comfy_ref",
            "comfy_commit", "comfy_version", "python", "python_version",
            "packages", "python_packages", "package_indexes", "pip_indexes",
            "indexes", "package_index", "launch", "launch_flags", "models",
            "custom_nodes",
        }
        return cls(
            comfy_source=comfy_source,
            comfy_ref=comfy_ref,
            comfy_commit=comfy_commit,
            comfy_version=comfy_version,
            python_version=python_version,
            packages=tuple(sorted(packages.items())),
            package_indexes=tuple(dict.fromkeys(item.strip() for item in indexes_raw)),
            launch_flags=tuple(dict.fromkeys(item.strip() for item in flags_raw)),
            models=tuple(_object_list(value.get("models"), "requirements.runtime.models")),
            custom_nodes=tuple(_normalize_runtime_custom_nodes(value.get("custom_nodes"))),
            extras={str(key): item for key, item in value.items() if key not in known},
        )


def _optional_string(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise RuntimeDependencyError(f"{label} must be a nonblank string or null")
    return value.strip()


def _object_list(value: Any, label: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise RuntimeDependencyError(f"{label} must be an array")
    result: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            result.append({"name": item})
        elif isinstance(item, Mapping):
            result.append({str(key): child for key, child in item.items()})
        else:
            raise RuntimeDependencyError(f"{label} entries must be strings or mappings")
    return result


def _merge_package_constraints(value: Mapping[str, Any]) -> dict[str, str]:
    """Merge package aliases while rejecting contradictory exact facts."""
    packages: dict[str, str] = {}
    locations: dict[str, tuple[str, str]] = {}
    for key, label in (("packages", "requirements.runtime.packages"), ("python_packages", "requirements.runtime.python_packages")):
        raw = value.get(key)
        if raw is None:
            continue
        if isinstance(raw, Mapping):
            entries = raw.items()
        elif isinstance(raw, (list, tuple)):
            # Older envelopes serialized the canonical package tuple as a
            # list of [name, constraint] pairs.  Accept that wire shape at
            # the decoder boundary and normalize it to the same mapping used
            # by the current contract; do not weaken entry validation.
            entries = []
            for index, item in enumerate(raw):
                if not isinstance(item, (list, tuple)) or len(item) != 2:
                    raise RuntimeDependencyError(
                        f"{label}[{index}] must be a [name, constraint] pair"
                    )
                entries.append((item[0], item[1]))
        else:
            raise RuntimeDependencyError(f"{label} must be a mapping or package pairs")
        for name, constraint in entries:
            if not isinstance(name, str) or not name.strip() or not isinstance(constraint, str) or not constraint.strip():
                raise RuntimeDependencyError(f"{label} entries need nonblank name and constraint")
            normalized_name = name.strip()
            normalized_constraint = constraint.strip()
            previous = packages.get(normalized_name)
            if previous is not None and previous != normalized_constraint:
                old_location, old_value = locations[normalized_name]
                raise RuntimeDependencyError(
                    f"conflicting runtime package constraint for {normalized_name!r}: "
                    f"{old_value!r} at {old_location} conflicts with "
                    f"{normalized_constraint!r} at {label}[{name!r}]"
                )
            packages[normalized_name] = normalized_constraint
            locations[normalized_name] = (f"{label}[{name!r}]", normalized_constraint)
    return packages


def _normalize_runtime_custom_nodes(value: Any) -> list[dict[str, Any]]:
    """Normalize legacy runtime custom-node rows and reject exact conflicts."""
    rows = _object_list(value, "requirements.runtime.custom_nodes")
    seen: dict[str, tuple[dict[str, Any], int]] = {}
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        selector = str(row.get("slug") or row.get("name") or "").strip()
        if not selector:
            # Preserve old descriptive rows that have no selector.
            result.append(row)
            continue
        prior = seen.get(selector)
        if prior is not None:
            old, old_index = prior
            for field in ("commit", "version", "url", "path"):
                old_value, new_value = old.get(field), row.get(field)
                if old_value not in (None, "") and new_value not in (None, "") and str(old_value) != str(new_value):
                    raise RuntimeDependencyError(
                        f"conflicting exact runtime custom-node ref {selector!r}: "
                        f"{field} {old_value!r} at requirements.runtime.custom_nodes[{old_index}] "
                        f"conflicts with {new_value!r} at requirements.runtime.custom_nodes[{index}]"
                    )
            merged = dict(old)
            for key, child in row.items():
                if key in {"classes", "class_set"} and isinstance(child, (list, tuple)):
                    merged[key] = sorted(set(merged.get(key, ())) | set(child))
                else:
                    merged.setdefault(key, child)
            result[result.index(old)] = merged
            seen[selector] = (merged, old_index)
        else:
            seen[selector] = (row, index)
            result.append(row)
    return result


__all__ = ["RuntimeDependencyError", "RuntimeRequirements"]
