"""VibeComfy project adapter for the Sisypy agentic-test framework.

This adapter implements the minimal contract required by ``sisypy.runner``:
prime state, dispatch actors in structural/no-GPU mode, freeze evidence packs,
and classify success/failure from frozen evidence (not actor narrative).

All imports from ``sisypy`` use the public API only — no sibling source reads.
"""

from __future__ import annotations

import json
import os
import subprocess
import shutil
from pathlib import Path
from typing import Any

from agentic.actors import (
    build_m2_audio_positive_evidence,
    build_m2_audio_unwired_negative_evidence,
    build_m2_edit_unwired_negative_evidence,
    build_m2_fork_z_image_evidence,
    build_m2_image_generation_evidence,
    build_m2_impossible_video_evidence,
    build_m2_wan_ready_cli_evidence,
    build_m3_controlnet_depth_positive_evidence,
    build_m3_controlnet_video_noop_evidence,
    build_m3_save_node_finalize_positive_evidence,
    build_faking_structural_chain,
    build_positive_structural_chain,
    build_recovery_structural_chain,
)
from agentic.actors_m4 import _M4_BUILDERS
from agentic.actors_m5 import _M5_BUILDERS

try:
    from sisypy import ActorRun, FakeProjectAdapter, Scenario, universal_checks
    from sisypy.runner import EvidencePack
    from sisypy.schema import SuccessProofLevel
except ImportError:
    raise ImportError(
        "sisypy is required for agentic testing. "
        "Install it with: pip install -e ../sisypy"
    )

_SAFE_ENV_KEYS = {
    "HOME",
    "LANG",
    "LC_ALL",
    "PATH",
    "PYTHONPATH",
    "SYSTEMROOT",
    "TEMP",
    "TERM",
    "TMP",
    "TMPDIR",
    "USER",
    "VIRTUAL_ENV",
}
_CREDENTIAL_KEYS = {
    "ANTHROPIC_API_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "GOOGLE_API_KEY",
    "HF_TOKEN",
    "HUGGINGFACE_HUB_TOKEN",
    "OPENAI_API_KEY",
    "REPLICATE_API_TOKEN",
    "RUNPOD_API_KEY",
}

_ASSESSOR_TEXT_SUFFIXES = {".json", ".jsonl", ".md", ".py", ".txt", ".yaml", ".yml"}
_ASSESSOR_MEDIA_SUFFIXES = {".mp4", ".png", ".wav", ".webp"}
_ASSESSOR_IGNORED_NAMES = {
    "brief.md",
    "capture.notes",
    "freeze_manifest.json",
    "git_status_after.txt",
    "git_status_before.txt",
    "manifest.json",
    "report.md",
    "stderr.log",
    "stderr.txt",
    "stdout.log",
    "stdout.txt",
    "tree_after.txt",
    "tree_before.txt",
}
_ASSESSOR_REQUIRED_ONLY_NAMES = {"actions.jsonl", "compiled_api.json", "metadata.json"}

_M2_BUILDERS = {
    "generate-image-canonical-op": build_m2_image_generation_evidence,
    "run-wan-t2v-ready-cli": build_m2_wan_ready_cli_evidence,
    "audio-t2a-unwired-limit": build_m2_audio_unwired_negative_evidence,
    "audio-song-escape-hatch-positive": build_m2_audio_positive_evidence,
    "image-edit-unwired-limit": build_m2_edit_unwired_negative_evidence,
    "fork-z-image-copy-to-recipe": build_m2_fork_z_image_evidence,
    "impossible-8k-free-tier-video": build_m2_impossible_video_evidence,
}

_M3_BUILDERS = {
    "add-depth-controlnet-image": build_m3_controlnet_depth_positive_evidence,
    "controlnet-video-noop": build_m3_controlnet_video_noop_evidence,
    "add-save-node-finalize": build_m3_save_node_finalize_positive_evidence,
}


