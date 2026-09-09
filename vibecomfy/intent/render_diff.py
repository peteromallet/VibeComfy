"""Structural and rendered-image diff utilities for VibeWorkflow edits.

Supported sampler class registry (SEED_FIELDS):
  KSampler            → seed field, control_after_generate control field
  KSamplerAdvanced    → noise_seed field, add_noise control field
  KSamplerSelect      → noise_seed field, no control field
  RandomNoise         → noise_seed field, control_after_generate control field
    (RandomNoise is the actual seed-bearing node in LTX-2.3 / SamplerCustomAdvanced graphs)

Note: ancestral and SDE samplers (euler_ancestral, dpm2_ancestral, etc.) remain
nondeterministic even when a fixed seed is set because of internal stochasticity in
the diffusion schedule; fixing the seed improves reproducibility but does not
guarantee bit-identical outputs across runs.

pHash default threshold: 8 for hash_size=16.  Distance ≤ threshold ⇒ perceptually equal.

GPU smoke tests (test_render_diff_runpod.py) are marked with the existing `runpod`
marker so they are deselected in CI (pytest -m intent_ci).  The embedded runtime is
exercised under a runpod-marked test for consistency with the rest of the GPU test suite:
the test provisions a pod, which means run_embedded_sync executes on GPU rather than
locally.  Corpus samplers that remain nondeterministic with fixed seeds (ancestral /
SDE variants used in wan_* and ltx_* workflows) are called out in the smoke-test
docstring; callers should widen the threshold for those families.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow

# Maps sampler class_type → (seed_field, control_field | None)
# control_field is set to "fixed" when not None.
SEED_FIELDS: dict[str, tuple[str, str | None]] = {
    "KSampler": ("seed", "control_after_generate"),
    "KSamplerAdvanced": ("noise_seed", "add_noise"),
    "KSamplerSelect": ("noise_seed", None),
    "RandomNoise": ("noise_seed", "control_after_generate"),
}


def fix_seeds_in_ir(wf: "VibeWorkflow", seed: int) -> "VibeWorkflow":
    """Return a clone of *wf* with every sampler seed set to *seed*.

    Walks ``wf.nodes`` by ``class_type``.  For each node whose class is in
    :data:`SEED_FIELDS`, sets the seed field to *seed* and (where defined)
    the control field to ``'fixed'``.

    Raises
    ------
    ValueError
        If no node in the workflow matches any entry in :data:`SEED_FIELDS`.
    """
    import copy as _copy
    from vibecomfy.workflow import VibeWorkflow

    cloned: VibeWorkflow = _copy.deepcopy(wf)
    matched = 0

    for node in cloned.nodes.values():
        entry = SEED_FIELDS.get(node.class_type)
        if entry is None:
            continue
        seed_field, control_field = entry
        node.inputs[seed_field] = seed
        if control_field is not None:
            node.inputs[control_field] = "fixed"
        # A ready workflow may expose the sampler field as a public input.
        # Update the detached descriptor value as well, otherwise projection
        # reapplies its old default and the returned IR does not compile with
        # the requested seed.
        public_updates = {seed_field: seed}
        if control_field is not None:
            public_updates[control_field] = "fixed"
        for public_name, public_input in cloned.inputs.items():
            if str(public_input.node_id) != str(node.id):
                continue
            if public_input.field in public_updates:
                cloned.set_input(public_name, public_updates[public_input.field])
        matched += 1

    if matched == 0:
        raise ValueError(
            f"fix_seeds_in_ir: no sampler node found in workflow "
            f"(nodes: {[n.class_type for n in wf.nodes.values()]})"
        )

    return cloned


@dataclass
class StructuralDiffResult:
    api_sha_pre: str
    api_sha_post: str
    equal: bool


def structural_proxy_diff(pre_wf: "VibeWorkflow", post_wf: "VibeWorkflow") -> StructuralDiffResult:
    """Return SHA-256 hashes of both compiled API dicts and whether they match.

    Compiles each workflow to the ComfyUI API JSON shape, serialises with
    ``sort_keys=True``, and SHA-256-hashes the result.  Returns a
    :class:`RenderDiffReport` with both hashes and an ``equal`` flag.

    Note: this catches structural deltas only (node graph shape, widget values,
    edge topology).  It does not detect differences in rendered image content.
    """
    def _sha(wf: "VibeWorkflow") -> str:
        api_dict = wf.compile("api")
        serialised = json.dumps(api_dict, sort_keys=True)
        return hashlib.sha256(serialised.encode()).hexdigest()

    sha_pre = _sha(pre_wf)
    sha_post = _sha(post_wf)
    return StructuralDiffResult(
        api_sha_pre=sha_pre,
        api_sha_post=sha_post,
        equal=(sha_pre == sha_post),
    )


# ---------------------------------------------------------------------------
# pHash utilities (T7)
# ---------------------------------------------------------------------------

def phash_distance(path_a: str | Path, path_b: str | Path, hash_size: int = 16) -> int:
    """Return the difference-hash (dHash) distance between two images.

    Uses a vendored dHash implementation via Pillow.  Install the ``intent``
    extra to satisfy the dependency::

        uv pip install -e ".[intent]"

    Parameters
    ----------
    path_a, path_b:
        Paths to image files (PNG, JPEG, etc.).
    hash_size:
        Side length of the hash grid.  The hash has ``hash_size * (hash_size - 1)``
        bits.  Default 16 gives 240-bit hashes.

    Returns
    -------
    int
        Hamming distance between the two hashes (0 = identical).
    """
    try:
        from PIL import Image  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "phash_distance requires Pillow.  Install the `intent` extra: "
            "uv pip install -e '.[intent]'"
        ) from exc

    def _dhash(img_path: str | Path) -> int:
        img = Image.open(img_path).convert("L").resize(
            (hash_size + 1, hash_size), Image.LANCZOS
        )
        pixels = list(img.getdata())
        bits = 0
        for row in range(hash_size):
            for col in range(hash_size):
                left = pixels[row * (hash_size + 1) + col]
                right = pixels[row * (hash_size + 1) + col + 1]
                bits = (bits << 1) | (1 if left > right else 0)
        return bits

    h_a = _dhash(path_a)
    h_b = _dhash(path_b)
    xor = h_a ^ h_b
    return bin(xor).count("1")


def calibrate_threshold(pairs_same: list[int], pairs_diff: list[int]) -> int:
    """Pick the largest integer T such that max(same) <= T < min(diff).

    Parameters
    ----------
    pairs_same:
        pHash distances between images that *should* be considered equal.
    pairs_diff:
        pHash distances between images that *should* be considered different.

    Returns
    -------
    int
        The largest separable threshold.

    Raises
    ------
    ValueError
        If no integer T satisfies max(same) <= T < min(diff).
    """
    if not pairs_same or not pairs_diff:
        raise ValueError("calibrate_threshold: both pairs_same and pairs_diff must be non-empty")
    max_same = max(pairs_same)
    min_diff = min(pairs_diff)
    if max_same >= min_diff:
        raise ValueError(
            f"calibrate_threshold: no separable threshold exists "
            f"(max_same={max_same} >= min_diff={min_diff})"
        )
    return max_same


# ---------------------------------------------------------------------------
# Execution wrapper + rendered diff (T9)
# ---------------------------------------------------------------------------

class RenderDiffExecutionError(Exception):
    """Raised when run_and_collect fails or returns no outputs."""


@dataclass
class RenderDiffReport:
    """Result of a pixel-level rendered comparison between pre- and post-edit workflows.

    Default threshold: 8 for hash_size=16.
    """
    distance: int
    equal_within_tolerance: bool
    pre_outputs: list[Path]
    post_outputs: list[Path]


def run_and_collect(wf: "VibeWorkflow") -> list[Path]:
    """Execute *wf* via the embedded runtime and return output paths.

    Uses :func:`vibecomfy.runtime.run.run_embedded_sync` directly.
    Output paths are taken from ``result.outputs``; no private helpers are imported.

    Raises
    ------
    RenderDiffExecutionError
        On QueueError, RuntimeError, or when the run returns no output paths.
    """
    from vibecomfy.errors import QueueError
    from vibecomfy.runtime.run import run_embedded_sync

    try:
        result = run_embedded_sync(wf)
    except QueueError as exc:
        raise RenderDiffExecutionError(f"Queue error during execution: {exc}") from exc
    except RuntimeError as exc:
        raise RenderDiffExecutionError(f"Runtime error during execution: {exc}") from exc

    paths = [Path(p) for p in result.outputs]
    if not paths:
        raise RenderDiffExecutionError("run_and_collect: execution returned no output paths")
    return paths


def compare_rendered(
    pre_wf: "VibeWorkflow",
    post_wf: "VibeWorkflow",
    *,
    seed: int = 0,
    threshold: int | None = None,
) -> RenderDiffReport:
    """Run both workflows and compare rendered outputs via pHash distance.

    Applies :func:`fix_seeds_in_ir` to both workflows before execution to
    maximise reproducibility.  Default threshold is 8 (for hash_size=16).

    Note: workflows using ancestral or SDE samplers (e.g. wan_* / ltx_*)
    remain nondeterministic even with a fixed seed; callers may need to
    widen the threshold or run multiple trials for those families.
    """
    if threshold is None:
        threshold = 8

    seeded_pre = fix_seeds_in_ir(pre_wf, seed)
    seeded_post = fix_seeds_in_ir(post_wf, seed)

    pre_outputs = run_and_collect(seeded_pre)
    post_outputs = run_and_collect(seeded_post)

    if not pre_outputs or not post_outputs:
        raise RenderDiffExecutionError("compare_rendered: one or both runs produced no outputs")

    distance = phash_distance(pre_outputs[0], post_outputs[0])
    return RenderDiffReport(
        distance=distance,
        equal_within_tolerance=(distance <= threshold),
        pre_outputs=pre_outputs,
        post_outputs=post_outputs,
    )
