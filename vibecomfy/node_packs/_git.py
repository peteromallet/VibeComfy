from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from vibecomfy._git_utils import GitRunner, git_head, git_stdout
from vibecomfy.registry.pack_resolver import PackRef


@dataclass(frozen=True)
class InstalledPackGitRef:
    pack_ref: PackRef
    install_root: Path


def find_installed_pack_ref(
    query: str,
    *,
    install_roots: Iterable[Path],
    aux_id: str | None = None,
    version_pin: str | None = None,
    runner: GitRunner | None = None,
) -> InstalledPackGitRef | None:
    normalized_query = query.strip()
    normalized_aux_id = _normalize_aux_id(aux_id)
    if not normalized_query and normalized_aux_id is None:
        raise ValueError("query or aux_id is required")

    for install_root in install_roots:
        root = Path(install_root)
        if not root.exists() or not root.is_dir():
            continue
        for pack_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            metadata = _read_installed_pack_metadata(pack_dir, runner=runner)
            if metadata is None:
                continue
            if _matches_installed_pack(
                metadata,
                query=normalized_query,
                aux_id=normalized_aux_id,
            ):
                return InstalledPackGitRef(
                    pack_ref=_build_pack_ref(metadata, query=normalized_query, version_pin=version_pin),
                    install_root=root,
                )
    return None


def _read_installed_pack_metadata(pack_dir: Path, *, runner: GitRunner | None) -> dict[str, str] | None:
    if not (pack_dir / ".git").exists():
        return None
    origin_url = (git_stdout(pack_dir, ["config", "--get", "remote.origin.url"], runner=runner) or "").strip()
    head = git_head(pack_dir, runner=runner)
    if not origin_url or not head:
        return None
    aux_id = _aux_id_from_origin(origin_url)
    return {
        "dir_name": pack_dir.name,
        "path": str(pack_dir),
        "origin_url": origin_url,
        "head": head,
        "slug": _slug_from_origin(origin_url) or pack_dir.name,
        "aux_id": aux_id or "",
    }


def _matches_installed_pack(metadata: dict[str, str], *, query: str, aux_id: str | None) -> bool:
    if aux_id is not None and metadata.get("aux_id") == aux_id:
        return True
    if not query:
        return False
    lowered = query.lower()
    candidates = {
        metadata.get("dir_name", "").lower(),
        metadata.get("slug", "").lower(),
    }
    return lowered in candidates


def _build_pack_ref(metadata: dict[str, str], *, query: str, version_pin: str | None) -> PackRef:
    commit = metadata["head"]
    return PackRef(
        slug=metadata["slug"],
        source="local-git",
        version=version_pin,
        commit=commit,
        url=metadata["origin_url"],
        path=metadata["path"],
        name=query or metadata["dir_name"],
    )


def _normalize_aux_id(aux_id: str | None) -> str | None:
    if aux_id is None:
        return None
    stripped = aux_id.strip().strip("/")
    return stripped or None


def _aux_id_from_origin(origin_url: str) -> str | None:
    cleaned = origin_url.strip()
    if cleaned.startswith("git@github.com:"):
        cleaned = cleaned.split(":", 1)[1]
    elif cleaned.startswith("https://github.com/"):
        cleaned = cleaned.split("https://github.com/", 1)[1]
    else:
        return None
    cleaned = cleaned.removesuffix(".git").strip("/")
    parts = [part for part in cleaned.split("/") if part]
    if len(parts) < 2:
        return None
    return f"{parts[-2]}/{parts[-1]}"


def _slug_from_origin(origin_url: str) -> str | None:
    aux_id = _aux_id_from_origin(origin_url)
    if aux_id is None:
        return None
    return aux_id.split("/", 1)[1]


__all__ = ["InstalledPackGitRef", "find_installed_pack_ref"]
