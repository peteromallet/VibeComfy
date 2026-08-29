"""Canonical output-directory authorization for the live agentic harness."""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath

_DEFAULT_OUTPUT_BASE = Path("out/agentic")


def _validate_fragment(name: str, value: str) -> str:
    fragment = str(value)
    if not fragment:
        raise ValueError(f"output path {name} must be non-empty")

    posix = PurePosixPath(fragment)
    windows = PureWindowsPath(fragment)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise ValueError(f"output path {name} must be relative: {fragment!r}")

    # Treat both separator spellings identically so authorization is portable.
    components = fragment.replace("\\", "/").split("/")
    if any(component in {"", ".", ".."} for component in components):
        raise ValueError(
            f"output path {name} contains an invalid path component: {fragment!r}"
        )
    return fragment


def authorized_output_dir(
    output_base: Path | str | None,
    tag: str,
    scenario_id: str | None = None,
) -> Path:
    """Return a confined harness output directory without creating it.

    Tags may contain ordinary nested components (the retry layout depends on
    this), but absolute paths, traversal components, and platform-dependent
    aliases are rejected. Existing symlinks are resolved for authorization so
    a tag or scenario directory cannot redirect writes outside ``output_base``.
    """
    base = Path(output_base) if output_base is not None else _DEFAULT_OUTPUT_BASE
    fragments = [_validate_fragment("tag", tag)]
    if scenario_id is not None:
        fragments.append(_validate_fragment("scenario_id", scenario_id))
    candidate = base.joinpath(*fragments)

    try:
        resolved_base = base.resolve(strict=False)
        candidate.resolve(strict=False).relative_to(resolved_base)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError(
            f"output directory escapes output_base {str(base)!r}: {str(candidate)!r}"
        ) from exc
    return candidate
