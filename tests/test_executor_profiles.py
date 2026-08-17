"""Unit tests for profile loading and resolution.

Exercises ``vibecomfy/executor/profiles.py``: profile TOML parsing, stage
validation, agent validation, effort normalization, test path override,
and the four canonical profiles (``default``, ``openai``, ``anthropic``,
``opensource``).
"""

from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path
from typing import Generator

import pytest

from vibecomfy.executor.profiles import (
    ALLOWED_STAGES,
    DECLARED_STAGES,
    REQUIRED_STAGES,
    AgentSpecShape,
    MissingProfileStageError,
    load_all_profiles,
    load_profile,
    set_profile_override_dir,
)


# ── helpers ──────────────────────────────────────────────────────────────────


def _write_toml(dir_path: Path, name: str, content: str) -> Path:
    """Write a TOML profile file into *dir_path* and return its path."""
    file_path = dir_path / f"{name}.toml"
    file_path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return file_path


_BASE_PROFILE = """
[classify]
agent = "hermes"
model = "openrouter:deepseek/deepseek-v4-flash"
effort = "low"

[research]
agent = "hermes"
model = "openrouter:deepseek/deepseek-v4-pro"
effort = "medium"

[implement]
agent = "codex"
model = "gpt-5.4"
effort = "high"

[execute]
agent = "codex"
model = "gpt-5.4"
effort = "high"

[reply]
agent = "hermes"
model = "openrouter:deepseek/deepseek-v4-pro"
effort = "low"
"""


@pytest.fixture
def profile_dir() -> Generator[Path, None, None]:
    """Temporary directory populated with the four canonical profiles."""
    with tempfile.TemporaryDirectory() as tmp:
        dir_path = Path(tmp)
        _write_toml(dir_path, "default", _BASE_PROFILE)
        _write_toml(dir_path, "openai", _BASE_PROFILE.replace('"codex"', '"codex"').replace('"gpt-5.4"', '"gpt-5.5"'))
        _write_toml(dir_path, "anthropic", _BASE_PROFILE.replace('"codex"', '"claude"').replace('"gpt-5.4"', '"claude-sonnet-4-5"'))
        _write_toml(dir_path, "opensource", _BASE_PROFILE.replace('"codex"', '"shannon"').replace('"gpt-5.4"', '"openrouter/hermes-3-70b"'))
        set_profile_override_dir(dir_path)
        yield dir_path
        set_profile_override_dir(None)


def _stage_names(profile: dict[str, AgentSpecShape]) -> set[str]:
    return set(profile.keys())


# ── canonical stages ─────────────────────────────────────────────────────────


def test_required_stages_are_exactly_the_four_full_mode_phases() -> None:
    """The module-level required set contains exactly the four full-mode phases."""
    assert REQUIRED_STAGES == {"classify", "research", "implement", "reply"}


def test_allowed_stages_add_only_execute() -> None:
    """``execute`` is the ONLY allowed extra stage (the two-step phase)."""
    assert ALLOWED_STAGES == REQUIRED_STAGES | {"execute"}


def test_declared_stages_alias_stays_the_four_full_mode_phases() -> None:
    """Backwards-compatible alias keeps the historical four-phase meaning."""
    assert DECLARED_STAGES == REQUIRED_STAGES
    assert DECLARED_STAGES == {"classify", "research", "implement", "reply"}


# ── AgentSpecShape ───────────────────────────────────────────────────────────


def test_agent_spec_shape_defaults() -> None:
    spec = AgentSpecShape(agent="hermes", model="deepseek-v4")
    assert spec.agent == "hermes"
    assert spec.model == "deepseek-v4"
    assert spec.effort == "low"


def test_agent_spec_shape_explicit_effort() -> None:
    spec = AgentSpecShape(agent="codex", model="gpt-5.4", effort="high")
    assert spec.effort == "high"


def test_agent_spec_shape_invalid_effort_clamps_to_low() -> None:
    spec = AgentSpecShape(agent="hermes", model="d", effort="extreme")
    assert spec.effort == "low"


