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

import json
import os
import shutil
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

from vibecomfy.errors import OnDemandCloneError

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
_CLONE_COMPLETE_MARKER = ".vibecomfy-clone-complete.json"


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


def _safe_slug(slug: Any) -> str:
    if not isinstance(slug, str) or not slug or "\x00" in slug:
        raise ValueError("on-demand pack slug must be a non-empty string")
    path = Path(slug)
    if slug in {".", ".."} or "/" in slug or "\\" in slug or path.is_absolute() or path.name != slug:
        raise ValueError("on-demand pack slug must be a single path-safe component")
    return slug


def _git_diagnostics(command: list[str], exc: BaseException) -> str:
    stdout = getattr(exc, "stdout", None) or getattr(exc, "output", None) or ""
    stderr = getattr(exc, "stderr", None) or ""
    if isinstance(stdout, bytes):
        stdout = stdout.decode(errors="replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode(errors="replace")
    details = [f"git command failed: {' '.join(command)}"]
    returncode = getattr(exc, "returncode", None)
    if returncode is not None:
        details.append(f"returncode={returncode}")
    if stdout:
        details.append(f"stdout: {str(stdout).strip()}")
    if stderr:
        details.append(f"stderr: {str(stderr).strip()}")
    if isinstance(exc, subprocess.TimeoutExpired):
        details.append("timed out")
    if isinstance(exc, OSError):
        details.append(str(exc))
    return "; ".join(details)


def _run_git(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise OnDemandCloneError(_git_diagnostics(command, exc)) from exc


def _has_active_reader(path: Path) -> bool:
    for lease in path.glob(".vibecomfy-reader-*.lease"):
        try:
            pid = int(lease.read_text(encoding="ascii").strip())
            os.kill(pid, 0)
        except ProcessLookupError:
            try:
                lease.unlink()
            except OSError:
                pass
        except (OSError, ValueError):
            return True
        else:
            return True
    return False


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
        self.last_clone_error: str | None = None

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

        with self._reader_lease(clone_path):
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
            source_provider="on_demand_import",
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
        slug = _safe_slug(slug)
        target = self.sandbox_root / slug
        pin = getattr(ref, "version", None) or getattr(ref, "commit", None)
        url = getattr(ref, "url", None)
        self.last_clone_error = None
        if target.is_symlink():
            error = OnDemandCloneError(f"refusing symlinked on-demand clone at {target}")
            self.last_clone_error = str(error)
            raise error
        if target.is_dir():
            if self._is_complete_clone(target, slug, pin, url):
                try:
                    os.utime(target, None)
                except OSError:
                    pass
                return target
            if _has_active_reader(target):
                error = OnDemandCloneError(
                    f"refusing incomplete on-demand clone with an active reader at {target}"
                )
                self.last_clone_error = str(error)
                raise error
            try:
                shutil.rmtree(target)
            except OSError as exc:
                error = OnDemandCloneError(f"could not clean incomplete on-demand clone at {target}: {exc}")
                self.last_clone_error = str(error)
                raise error from exc
        elif target.exists():
            error = OnDemandCloneError(f"refusing existing non-directory on-demand clone at {target}")
            self.last_clone_error = str(error)
            raise error
        self._enforce_cap()  # make room before adding a new clone
        staging_parent: Path | None = None
        try:
            self.sandbox_root.mkdir(parents=True, exist_ok=True)
            staging_parent = Path(tempfile.mkdtemp(prefix=f".{slug}-", dir=self.sandbox_root))
            staging = staging_parent / slug
            if pin:
                _run_git(["git", "clone", ref.url, str(staging)], self.clone_timeout)
                _run_git(
                    ["git", "-C", str(staging), "fetch", "--tags", "--depth", "1", "origin", pin],
                    30,
                )
                _run_git(["git", "-C", str(staging), "checkout", pin], 10)
            else:
                _run_git(["git", "clone", "--depth", "1", ref.url, str(staging)], self.clone_timeout)
            head = _run_git(["git", "-C", str(staging), "rev-parse", "HEAD"], 10).stdout.strip()
            if pin:
                want = _run_git(["git", "-C", str(staging), "rev-parse", f"{pin}^{{commit}}"], 10).stdout.strip()
                if not want or head != want:
                    raise OnDemandCloneError(
                        f"git checkout did not reach requested pin {pin!r}: head={head!r}, expected={want!r}"
                    )
            (staging / _CLONE_COMPLETE_MARKER).write_text(
                json.dumps(
                    {"complete": True, "slug": slug, "url": ref.url, "pin": pin, "head": head},
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            if target.exists() or target.is_symlink():
                raise OnDemandCloneError(f"on-demand clone target appeared during publish: {target}")
            os.replace(staging, target)
            return target
        except OnDemandCloneError as exc:
            self.last_clone_error = str(exc)
            raise
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            error = OnDemandCloneError(_git_diagnostics([], exc))
            self.last_clone_error = str(error)
            raise error from exc
        finally:
            if staging_parent is not None:
                shutil.rmtree(staging_parent, ignore_errors=True)

    def _is_complete_clone(
        self, target: Path, slug: str, pin: str | None, url: str | None = None
    ) -> bool:
        if target.is_symlink():
            return False
        git_dir = target / ".git"
        if git_dir.is_symlink() or not git_dir.exists():
            return False
        marker = target / _CLONE_COMPLETE_MARKER
        if marker.is_symlink():
            return False
        # Accept a valid legacy checkout created before transactional clone
        # markers were introduced. It is safe to reuse only an actual Git
        # checkout; incomplete test/staging directories do not contain HEAD
        # and objects, so they still take the cleanup-and-retry path below.
        if not marker.exists() and (git_dir / "HEAD").is_file() and (git_dir / "objects").is_dir():
            try:
                head = _run_git(["git", "-C", str(target), "rev-parse", "HEAD"], 10).stdout.strip()
                if head:
                    return True
            except (OSError, ValueError, TypeError, subprocess.SubprocessError, OnDemandCloneError):
                return False
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("complete") is not True:
                return False
            if data.get("slug") != slug or data.get("pin") != pin:
                return False
            if url is not None and data.get("url") != url:
                return False
            head = _run_git(["git", "-C", str(target), "rev-parse", "HEAD"], 10).stdout.strip()
            return data.get("head") == head
        except (OSError, ValueError, TypeError, json.JSONDecodeError, OnDemandCloneError):
            return False

    @contextmanager
    def _reader_lease(self, clone_path: Path):
        lease = clone_path / f".vibecomfy-reader-{os.getpid()}-{uuid.uuid4().hex}.lease"
        try:
            lease.write_text(str(os.getpid()), encoding="ascii")
        except OSError as exc:
            raise OnDemandCloneError(f"could not lease on-demand clone for reading: {clone_path}") from exc
        try:
            yield clone_path
        finally:
            try:
                lease.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass

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
                if not child.is_dir() or child.name.startswith("."):
                    continue
                if _has_active_reader(child):
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
