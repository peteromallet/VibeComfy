"""No-GPU canonical user-path checks for T21's pinned H3 workflow."""
from __future__ import annotations

from pathlib import Path

from vibecomfy.cli_loader import load_bundle
from vibecomfy.security.agent_generated_loader import load_agent_generated_scratchpad
from vibecomfy.security.provenance import Provenance


FIXTURE = Path(__file__).parent / "fixtures" / "h3_canonical.py"


def test_h3_build_reload_compile_api_is_stable() -> None:
    first = load_agent_generated_scratchpad(FIXTURE)
    second = load_agent_generated_scratchpad(FIXTURE)
    assert first.id == second.id
    assert first.semantic_digest() == second.semantic_digest()
    assert first.compile("api") == second.compile("api")


def test_h3_fixture_is_canonical_public_build_source() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    assert "def build()" in text
    assert "._node" not in text
    assert ".add(" not in text
    assert "raw_call(" in text  # unresolved H3 classes remain local and explicit
    workflow = load_agent_generated_scratchpad(FIXTURE)
    assert workflow.metadata.get("h3_source_repository") == "seitanism/ComfyUI-H3-Motion-Context-MultiRef"
    assert workflow.metadata.get("h3_source_commit") == "2ed4b27e5e262a996ad2670ac6d2fd2e505cf3a3"


def test_h3_load_bundle_public_path_matches_direct_build() -> None:
    direct = load_agent_generated_scratchpad(FIXTURE)
    bundle = load_bundle(FIXTURE, trust=Provenance.USER_CONFIRMED)
    assert bundle.workflow.semantic_digest() == direct.semantic_digest()
    assert bundle.workflow.compile("api") == direct.compile("api")