# ── profile loading (happy path) ─────────────────────────────────────────────


class TestLoadProfile:
    """Tests for ``load_profile()`` with valid fixture profiles."""

    def test_load_default_profile(self, profile_dir: Path) -> None:
        profile = load_profile("default")
        assert _stage_names(profile) == ALLOWED_STAGES

        classify = profile["classify"]
        assert classify.agent == "hermes"
        assert classify.model == "openrouter:deepseek/deepseek-v4-flash"
        assert classify.effort == "low"

        research = profile["research"]
        assert research.agent == "hermes"
        assert research.model == "openrouter:deepseek/deepseek-v4-pro"
        assert research.effort == "medium"

        implement = profile["implement"]
        assert implement.agent == "codex"
        assert implement.model == "gpt-5.4"
        assert implement.effort == "high"

        execute = profile["execute"]
        assert execute.agent == "codex"
        assert execute.model == "gpt-5.4"
        assert execute.effort == "high"

        reply = profile["reply"]
        assert reply.agent == "hermes"
        assert reply.model == "openrouter:deepseek/deepseek-v4-pro"
        assert reply.effort == "low"

    def test_load_openai_profile(self, profile_dir: Path) -> None:
        profile = load_profile("openai")
        assert profile["classify"].agent == "hermes"
        assert profile["implement"].agent == "codex"
        assert profile["implement"].model == "gpt-5.5"
        # execute follows the implement family in the fixture profiles.
        assert profile["execute"].agent == "codex"
        assert profile["execute"].model == "gpt-5.5"

    def test_load_anthropic_profile(self, profile_dir: Path) -> None:
        profile = load_profile("anthropic")
        assert profile["classify"].agent == "hermes"
        assert profile["implement"].agent == "claude"
        assert profile["implement"].model == "claude-sonnet-4-5"
        assert profile["execute"].agent == "claude"

    def test_load_opensource_profile(self, profile_dir: Path) -> None:
        profile = load_profile("opensource")
        assert profile["classify"].agent == "hermes"
        assert profile["implement"].agent == "shannon"
        assert profile["implement"].model == "openrouter/hermes-3-70b"
        assert profile["execute"].agent == "shannon"


def test_packaged_openai_profile_uses_luna_adjudicator_and_sol_workers() -> None:
    """Guard the shipped profile, not the synthetic profile fixture above."""
    set_profile_override_dir(None)
    profile = load_profile("openai")

    assert profile["classify"] == AgentSpecShape(
        agent="codex", model="gpt-5.6-luna", effort="medium"
    )
    for stage in ("research", "implement", "reply"):
        assert profile[stage] == AgentSpecShape(
            agent="codex", model="gpt-5.6-sol", effort="medium"
        )
    # execute (two-step) follows the implement family in the shipped profile.
    assert profile["execute"] == AgentSpecShape(
        agent="codex", model="gpt-5.6-sol", effort="medium"
    )


def test_packaged_profiles_declare_explicit_execute_stage() -> None:
    """Every shipped profile declares its own ``execute`` spec (B05)."""
    set_profile_override_dir(None)
    for name in ("default", "openai", "openrouter", "anthropic", "opensource"):
        profile = load_profile(name)
        assert "execute" in profile, f"shipped profile {name!r} lacks an execute stage"
        execute = profile["execute"]
        implement = profile["implement"]
        assert execute.agent == implement.agent, f"{name}: execute agent != implement agent"
        assert execute.model == implement.model, f"{name}: execute model != implement model"


