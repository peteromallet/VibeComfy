"""Profile loading and resolution for the embedded VibeComfy executor.

Loads per-phase agent specs from Arnold-owned TOML profiles.  Each profile
maps the canonical stages (``classify``, ``research``, ``implement``,
``reply``) to an :class:`AgentSpecShape` with ``agent``, ``model``, and
``effort`` fields.

The primary source is ``arnold.pipelines.vibecomfy_executor.profiles``
loaded via ``importlib.resources``.  For testing, callers can override
the profile directory via ``set_profile_override_dir()``.

Spec-to-provider mapping (executed by ``agent_backend.py``, not here):
``AgentSpecShape.agent`` → VibeComfy provider ``route`` kwarg,
``AgentSpecShape.model`` → VibeComfy provider ``model`` kwarg,
``effort`` → may be ignored if the provider function does not accept it.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ── canonical stages ─────────────────────────────────────────────────────────

DECLARED_STAGES: frozenset[str] = frozenset({"classify", "research", "implement", "reply"})
_KNOWN_AGENTS: frozenset[str] = frozenset(
    {"hermes", "openrouter", "codex", "claude", "shannon"}
)

# ── AgentSpecShape ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentSpecShape:
    """Resolved agent specification for a single executor phase.

    ``agent`` maps to the VibeComfy provider ``route`` kwarg.
    ``model`` maps to the VibeComfy provider ``model`` kwarg.
    ``effort`` is a coarse hint (``"low"`` / ``"medium"`` / ``"high"``).
    """

    agent: str
    model: str
    effort: str = "low"

    def __post_init__(self) -> None:
        if self.effort not in ("low", "medium", "high"):
            object.__setattr__(self, "effort", "low")


# ── test path override ───────────────────────────────────────────────────────

# Module-level override: when set to a non-None Path, profile loading uses
# this directory instead of attempting importlib.resources on the Arnold
# package.  Call ``set_profile_override_dir(None)`` to restore the default.
_profile_override_dir: Path | None = None


def set_profile_override_dir(path: Path | str | None) -> None:
    """Override the directory from which profile TOMLs are loaded.

    Set to a :class:`Path` to load from a local directory (useful for testing).
    Set to ``None`` to restore the default Arnold package-resource behaviour.
    """
    global _profile_override_dir
    if path is None:
        _profile_override_dir = None
    else:
        _profile_override_dir = Path(path)


# ── profile directory resolution ─────────────────────────────────────────────


def _profile_dir() -> Path:
    """Return the resolved profile directory.

    Uses the test override when set; otherwise loads the profile TOMLs
    shipped inside ``vibecomfy.executor.profile_data`` so that external
    installs work without an Arnold checkout.
    """
    if _profile_override_dir is not None:
        return _profile_override_dir

    # Import here so the file is still importable even when Arnold is absent.
    from importlib import resources

    pkg_files = resources.files("vibecomfy.executor.profile_data")
    path = Path(str(pkg_files))
    if not path.is_dir() or not any(path.glob("*.toml")):
        raise FileNotFoundError(
            "Cannot locate executor profile directory. "
            "Install VibeComfy with the [agent] extra, or call "
            "set_profile_override_dir() to point to a local profile directory."
        )
    return path


# ── validation ───────────────────────────────────────────────────────────────


_EFFORT_TOKENS: frozenset[str] = frozenset({"low", "medium", "high"})


def _validate_stages(stage_map: dict[str, Any]) -> None:
    """Ensure *stage_map* contains exactly the declared stages."""
    stages = frozenset(stage_map.keys())
    missing = DECLARED_STAGES - stages
    extra = stages - DECLARED_STAGES
    if missing:
        raise ValueError(
            f"Profile is missing required stages: {sorted(missing)}"
        )
    if extra:
        raise ValueError(
            f"Profile contains unknown stages: {sorted(extra)}"
        )


def _parse_compact_spec(spec: str, *, stage: str) -> AgentSpecShape:
    """Parse a compact ``agent:model[:effort]`` string spec.

    Model identifiers may themselves contain colons (e.g.
    ``"hermes:openrouter:deepseek/deepseek-v4-pro"``), so effort is only extracted
    when the final colon-separated segment is a known effort token.
    """
    candidate = spec.strip()
    parts = candidate.split(":")
    if any(part == "" for part in parts):
        raise ValueError(
            f"Stage '{stage}' compact spec {spec!r} contains an empty segment."
        )

    agent = parts[0]
    if agent not in _KNOWN_AGENTS:
        raise ValueError(
            f"Stage '{stage}' agent '{agent}' is not a known agent. "
            f"Known agents: {sorted(_KNOWN_AGENTS)}"
        )

    if len(parts) == 1:
        raise ValueError(
            f"Stage '{stage}' compact spec {spec!r} must include a model."
        )

    if parts[-1] in _EFFORT_TOKENS and len(parts) >= 3:
        effort = parts[-1]
        model = ":".join(parts[1:-1])
    else:
        effort = "low"
        model = ":".join(parts[1:])

    if not model.strip():
        raise ValueError(
            f"Stage '{stage}' compact spec {spec!r} has an empty model."
        )

    return AgentSpecShape(agent=agent, model=model, effort=effort)


def _parse_spec(raw: Any, *, stage: str) -> AgentSpecShape:
    """Parse a single stage spec into an :class:`AgentSpecShape`.

    Accepts either the compact string form ``agent:model[:effort]`` or the
    legacy dict form with ``agent``, ``model`` and optional ``effort`` keys.
    """
    if isinstance(raw, str):
        return _parse_compact_spec(raw, stage=stage)

    if not isinstance(raw, dict):
        raise ValueError(
            f"Stage '{stage}' spec must be a string or dict, got {type(raw).__name__}."
        )

    # --- agent ---
    agent = raw.get("agent")
    if not isinstance(agent, str) or not agent.strip():
        raise ValueError(
            f"Stage '{stage}' must specify a non-empty string 'agent'."
        )
    agent = agent.strip()
    if agent not in _KNOWN_AGENTS:
        raise ValueError(
            f"Stage '{stage}' agent '{agent}' is not a known agent. "
            f"Known agents: {sorted(_KNOWN_AGENTS)}"
        )

    # --- model ---
    model = raw.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError(
            f"Stage '{stage}' must specify a non-empty string 'model'."
        )
    model = model.strip()

    # --- effort ---
    effort = raw.get("effort", "low")
    if not isinstance(effort, str) or effort not in _EFFORT_TOKENS:
        effort = "low"

    return AgentSpecShape(agent=agent, model=model, effort=effort)


# ── public API ───────────────────────────────────────────────────────────────


def load_profile(name: str) -> dict[str, AgentSpecShape]:
    """Load a single named profile.

    Reads ``{name}.toml`` from the profile directory and parses each
    declared stage into an :class:`AgentSpecShape`.

    Returns a mapping from stage name (``"classify"``, ``"research"``,
    ``"implement"``, ``"reply"``) to its resolved spec.
    """
    toml_path = _profile_dir() / f"{name}.toml"
    if not toml_path.is_file():
        raise FileNotFoundError(f"Profile '{name}' not found at {toml_path}")

    raw = tomllib.loads(toml_path.read_text(encoding="utf-8"))

    # Allow profiles to nest their stages under a top-level key.  Two common
    # conventions exist in the wild:
    #   1. Stages directly at top level.
    #   2. Stages under [profiles.{name}] (Arnold-style packaging).
    #   3. Stages under a single wrapper key such as [default] or [profile].
    has_stages_directly = bool(DECLARED_STAGES & frozenset(raw.keys()))
    if not has_stages_directly:
        # Convention 2: {profiles = {name = {classify = ...}}}
        if (
            "profiles" in raw
            and isinstance(raw["profiles"], dict)
            and isinstance(raw["profiles"].get(name), dict)
        ):
            raw = raw["profiles"][name]
        else:
            # Convention 3: single wrapper key containing the stage dict.
            for value in raw.values():
                if isinstance(value, dict) and DECLARED_STAGES & frozenset(value.keys()):
                    raw = value
                    break

    _validate_stages(raw)

    return {
        stage: _parse_spec(raw[stage], stage=stage) for stage in DECLARED_STAGES
    }


def load_all_profiles() -> dict[str, dict[str, AgentSpecShape]]:
    """Load every ``*.toml`` profile from the profile directory.

    Returns a mapping from profile name (stem) to its resolved stage map.
    """
    profiles: dict[str, dict[str, AgentSpecShape]] = {}
    for toml_path in sorted(_profile_dir().glob("*.toml")):
        name = toml_path.stem
        profiles[name] = load_profile(name)
    return profiles


__all__ = [
    "AgentSpecShape",
    "DECLARED_STAGES",
    "load_all_profiles",
    "load_profile",
    "set_profile_override_dir",
]
