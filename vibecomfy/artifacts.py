from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from vibecomfy.workflow import VibeWorkflow

if TYPE_CHECKING:
    # Importing `vibecomfy.runtime` eagerly pulls in `vibecomfy.runtime.client`,
    # `vibecomfy.runtime.server`, and (transitively) `vibecomfy.comfy_command`,
    # which breaks the cheap-import contract for `vibecomfy.testing`. The
    # symbol is only used as a return-type annotation thanks to
    # `from __future__ import annotations`, so a TYPE_CHECKING-guarded import
    # is sufficient and stays out of `sys.modules` at runtime.
    from vibecomfy.runtime import RunResult


ArtifactKind = Literal["image", "video", "audio", "latent", "mask"]


@dataclass(frozen=True, slots=True)
class Artifact:
    workflow: VibeWorkflow
    node_id: str
    output_slot: int
    kind: ArtifactKind
    metadata: dict[str, Any] = field(default_factory=dict)

    def preview_workflow(self) -> VibeWorkflow:
        return self.workflow

    def compile(self) -> dict[str, Any]:
        return self.workflow.compile("api")

    def run(self, *, runtime: str = "embedded", **kwargs: Any) -> RunResult:
        del kwargs
        if runtime in {"embedded", "server", "external"}:
            from vibecomfy.workflow_bundle import WorkflowBundleError

            raise WorkflowBundleError(
                "Artifact.run cannot execute a bare workflow; execution requires finalizing and approving a candidate "
                "into an ApprovedProjectionRecord bound to a WorkflowBundle. Next: call "
                "run_embedded_sync(record, bundle) or run_sync(record, bundle, server_url=...). For raw or legacy sources, run "
                "`vibecomfy port check <source> --json` then `vibecomfy port convert <source> --out "
                "out/scratchpads/<name>.py`."
            )
        raise ValueError(f"Unknown artifact runtime: {runtime}")


@dataclass(frozen=True, slots=True)
class Image(Artifact):
    kind: Literal["image"] = "image"


@dataclass(frozen=True, slots=True)
class Video(Artifact):
    kind: Literal["video"] = "video"


@dataclass(frozen=True, slots=True)
class Audio(Artifact):
    kind: Literal["audio"] = "audio"


@dataclass(frozen=True, slots=True)
class Latent(Artifact):
    kind: Literal["latent"] = "latent"


@dataclass(frozen=True, slots=True)
class Mask(Artifact):
    kind: Literal["mask"] = "mask"


__all__ = ["Artifact", "ArtifactKind", "Image", "Video", "Audio", "Latent", "Mask"]