def test_packaged_openrouter_profile_preserves_explicit_provider_route() -> None:
    set_profile_override_dir(None)
    profile = load_profile("openrouter")

    assert profile["classify"] == AgentSpecShape(
        agent="openrouter",
        model="openrouter:deepseek/deepseek-v4-flash",
        effort="low",
    )
    assert profile["implement"] == AgentSpecShape(
        agent="openrouter",
        model="openrouter:deepseek/deepseek-v4-pro",
        effort="low",
    )

    def test_all_profiles_have_required_plus_optional_stages(self, profile_dir: Path) -> None:
        for name in ("default", "openai", "anthropic", "opensource"):
            profile = load_profile(name)
            assert _stage_names(profile) == ALLOWED_STAGES, (
                f"{name} has {_stage_names(profile)}; expected {ALLOWED_STAGES}"
            )

    def test_all_profiles_have_valid_effort_values(self, profile_dir: Path) -> None:
        for name in ("default", "openai", "anthropic", "opensource"):
            profile = load_profile(name)
            for stage, spec in profile.items():
                assert spec.effort in ("low", "medium", "high"), (
                    f"{name}/{stage} effort={spec.effort!r}"
                )


# ── load_all_profiles ────────────────────────────────────────────────────────


class TestLoadAllProfiles:
    """Tests for ``load_all_profiles()``."""

    def test_loads_all_four_canonical_profiles(self, profile_dir: Path) -> None:
        all_profiles = load_all_profiles()
        assert set(all_profiles.keys()) == {"default", "openai", "anthropic", "opensource"}

    def test_every_profile_maps_all_stages(self, profile_dir: Path) -> None:
        all_profiles = load_all_profiles()
        for name, profile in all_profiles.items():
            assert REQUIRED_STAGES <= _stage_names(profile) <= ALLOWED_STAGES, (
                f"{name} stages: {_stage_names(profile)}; "
                f"required {REQUIRED_STAGES} ⊆ stages ⊆ {ALLOWED_STAGES}"
            )


# ── validation (error paths) ─────────────────────────────────────────────────


class TestValidationErrors:
    """Tests for profile validation error paths."""

    def test_missing_stage_raises_typed_error(self, profile_dir: Path) -> None:
        _write_toml(
            profile_dir,
            "bad_missing",
            """
            [classify]
            agent = "hermes"
            model = "d"
            [research]
            agent = "hermes"
            model = "d"
            [implement]
            agent = "hermes"
            model = "d"
            # reply missing
            """,
        )
        with pytest.raises(MissingProfileStageError, match="missing required stages"):
            load_profile("bad_missing")

    def test_extra_stage_raises(self, profile_dir: Path) -> None:
        _write_toml(
            profile_dir,
            "bad_extra",
            _BASE_PROFILE
            + """
            [extra_stage]
            agent = "hermes"
            model = "d"
            """,
        )
        with pytest.raises(ValueError, match="unknown stages"):
            load_profile("bad_extra")

    def test_unknown_agent_raises(self, profile_dir: Path) -> None:
        _write_toml(
            profile_dir,
            "bad_agent",
            _BASE_PROFILE.replace('"hermes"', '"gpt-5-robot"'),
        )
        with pytest.raises(ValueError, match="not a known agent"):
            load_profile("bad_agent")

    def test_missing_model_field_raises(self, profile_dir: Path) -> None:
        _write_toml(
            profile_dir,
            "bad_no_model",
            """
            [classify]
            agent = "hermes"

            [research]
            agent = "hermes"
            model = "d"

            [implement]
            agent = "hermes"
            model = "d"

            [reply]
            agent = "hermes"
            model = "d"
            """,
        )
        with pytest.raises(ValueError, match="non-empty string 'model'"):
            load_profile("bad_no_model")

    def test_missing_agent_field_raises(self, profile_dir: Path) -> None:
        _write_toml(
            profile_dir,
            "bad_no_agent",
            """
            [classify]
            model = "d"

            [research]
            agent = "hermes"
            model = "d"

            [implement]
            agent = "hermes"
            model = "d"

            [reply]
            agent = "hermes"
            model = "d"
            """,
        )
        with pytest.raises(ValueError, match="non-empty string 'agent'"):
            load_profile("bad_no_agent")

    def test_missing_profile_file_raises(self, profile_dir: Path) -> None:
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            load_profile("nonexistent")

    def test_execute_stage_is_optional_and_never_synthesized(self, profile_dir: Path) -> None:
        """A profile without ``execute`` loads fine and never gets one
        synthesized from ``implement`` (two-step resolves it explicitly)."""
        _write_toml(
            profile_dir,
            "no_execute",
            _BASE_PROFILE.replace(
                '[execute]\nagent = "codex"\nmodel = "gpt-5.4"\neffort = "high"\n\n', ""
            ),
        )
        profile = load_profile("no_execute")
        assert "execute" not in profile
        assert _stage_names(profile) == REQUIRED_STAGES
        # Implement remains the four-phase implement spec — no alias leak.
        assert profile["implement"].agent == "codex"

    def test_execute_only_extra_stage_is_allowed(self, profile_dir: Path) -> None:
        """``execute`` is the one permitted extra stage."""
        profile = load_profile("default")
        assert "execute" in profile
        assert _stage_names(profile) - REQUIRED_STAGES == {"execute"}

    def test_extra_stage_not_in_allowed_raises(self, profile_dir: Path) -> None:
        """A second extra stage beyond ``execute`` is still rejected."""
        _write_toml(
            profile_dir,
            "bad_two_extras",
            _BASE_PROFILE
            + """
            [extra_stage]
            agent = "hermes"
            model = "d"
            """,
        )
        with pytest.raises(ValueError, match="unknown stages"):
            load_profile("bad_two_extras")

    def test_empty_effort_defaults_to_low(self, profile_dir: Path) -> None:
        _write_toml(
            profile_dir,
            "empty_effort",
            _BASE_PROFILE.replace('effort = "low"', 'effort = ""'),
        )
        profile = load_profile("empty_effort")
        assert profile["classify"].effort == "low"