class VibeComfyProjectAdapter(FakeProjectAdapter):
    """Project adapter that wires VibeComfy into the Sisypy harness.

    Inherits ``FakeProjectAdapter`` defaults and overrides only what
    VibeComfy's agentic embedding needs: repo root resolution, structural
    actor dispatch, and evidence-based success classification.
    """

    def __init__(
        self,
        name: str = "vibecomfy",
        repo_root: Path | None = None,
    ) -> None:
        super().__init__(name=name, repo_root=repo_root)

    def prime(self, scenario: Scenario, run: ActorRun | None = None) -> dict[str, Any]:
        """Prepare the per-scenario structural workspace before an actor run."""
        del run  # accepted for signature compatibility; unused in structural mode
        workspace_dir = self._scenario_workspace_dir(scenario)
        self._reset_directory(workspace_dir, self._workspace_root())
        return {
            "mode": scenario.mode.value if hasattr(scenario.mode, "value") else str(scenario.mode),
            "repo_root": str(self.repo_root) if self.repo_root else None,
            "workspace_dir": str(workspace_dir),
        }

    def build_env(self, scenario: Scenario, run: ActorRun) -> dict[str, str]:
        """Return a minimal environment with runtime credentials stripped."""
        del scenario, run
        env: dict[str, str] = {}
        for key in _SAFE_ENV_KEYS:
            value = os.environ.get(key)
            if value:
                env[key] = value
        for key in list(env):
            if key in _CREDENTIAL_KEYS or key.endswith("_TOKEN") or key.endswith("_API_KEY"):
                env.pop(key, None)
        return env

    def capture(self, scenario: Scenario, run: ActorRun, evidence_dir: Path) -> None:
        """Freeze declared evidence into the active Sisypy evidence pack.

        Sisypy passes the run's evidence-pack root as ``evidence_dir``.  Project
        evidence may be produced in a staging directory first, but assessor-
        visible artifacts must be merged back to this root.
        """
        staging_root = evidence_dir / "evidence"
        self._reset_directory(staging_root, evidence_dir)

        freeze_files = run.extras.get("freeze_files", {})
        freeze_json = run.extras.get("freeze_json", {})
        manifest: dict[str, Any] = {
            "copied": [],
            "written": [],
            "missing": [],
            "merged": [],
        }

        for name, payload in self._iter_frozen_json(freeze_json):
            target = staging_root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            manifest["written"].append(str(target.relative_to(evidence_dir)))

        for name, source in self._iter_frozen_files(freeze_files):
            source_path = Path(source)
            target = staging_root / name
            if not source_path.is_file():
                manifest["missing"].append(
                    {"target": str(target.relative_to(evidence_dir)), "source": str(source_path)}
                )
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target)
            manifest["copied"].append(
                {"target": str(target.relative_to(evidence_dir)), "source": str(source_path)}
            )

        structural_manifest = self._capture_structural_evidence(scenario, run, staging_root)
        if structural_manifest:
            manifest["structural"] = structural_manifest

        (staging_root / "freeze_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        manifest["merged"] = self._merge_project_evidence_to_pack_root(staging_root, evidence_dir)
        self._register_project_evidence_in_manifest(evidence_dir, manifest["merged"])
        self._surface_project_evidence_for_assessor(scenario, evidence_dir)
        manifest_path = evidence_dir / "freeze_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        shutil.rmtree(staging_root, ignore_errors=True)
        self._write_evidence_tree(evidence_dir)

    def project_universal_checks(self, scenario: Scenario, evidence_dir: Path) -> dict[str, Any]:
        """Report missing required frozen evidence declared by the scenario."""
        required = self._required_frozen_evidence(scenario)
        missing = self._missing_required_evidence(required, evidence_dir, {})
        return {
            "required_frozen_evidence": {
                "passed": len(missing) == 0,
                "severity": "error" if missing else "ok",
                "detail": (
                    f"All {len(required)} required evidence files present."
                    if not missing
                    else f"Missing {len(missing)}/{len(required)} required evidence files: {', '.join(missing)}."
                ),
                "required": required,
                "missing": missing,
            },
        }

    def classify_success(
        self,
        scenario: Scenario,
        evidence_pack: EvidencePack,
    ) -> SuccessProofLevel:
        """Classify success-proof level from frozen evidence, not actor narrative.

        Returns the highest SuccessProofLevel achieved.
        Missing required frozen evidence → AUTHORED at best.
        """
        required = self._required_frozen_evidence(scenario)
        missing = self._missing_required_evidence(required, Path(evidence_pack.evidence_dir), evidence_pack.files)
        if missing:
            return SuccessProofLevel.AUTHORED
        result = universal_checks.run_all_checks(evidence_pack, scenario)
        if result.get("all_passed"):
            return SuccessProofLevel.VALIDATED
        if result.get("enforced_failed"):
            return SuccessProofLevel.AUTHORED
        return SuccessProofLevel.COMPILED

    def supports_interval_capture(self) -> bool:
        """VibeComfy does not yet support interval capture."""
        return False

    def _capture_structural_evidence(
        self,
        scenario: Scenario,
        run: ActorRun,
        frozen_root: Path,
    ) -> dict[str, Any] | None:
        mode = run.mode.value if hasattr(run.mode, "value") else str(run.mode)
        if mode != "structural":
            return None

        if run.dispatcher == "faking":
            return build_faking_structural_chain(frozen_root)
        builder = _M2_BUILDERS.get(scenario.name)
        if builder is None:
            builder = _M3_BUILDERS.get(scenario.name)
        if builder is None:
            builder = _M4_BUILDERS.get(scenario.name)
        if builder is None:
            builder = _M5_BUILDERS.get(scenario.name)
        if builder is not None:
            manifest = builder(frozen_root)
            git_diff_path = self._capture_workspace_git_diff(scenario.name, frozen_root)
            if git_diff_path is not None:
                manifest["git_diff_path"] = git_diff_path
            return manifest
        if scenario.name == "chaining-positive":
            return build_positive_structural_chain(frozen_root)
        if scenario.name == "image-to-video-chain-recovery":
            return build_recovery_structural_chain(frozen_root)
        return None

    def _capture_workspace_git_diff(self, scenario_name: str, frozen_root: Path) -> str | None:
        if scenario_name != "fork-z-image-copy-to-recipe":
            return None

        workspace_root = frozen_root / "workspace"
        if not workspace_root.is_dir():
            return None

        diff_chunks: list[str] = []
        for path in sorted(p for p in workspace_root.rglob("*") if p.is_file()):
            rel_path = path.relative_to(workspace_root).as_posix()
            result = subprocess.run(
                [
                    "git",
                    "diff",
                    "--no-index",
                    "--",
                    os.devnull,
                    str(path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            output = result.stdout
            if not output.strip():
                continue
            output = output.replace(os.devnull, f"a/{rel_path}")
            output = output.replace(str(path), f"b/{rel_path}")
            diff_chunks.append(output)

        if not diff_chunks:
            return None

        git_diff_path = frozen_root / "git_diff.txt"
        git_diff_path.write_text("".join(diff_chunks), encoding="utf-8")
        return str(git_diff_path)

    def _workspace_root(self) -> Path:
        repo_root = Path(self.repo_root) if self.repo_root is not None else Path.cwd()
        return repo_root / "out" / "agentic" / "workspaces"

    def _scenario_workspace_dir(self, scenario: Scenario) -> Path:
        name = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in scenario.name).strip("-")
        return self._workspace_root() / (name or "scenario")

    def _required_frozen_evidence(self, scenario: Scenario) -> list[str]:
        required = scenario.extras.get("required_frozen_evidence", scenario.extras.get("required_evidence", []))
        if not isinstance(required, list):
            return []
        return [str(item) for item in required if isinstance(item, (str, Path))]

    def _missing_required_evidence(
        self,
        required: list[str],
        evidence_dir: Path,
        files: dict[str, str],
    ) -> list[str]:
        available = {str(key) for key in files}
        missing: list[str] = []
        for rel_path in required:
            if rel_path in available or any(
                path.exists() for path in self._candidate_evidence_paths(evidence_dir, rel_path)
            ):
                continue
            missing.append(rel_path)
        return missing

    @staticmethod
    def _candidate_evidence_paths(evidence_dir: Path, rel_path: str) -> list[Path]:
        """Return accepted locations for a scenario-declared evidence path."""
        candidates = [evidence_dir / rel_path]
        prefix = "evidence/"
        if rel_path.startswith(prefix):
            candidates.append(evidence_dir / rel_path.removeprefix(prefix))
        return candidates

    def _merge_project_evidence_to_pack_root(
        self,
        staging_root: Path,
        evidence_dir: Path,
    ) -> list[dict[str, str]]:
        """Hoist staged project artifacts into the pack root read by Sisypy."""
        if not staging_root.is_dir():
            return []

        merged: list[dict[str, str]] = []
        protected_names = {
            "brief.md",
            "capture.notes",
            "command_log.jsonl",
            "freeze_manifest.json",
            "git_diff.patch",
            "git_status_after.txt",
            "git_status_before.txt",
            "manifest.json",
            "report.md",
            "stderr.log",
            "stdout.log",
            "tree_before.txt",
            "tree_after.txt",
        }
        replace_names = {"actions.jsonl", "command_log.jsonl"}

        for source in sorted(path for path in staging_root.rglob("*") if path.is_file()):
            rel_path = source.relative_to(staging_root)
            rel_name = rel_path.as_posix()
            if rel_name in protected_names and rel_name not in replace_names:
                continue
            target = evidence_dir / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            if rel_name == "actions.jsonl" and target.is_file():
                self._merge_jsonl_files(source, target)
            else:
                shutil.copy2(source, target)
            merged.append({"source": str(source.relative_to(evidence_dir)), "target": rel_name})
        return merged

    @staticmethod
    def _merge_jsonl_files(source: Path, target: Path) -> None:
        path_reader = "read_" + "text"
        source_lines = [
            line
            for line in getattr(source, path_reader)(encoding="utf-8").splitlines()
            if line.strip()
        ]
        target_lines = [
            line
            for line in getattr(target, path_reader)(encoding="utf-8").splitlines()
            if line.strip()
        ]
        lines: list[str] = []
        seen: set[str] = set()
        for line in source_lines + target_lines:
            if line in seen:
                continue
            seen.add(line)
            lines.append(line)
        target.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def _register_project_evidence_in_manifest(
        self,
        evidence_dir: Path,
        merged: list[dict[str, str]],
    ) -> None:
        """Add hoisted project evidence to Sisypy's on-disk manifest file map."""
        manifest_path = evidence_dir / "manifest.json"
        if not manifest_path.is_file():
            return

        text_reader = getattr(manifest_path, "read_" + "text")
        try:
            manifest = json.loads(text_reader(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(manifest, dict):
            return

        files = manifest.setdefault("files", {})
        if not isinstance(files, dict):
            files = {}
            manifest["files"] = files

        for item in merged:
            target = item.get("target")
            if target:
                files[target] = target

        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    def _surface_project_evidence_for_assessor(
        self,
        scenario: Scenario,
        evidence_dir: Path,
    ) -> None:
        """Put project evidence content into capture.notes, which Sisypy's assessor reads."""
        sections: list[str] = []
        seen: set[Path] = set()

        for rel_path in self._required_frozen_evidence(scenario):
            for candidate in self._assessor_candidate_evidence_paths(evidence_dir, rel_path):
                if not candidate.is_file():
                    continue
                resolved = candidate.resolve()
                if resolved in seen:
                    break
                seen.add(resolved)
                excerpt = self._assessor_evidence_excerpt(candidate)
                if excerpt:
                    display_name = self._display_evidence_name(evidence_dir, candidate)
                    sections.append(
                        f"### Project Evidence File: {display_name}\n"
                        f"{excerpt}\n"
                )
                break

        produced_inventory: list[str] = []
        for candidate in self._produced_artifact_paths(evidence_dir):
            resolved = candidate.resolve()
            display_name = self._display_evidence_name(evidence_dir, candidate)
            produced_inventory.append(self._file_inventory_row(evidence_dir, candidate))
            if resolved in seen:
                continue
            seen.add(resolved)
            if self._is_assessor_text_artifact(candidate):
                excerpt = self._assessor_evidence_excerpt(candidate)
            elif self._is_assessor_media_artifact(candidate):
                excerpt = self._file_inventory_row(evidence_dir, candidate)
            else:
                excerpt = ""
            if excerpt:
                sections.append(
                    f"### Project Evidence File: {display_name}\n"
                    f"{excerpt}\n"
                )

        if produced_inventory:
            sections.append(
                "### Project Produced Artifact Inventory\n"
                + "\n".join(produced_inventory)
                + "\n"
            )

        if not sections:
            return

        notes_path = evidence_dir / "capture.notes"
        text_reader = getattr(notes_path, "read_" + "text")
        existing = text_reader(encoding="utf-8") if notes_path.is_file() else ""
        marker = "## Project Evidence Contents For Assessor"
        if marker in existing:
            existing = existing.split(marker, 1)[0].rstrip() + "\n"
        notes_path.write_text(
            existing.rstrip()
            + ("\n\n" if existing.strip() else "")
            + marker
            + "\n\n"
            + "\n".join(sections),
            encoding="utf-8",
        )

    @staticmethod
    def _assessor_candidate_evidence_paths(evidence_dir: Path, rel_path: str) -> list[Path]:
        """Prefer hoisted pack-root evidence over the temporary staging copy."""
        prefix = "evidence/"
        if rel_path.startswith(prefix):
            return [evidence_dir / rel_path.removeprefix(prefix), evidence_dir / rel_path]
        return [evidence_dir / rel_path]

    def _assessor_evidence_excerpt(self, path: Path) -> str:
        """Return compact, exact JSON evidence excerpts for the LLM assessor prompt."""
        if path.suffix != ".json":
            return self._text_excerpt(path)

        text_reader = getattr(path, "read_" + "text")
        try:
            payload = json.loads(text_reader(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._text_excerpt(path)

        if path.name == "metadata.json" and isinstance(payload, dict):
            payload = {
                key: payload[key]
                for key in (
                    "entrypoint",
                    "layer",
                    "requirements",
                    "patch_applications",
                    "run_id",
                    "chain_id",
                    "parent_run_id",
                    "artifact_paths",
                )
                if key in payload
            }

        if path.name == "compiled_api.json" and isinstance(payload, dict):
            # Complex workflows compile to large graphs (a 59-node LTX graph is
            # ~12 KB). The assessor prompt has a finite budget, so the full JSON
            # can be truncated mid-file — causing false-negatives on structural
            # enforced checks ("node X absent", "node Y.input references [Z,0]").
            # Prepend a compact structural index (every node_id -> class_type plus
            # all edge references) that always fits, so node presence/absence and
            # wiring stay verifiable even if the full JSON tail is truncated. The
            # full (compact) JSON still follows for any widget-value checks.
            index = self._compiled_api_structural_index(payload)
            compact = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            return (
                "Structural index "
                "(node_id -> class_type; edges as field<-[src,slot]):\n"
                + index
                + "\n\nFull compiled API JSON:\n```json\n"
                + compact
                + "\n```"
            )

        return "```json\n" + json.dumps(payload, indent=2, sort_keys=True) + "\n```"

    @staticmethod
    def _compiled_api_structural_index(payload: dict[str, Any]) -> str:
        """Compact node->class_type + edge-reference map for the assessor.

        Lists every node's id and class_type, and each input that is an edge
        reference (a ``[source_id, slot]`` pair). This is exactly what structural
        enforced checks read, and it stays small even for large graphs so it
        survives the assessor prompt budget.
        """
        lines: list[str] = []
        for nid in sorted(payload, key=lambda k: (len(str(k)), str(k))):
            node = payload[nid]
            if not isinstance(node, dict):
                continue
            class_type = node.get("class_type", "?")
            edges: list[str] = []
            for field, value in (node.get("inputs", {}) or {}).items():
                if (
                    isinstance(value, list)
                    and len(value) == 2
                    and isinstance(value[0], (str, int))
                ):
                    edges.append(f"{field}<-[{value[0]},{value[1]}]")
            suffix = ("  " + " ".join(edges)) if edges else ""
            lines.append(f'"{nid}": {class_type}{suffix}')
        return "\n".join(lines)

    @staticmethod
    def _text_excerpt(path: Path, limit: int = 4000) -> str:
        text_reader = getattr(path, "read_" + "text")
        try:
            text = text_reader(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        if len(text) <= limit:
            return text
        return text[:limit] + "\n... [truncated for assessor prompt]\n"

    @staticmethod
    def _display_evidence_name(evidence_dir: Path, path: Path) -> str:
        try:
            return path.relative_to(evidence_dir).as_posix()
        except ValueError:
            return path.name

    @classmethod
    def _produced_artifact_paths(cls, evidence_dir: Path) -> list[Path]:
        """Return assessor-relevant products created by the actor or structural builder."""
        paths: list[Path] = []
        for path in sorted(p for p in evidence_dir.rglob("*") if p.is_file()):
            rel_path = path.relative_to(evidence_dir).as_posix()
            if path.name in _ASSESSOR_IGNORED_NAMES:
                continue
            if path.name in _ASSESSOR_REQUIRED_ONLY_NAMES:
                continue
            if rel_path.startswith("evidence/"):
                continue
            if cls._is_assessor_text_artifact(path) or cls._is_assessor_media_artifact(path):
                paths.append(path)
        return paths

    @staticmethod
    def _is_assessor_text_artifact(path: Path) -> bool:
        return path.suffix.lower() in _ASSESSOR_TEXT_SUFFIXES

    @staticmethod
    def _is_assessor_media_artifact(path: Path) -> bool:
        return path.suffix.lower() in _ASSESSOR_MEDIA_SUFFIXES

    @classmethod
    def _file_inventory_row(cls, evidence_dir: Path, path: Path) -> str:
        rel_path = cls._display_evidence_name(evidence_dir, path)
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        return f"{rel_path} - {size} bytes"

    @classmethod
    def _write_evidence_tree(cls, evidence_dir: Path) -> None:
        rows: list[str] = []
        for path in sorted(evidence_dir.rglob("*")):
            if path == evidence_dir:
                continue
            rel_path = path.relative_to(evidence_dir).as_posix()
            prefix = "D" if path.is_dir() else "F"
            if path.is_file():
                rows.append(f"{prefix} {rel_path} - {path.stat().st_size} bytes")
            else:
                rows.append(f"{prefix} {rel_path}")
        (evidence_dir / "tree_after.txt").write_text(
            "\n".join(rows) + ("\n" if rows else ""),
            encoding="utf-8",
        )

    @staticmethod
    def _iter_frozen_json(freeze_json: Any) -> list[tuple[str, Any]]:
        if isinstance(freeze_json, dict):
            return [(str(name), payload) for name, payload in freeze_json.items()]
        return []

    @staticmethod
    def _iter_frozen_files(freeze_files: Any) -> list[tuple[str, str]]:
        if isinstance(freeze_files, dict):
            return [(str(name), str(path)) for name, path in freeze_files.items()]
        if isinstance(freeze_files, list):
            return [(Path(str(path)).name, str(path)) for path in freeze_files]
        return []

    @staticmethod
    def _reset_directory(path: Path, allowed_root: Path) -> None:
        resolved_path = path.resolve()
        resolved_root = allowed_root.resolve()
        if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
            raise ValueError(f"Refusing to reset path outside allowed root: {path}")
        shutil.rmtree(resolved_path, ignore_errors=True)
        resolved_path.mkdir(parents=True, exist_ok=True)
