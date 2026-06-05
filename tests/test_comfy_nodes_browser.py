from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

import pytest

from vibecomfy.comfy_nodes.agent_session import payload_hash, structural_graph_hash

_WORKTREE_ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_browser_harness_smoke() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for browser harness smoke")

    result = subprocess.run(
        [node, "--test", "tests/browser/roundtrip_smoke.test.mjs"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_browser_canonical_hash_matches_python_payload_hash() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for browser hash parity")

    payloads = [
        {
            "graph": {
                "meta": {"locale": "café 漢字", "seed": 9007199254740991, "cfg": 7.5},
                "nodes": [
                    {
                        "id": 2,
                        "type": "SaveImage",
                        "widgets_values": [{"beta": 2, "alpha": 1}, ["frame-1", {"z": 3, "a": 2}]],
                        "properties": {"vibecomfy_uid": "uid-2", "nested": {"zeta": 2, "alpha": 1}},
                    },
                    {
                        "id": 1,
                        "type": "Input",
                        "properties": {"vibecomfy_uid": "uid-1", "prompt": "naïve façade"},
                    },
                ],
                "links": [[1, 1, 0, 2, 0, "IMAGE"]],
            }
        },
        {
            "graph": {
                "links": [],
                "nodes": [
                    {
                        "id": 4,
                        "type": "KSampler",
                        "widgets_values": [123456789, 20, 0.125, "euler"],
                        "properties": {"vibecomfy_uid": "uid-4", "labels": ["ä", "ß", "ç"]},
                    }
                ],
                "extras": {
                    "sorted_key_edge_case": {
                        "zebra": 1,
                        "alpha": 2,
                        "middle": {"omega": 9, "beta": 3},
                    }
                },
            }
        },
        {
            "graph": {
                "nodes": [
                    {
                        "id": 7,
                        "type": "PreviewImage",
                        "properties": {"vibecomfy_uid": "uid-7", "floats": [0.5, 1.25, 2.75]},
                    }
                ],
                "links": [],
                "audit": {
                    "reviewer": {"notes": ["résumé", "jalapeño"], "accepted": False},
                    "history": [
                        {"turn_id": "0001", "state": "candidate"},
                        {"turn_id": "0002", "state": "unknown"},
                    ],
                },
            }
        },
    ]

    script = """
import crypto from "node:crypto";

function canonicalizeJsonValue(value) {
  if (Array.isArray(value)) {
    return value.map((entry) => canonicalizeJsonValue(entry));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, entryValue]) => [key, canonicalizeJsonValue(entryValue)]),
    );
  }
  return value;
}

const payloads = JSON.parse(process.argv[1]);
const hashes = payloads.map((value) =>
  crypto.createHash("sha256").update(JSON.stringify(canonicalizeJsonValue(value)), "utf8").digest("hex"),
);
process.stdout.write(JSON.stringify(hashes));
"""
    result = subprocess.run(
        [node, "--input-type=module", "-e", script, json.dumps(payloads, ensure_ascii=False)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    js_hashes = json.loads(result.stdout)
    py_hashes = [payload_hash(payload) for payload in payloads]
    assert js_hashes == py_hashes


def test_browser_structural_hash_matches_python_structural_graph_hash() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for browser structural hash parity")

    # Fixture graphs intentionally exercise every divergence risk between the
    # JS buildStructuralGraphProjection() and the Python
    # structural_graph_projection():
    #
    #   integral floats   — 1.0 → 1; 2.0 → 2; 0.0 → 0; -3.0 → -3
    #   non-integral      — 1.5, -0.5 stay as-is
    #   booleans          — True / False preserved (NOT int-coerced)
    #   preview-like keys — "preview", "videopreview", "_preview",
    #                        "preview_", "video_preview" stripped
    #   mixed-format ids  — string "10","2","alpha","02", int -1
    #   unwired inputs    — link: None filtered out
    #   dead outputs      — links: [] / links: None filtered out
    #   endpoint-name     — links projected by slot name, not index
    graphs = [
        # ── Graph 1: full-structural smoke test ──────────────────────────
        {
            "extra": {"ds": {"scale": 1.0}},
            "nodes": [
                {
                    "id": "10",
                    "type": "SaveImage",
                    "pos": [300, 200],
                    "inputs": [
                        {"name": "unused_optional", "link": None, "type": "IMAGE"},
                        {"name": "images", "link": 9, "type": "IMAGE"},
                    ],
                    "outputs": [
                        {"name": "ignored_empty", "links": []},
                        {"name": "ui_preview", "links": None},
                    ],
                    "widgets_values": ["prefix"],
                },
                {
                    "id": "2",
                    "type": "KSampler",
                    "pos": [100, 200],
                    "size": [300, 400],
                    "order": 7,
                    "flags": {"collapsed": True},
                    "properties": {"vibecomfy_uid": "volatile"},
                    "mode": 0,
                    "inputs": [
                        {"name": "unwired_seed", "link": None, "type": "INT"},
                        {"name": "model", "link": 99, "type": "MODEL"},
                    ],
                    "outputs": [
                        {"name": "LATENT", "links": [9]},
                        {"name": "unused", "links": []},
                    ],
                    "widgets_values": [
                        # direct integral float → int, plus preview-like keys
                        1.0,
                        True,
                        False,
                        1.5,
                        {"keep": "value", "videopreview": {"frame": 9, "url": "/view"}},
                        {"scale": 2.0, "preview": "ignored"},
                        {
                            "_preview": "drop-me",
                            "preview_": "drop-too",
                            "video_preview": "also-dropped",
                            "keep_me": 0.0,
                            "nested": {
                                "preview_inner": "drop",
                                "val": -3.0,
                            },
                        },
                    ],
                },
            ],
            "links": [
                [99, 1, 0, "2", 1, "MODEL"],
                [9, "2", 0, "10", 1, "IMAGE"],
                {
                    "id": 12,
                    "origin_id": "2",
                    "origin_slot": 0,
                    "target_id": "10",
                    "target_slot": 1,
                    "type": "IMAGE",
                },
            ],
            "groups": [{"title": "ignored"}],
        },
        # ── Graph 2: non-standard ids, non-node/link entries, named slots ─
        {
            "nodes": [
                {"id": "alpha", "type": "Note", "widgets_values": {"keep": True}},
                {"id": -1, "type": "Input"},
                "not-a-node",
                {"id": "02", "type": "Input"},
            ],
            "links": [
                {
                    "origin_id": "alpha",
                    "origin_slot": "custom",
                    "target_id": -1,
                    "target_slot": "field",
                    "type": "STRING",
                },
                "not-a-link",
            ],
        },
    ]

    script = """
import crypto from "node:crypto";
import { createBrowserHarness } from "./tests/browser/harness.mjs";

function canonicalizeJsonValue(value) {
  if (Array.isArray(value)) return value.map((entry) => canonicalizeJsonValue(entry));
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, entryValue]) => [key, canonicalizeJsonValue(entryValue)]),
    );
  }
  return value;
}
const graphs = JSON.parse(process.argv[1]);
const harness = await createBrowserHarness({
  responses: { "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } } },
});
try {
  const extensionModule = await harness.loadExtension();
  const hashes = graphs.map((graph) =>
    crypto
      .createHash("sha256")
      .update(
        JSON.stringify(canonicalizeJsonValue(extensionModule.buildStructuralGraphProjection(graph))),
        "utf8",
      )
      .digest("hex"),
  );
  process.stdout.write(JSON.stringify(hashes));
} finally {
  await harness.dispose();
}
"""
    result = subprocess.run(
        [node, "--input-type=module", "-e", script, json.dumps(graphs, ensure_ascii=False)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_WORKTREE_ROOT),
    )

    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert json.loads(result.stdout) == [structural_graph_hash(graph) for graph in graphs]