# ── test path override ───────────────────────────────────────────────────────


class TestOverrideDir:
    """Tests for ``set_profile_override_dir()``."""

    def test_override_dir_is_respected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dir_path = Path(tmp)
            _write_toml(dir_path, "custom", _BASE_PROFILE)
            set_profile_override_dir(dir_path)
            try:
                profile = load_profile("custom")
                assert profile["classify"].agent == "hermes"
            finally:
                set_profile_override_dir(None)

    def test_none_clears_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dir_path = Path(tmp)
            _write_toml(dir_path, "custom", _BASE_PROFILE)
            set_profile_override_dir(dir_path)
            set_profile_override_dir(None)
            # After clearing, loading without a real Arnold package raises
            # because the default importlib.resources path won't work.
            # We just verify the override was cleared (no lingering dir).
            from vibecomfy.executor import profiles

            assert profiles._profile_override_dir is None


# ── nested TOML convention ───────────────────────────────────────────────────


class TestNestedToml:
    """Arnold convention sometimes nests stages under a top-level key."""

    def test_nested_profile_is_unwrapped(self, profile_dir: Path) -> None:
        _write_toml(
            profile_dir,
            "nested",
            """
            [profile]
            [profile.classify]
            agent = "hermes"
            model = "openrouter:deepseek/deepseek-v4-flash"
            effort = "low"
            [profile.research]
            agent = "hermes"
            model = "openrouter:deepseek/deepseek-v4-pro"
            effort = "medium"
            [profile.implement]
            agent = "codex"
            model = "gpt-5.4"
            effort = "high"
            [profile.reply]
            agent = "hermes"
            model = "openrouter:deepseek/deepseek-v4-pro"
            effort = "low"
            """,
        )
        profile = load_profile("nested")
        assert _stage_names(profile) == DECLARED_STAGES
        assert profile["classify"].agent == "hermes"
        assert profile["implement"].agent == "codex"


# ── compact string specs ─────────────────────────────────────────────────────


