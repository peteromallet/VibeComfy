from __future__ import annotations

import json
from pathlib import Path

from scripts import runpod_route_validate


def test_resolve_z_image_turbo_route_template() -> None:
    spec = runpod_route_validate.resolve_route_template(route_key="z_image_turbo")

    assert spec.route_key == "z_image_turbo"
    assert spec.task_type == "z_image_turbo"
    assert spec.support_state == "vibecomfy_supported"
    assert spec.selected_template_id == "image/z_image"
    assert spec.fixture_path.name == "z_image_turbo.json"


def test_remote_script_records_route_specific_manifest() -> None:
    spec = runpod_route_validate.resolve_route_template(route_key="z_image_turbo")
    fixture = json.loads(spec.fixture_path.read_text(encoding="utf-8"))
    script = runpod_route_validate.build_remote_script(spec, fixture, Path("out/reigh_route_validation/z_image_turbo"))

    assert "image/z_image" in script
    assert "z_image_turbo" in script
    assert "route_manifest.json" in script
    assert "result.json" in script
    assert "--prompt" in script
    assert "--seed" in script
    assert "--steps" in script


def test_dry_run_outputs_route_manifest(capsys) -> None:
    result = runpod_route_validate.main(["--dry-run", "--route-key", "z_image_turbo"])

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["route"]["route_key"] == "z_image_turbo"
    assert payload["manifest"]["selected_template_id"] == "image/z_image"
    assert payload["manifest"]["fixture_params"]["resolution"] == "1024x1024"


def test_missing_runpod_api_key_fails_before_launch(monkeypatch, capsys) -> None:
    calls = []

    async def fake_run_pod_detached(*_args, **_kwargs):
        calls.append("called")
        return 0

    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    monkeypatch.setattr(runpod_route_validate, "DEFAULT_ENV_FILES", ())
    monkeypatch.setattr(runpod_route_validate, "run_pod_detached", fake_run_pod_detached)

    result = runpod_route_validate.main(["--route-key", "z_image_turbo"])

    assert result == 2
    assert calls == []
    assert "RUNPOD_API_KEY" in capsys.readouterr().out


def test_default_env_files_load_runpod_key_without_overriding_existing(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "RUNPOD_API_KEY='from-file'\nSUPABASE_URL=https://example.supabase.co\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("RUNPOD_API_KEY", "already-set")
    monkeypatch.delenv("SUPABASE_URL", raising=False)

    runpod_route_validate.load_default_env_files((env_file,))

    assert runpod_route_validate.os.environ["RUNPOD_API_KEY"] == "already-set"
    assert runpod_route_validate.os.environ["SUPABASE_URL"] == "https://example.supabase.co"


def test_unknown_route_requires_template_and_fixture(tmp_path: Path, capsys) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps({"route_key": "custom_route", "task_type": "custom_task", "params": {"prompt": "x"}}),
        encoding="utf-8",
    )

    missing = runpod_route_validate.main(["--dry-run", "--route-key", "custom_route"])
    assert missing == 2
    capsys.readouterr()

    ok = runpod_route_validate.main(
        [
            "--dry-run",
            "--route-key",
            "custom_route",
            "--selected-template-id",
            "image/custom",
            "--input-fixture",
            str(fixture),
        ]
    )
    assert ok == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["route"]["selected_template_id"] == "image/custom"
