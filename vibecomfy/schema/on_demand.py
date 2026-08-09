"""On-demand node-schema resolution for classes not known to any local source.

The escalation ladder (see docs/plans/all-installable-nodes.md):

* **Rung 1** (always, when on-demand is on): resolve the class's pack via the Comfy
  registry, shallow-clone its public source into a sandbox, and statically parse
  ``INPUT_TYPES`` via ``SourceSchemaProvider`` — **no execution** of the pack's
  Python. Safe and covers most nodes.
* **Rung 2** (sub-gated on ``VIBECOMFY_ON_DEMAND_BOOT=1``): on a rung-1 miss, exec
  the pack in an isolated stubbed subprocess and call ``cls.INPUT_TYPES()`` **at
  runtime** — faithful to dynamic inputs but executes third-party code, so it is
  opt-in. Implemented via ``vibecomfy.schema.extract.extract_by_import``.

Future rungs (transitive deps, version retry, LLM inference) escalate from here.
Every success is memoized in-process; the clone persists on disk so re-parse never
re-clones. The sandbox is **bounded** (LRU eviction by ``max_packs`` / ``max_bytes``;
env-tunable via ``VIBECOMFY_SCHEMA_SANDBOX_MAX_PACKS`` /
``VIBECOMFY_SCHEMA_SANDBOX_MAX_BYTES``) so it can't grow without limit.

Opt-in: only active when ``VIBECOMFY_ON_DEMAND_SCHEMAS=1`` (or constructed directly),
because a miss triggers network + git operations against public third-party repos.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any

_DEFAULT_SANDBOX = Path(
    os.environ.get("VIBECOMFY_SCHEMA_SANDBOX", "~/.cache/vibecomfy/schema-sandbox")
).expanduser()


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


# Bounded sandbox: cloned packs accumulate forever without a cap (this grew to
# 12 GiB on one machine). Eviction is LRU by directory mtime; tuned via env so a
# tight disk can shrink it and a generous one can grow it.
_DEFAULT_MAX_PACKS = _env_int("VIBECOMFY_SCHEMA_SANDBOX_MAX_PACKS", 64)
_DEFAULT_MAX_BYTES = _env_int("VIBECOMFY_SCHEMA_SANDBOX_MAX_BYTES", 2 * 1024 * 1024 * 1024)  # 2 GiB


def _dir_size(path: Path) -> int:
    total = 0
    try:
        for root, _dirs, files in os.walk(path):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _slug_from_url(url: str) -> str:
    tail = url.rstrip("/").split("/")[-1]
    return tail.removesuffix(".git") or "pack"


def _normalize_class_name(name: str) -> str:
    """Fold a node class name for fuzzy matching: underscores<->spaces, lowercased."""
    return name.replace("_", " ").strip().casefold()


class OnDemandInstallSchemaProvider:
    """Resolve a node's schema by cloning its pack and parsing source (no execution)."""

    def __init__(
        self,
        sandbox_root: str | Path | None = None,
        *,
        clone_timeout: int = 120,
        max_packs: int | None = None,
        max_bytes: int | None = None,
    ) -> None:
        self.sandbox_root = Path(sandbox_root) if sandbox_root is not None else _DEFAULT_SANDBOX
        self.clone_timeout = clone_timeout
        self.max_packs = _DEFAULT_MAX_PACKS if max_packs is None else max_packs
        self.max_bytes = _DEFAULT_MAX_BYTES if max_bytes is None else max_bytes
        self._cache: dict[str, Any] = {}  # class_type -> NodeSchema | None

    def get(self, class_type: str) -> Any:
        return self.get_schema(class_type)

    def get_schema(self, class_type: str) -> Any:
        if class_type in self._cache:
            return self._cache[class_type]
        schema = self._resolve(class_type)
        self._cache[class_type] = schema
        return schema

    def schemas(self) -> dict[str, Any]:
        # Only knows what it has already resolved on demand; not enumerable up front.
        return {k: v for k, v in self._cache.items() if v is not None}

    def _resolve(self, class_type: str) -> Any:
        ref = self._resolve_pack(class_type)
        if ref is None or not getattr(ref, "url", None):
            return None
        clone_path = self._ensure_clone(ref)
        if clone_path is None:
            return None
        slug = getattr(ref, "slug", None) or _slug_from_url(ref.url)

        # Rung 1 — static AST parse (no execution; safe). Covers most nodes.
        static_schema = None
        try:
            from vibecomfy.schema.provider import SourceSchemaProvider

            static_schema = SourceSchemaProvider([clone_path]).get_schema(class_type)
        except Exception:
            static_schema = None
        # A non-empty static schema is a real hit. An empty-inputs schema is a
        # degenerate parse (INPUT_TYPES was dynamic) — keep it as a fallback but
        # prefer rung 2 if it can do better.
        if static_schema is not None and static_schema.inputs:
            return replace(
                static_schema,
                source_provider="on_demand_static",
                source_package=slug,
                confidence=0.9,
            )

        # Rung 2 — subprocess runtime INPUT_TYPES() (executes third-party code).
        runtime_schema = self._resolve_runtime(class_type, clone_path, slug)
        if runtime_schema is not None:
            return runtime_schema
        # Fall back to the degenerate static schema (if any) rather than nothing.
        if static_schema is not None:
            return replace(
                static_schema,
                source_provider="on_demand_static",
                source_package=slug,
                confidence=0.9,
            )
        return None

    def _resolve_runtime(self, class_type: str, clone_path: Any, slug: str) -> Any:
        """Rung 2: exec the cloned pack in a stubbed subprocess, call INPUT_TYPES() at runtime.

        Gated on ``VIBECOMFY_ON_DEMAND_BOOT=1`` because it runs the pack's Python in a
        child process. Returns a runtime-extracted schema (confidence 1.0) or None.
        """
        if os.environ.get("VIBECOMFY_ON_DEMAND_BOOT") != "1":
            return None
        try:
            from vibecomfy.schema.extract import extract_by_import
            from vibecomfy.schema.provider import _schema_from_object_info

            # Extract ALL classes the pack exposes (the subprocess already does
            # the work; filtering would drop a match whose NODE_CLASS_MAPPINGS key
            # differs from the requested spelling).
            entries, _method = extract_by_import(
                clone_path,
                pack_name=slug,
                version="on-demand",
                only_classes=None,
                timeout=self.clone_timeout,
            )
        except Exception:
            return None
        # Match the requested class_type: exact key first, then normalized
        # (spaces <-> underscores, case-insensitive) so "CR_Text_List" finds
        # the canonical "CR Text List".
        matched_key = class_type if class_type in entries else None
        if matched_key is None:
            wanted = _normalize_class_name(class_type)
            for key in entries:
                if _normalize_class_name(key) == wanted:
                    matched_key = key
                    break
        if matched_key is None:
            return None
        try:
            schema = _schema_from_object_info(matched_key, entries[matched_key])
        except Exception:
            return None
        return replace(
            schema,
            source_provider="on_demand_runtime",
            source_package=slug,
            confidence=1.0,
        )

    def _resolve_pack(self, class_type: str) -> Any:
        try:
            from vibecomfy.registry.pack_resolver import resolve_missing_nodes

            resolution = resolve_missing_nodes(class_type)
        except Exception:
            return None
        for candidate in getattr(resolution, "candidates", ()) or ():
            ref = getattr(candidate, "ref", None)
            if ref is not None and getattr(ref, "url", None):
                return ref
        return None

    def _ensure_clone(self, ref: Any) -> Path | None:
        slug = getattr(ref, "slug", None) or getattr(ref, "registry_id", None) or _slug_from_url(ref.url)
        target = self.sandbox_root / slug
        if target.is_dir():
            # LRU: bump mtime so this clone reads as recently used for eviction.
            try:
                os.utime(target, None)
            except OSError:
                pass
            return target
        self._enforce_cap()  # make room before adding a new clone
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "clone", "--depth", "1", ref.url, str(target)],
                check=True,
                capture_output=True,
                timeout=self.clone_timeout,
            )
            return target
        except Exception:
            return None

    def _enforce_cap(self) -> None:
        """Evict oldest clones (LRU by mtime) to stay under max_packs / max_bytes.

        Best-effort: never raises. A failed eviction must not block a clone — the
        whole point is that on-demand resolution degrades gracefully.
        """
        try:
            if not self.sandbox_root.is_dir():
                return
            entries = []
            for child in self.sandbox_root.iterdir():
                if not child.is_dir():
                    continue
                try:
                    stat = child.stat()
                except OSError:
                    continue
                entries.append((child, stat.st_mtime, _dir_size(child)))
            if not entries:
                return
            entries.sort(key=lambda e: e[1])  # oldest mtime first
            total_bytes = sum(size for _, _, size in entries)
            total_packs = len(entries)
            for path, _mtime, size in entries:
                if total_packs <= self.max_packs and total_bytes <= self.max_bytes:
                    break
                shutil.rmtree(path, ignore_errors=True)
                total_packs -= 1
                total_bytes -= size
        except Exception:
            return