class TestCompactStringSpecs:
    """Profiles may specify stages as compact ``agent:model[:effort]`` strings."""

    def test_openrouter_deepseek_model_parses_correctly(self, profile_dir: Path) -> None:
        _write_toml(
            profile_dir,
            "compact_default",
            """
            [profiles.compact_default]
            classify   = "hermes:openrouter:deepseek/deepseek-v4-flash"
            research   = "hermes:openrouter:deepseek/deepseek-v4-pro"
            implement  = "hermes:openrouter:deepseek/deepseek-v4-pro"
            reply      = "hermes:openrouter:deepseek/deepseek-v4-pro"
            """,
        )
        profile = load_profile("compact_default")
        assert profile["classify"].agent == "hermes"
        assert profile["classify"].model == "openrouter:deepseek/deepseek-v4-flash"
        assert profile["classify"].effort == "low"
        assert profile["implement"].model == "openrouter:deepseek/deepseek-v4-pro"

    def test_openrouter_colon_model_parses_correctly(self, profile_dir: Path) -> None:
        _write_toml(
            profile_dir,
            "compact_os",
            """
            [profiles.compact_os]
            classify   = "hermes:openrouter:deepseek/deepseek-v4-flash"
            research   = "hermes:openrouter:moonshotai/kimi-k2.7-code"
            implement  = "hermes:openrouter:moonshotai/kimi-k2.7-code"
            reply      = "hermes:openrouter:deepseek/deepseek-v4-pro"
            """,
        )
        profile = load_profile("compact_os")
        assert profile["classify"].model == "openrouter:deepseek/deepseek-v4-flash"
        assert profile["research"].model == "openrouter:moonshotai/kimi-k2.7-code"

    def test_effort_token_extracted_from_end(self, profile_dir: Path) -> None:
        _write_toml(
            profile_dir,
            "compact_effort",
            """
            [profiles.compact_effort]
            classify   = "codex:gpt-5.4:low"
            research   = "codex:gpt-5.5:medium"
            implement  = "codex:gpt-5.5:medium"
            reply      = "codex:gpt-5.4:low"
            """,
        )
        profile = load_profile("compact_effort")
        assert profile["classify"].model == "gpt-5.4"
        assert profile["classify"].effort == "low"
        assert profile["research"].model == "gpt-5.5"
        assert profile["research"].effort == "medium"

    def test_unknown_agent_in_compact_spec_raises(self, profile_dir: Path) -> None:
        _write_toml(
            profile_dir,
            "compact_bad_agent",
            """
            [profiles.compact_bad_agent]
            classify   = "gpt-5:some-model"
            research   = "hermes:openrouter:deepseek/deepseek-v4-pro"
            implement  = "hermes:openrouter:deepseek/deepseek-v4-pro"
            reply      = "hermes:openrouter:deepseek/deepseek-v4-pro"
            """,
        )
        with pytest.raises(ValueError, match="not a known agent"):
            load_profile("compact_bad_agent")

    def test_missing_model_in_compact_spec_raises(self, profile_dir: Path) -> None:
        _write_toml(
            profile_dir,
            "compact_no_model",
            """
            [profiles.compact_no_model]
            classify   = "hermes"
            research   = "hermes:openrouter:deepseek/deepseek-v4-pro"
            implement  = "hermes:openrouter:deepseek/deepseek-v4-pro"
            reply      = "hermes:openrouter:deepseek/deepseek-v4-pro"
            """,
        )
        with pytest.raises(ValueError, match="must include a model"):
            load_profile("compact_no_model")


# ── spec shape serves as mapping bridge ──────────────────────────────────────


class TestSpecShapeMapping:
    """Verify that ``AgentSpecShape`` fields carry the data expected by
    the provider seam (T3)."""

    def test_all_resolved_specs_have_route_agent_field(self, profile_dir: Path) -> None:
        for name in ("default", "openai", "anthropic", "opensource"):
            profile = load_profile(name)
            for stage, spec in profile.items():
                assert isinstance(spec.agent, str) and spec.agent, (
                    f"{name}/{stage} agent is empty"
                )
                assert spec.agent in ("hermes", "codex", "claude", "shannon"), (
                    f"{name}/{stage} agent={spec.agent!r} not in known set"
                )

    def test_all_resolved_specs_have_non_empty_model(self, profile_dir: Path) -> None:
        for name in ("default", "openai", "anthropic", "opensource"):
            profile = load_profile(name)
            for stage, spec in profile.items():
                assert isinstance(spec.model, str) and spec.model, (
                    f"{name}/{stage} model is empty"
                )
