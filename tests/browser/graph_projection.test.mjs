import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";

import {
  buildLayoutGraphProjection,
  buildStructuralGraphProjection,
} from "../../vibecomfy/comfy_nodes/web/graph_projection.js";
import { canonicalSessionJsonString } from "../../vibecomfy/comfy_nodes/web/canonical_hash.js";

const GRAPH = {
  extra: { prompt: { "1": {}, "11": {}, "2": {} } },
  nodes: [
    {
      id: 239,
      type: "GetNode",
      pos: [1, 2],
      size: [112, 36],
      widgets_values: ["latent"],
      outputs: [{ name: "LATENT", links: [40, 41] }],
    },
    {
      id: 113,
      type: "Sampler",
      pos: [5, 6],
      size: [210, 90],
      widgets_values: [2],
      inputs: [{ name: "latent_image", link: 41 }],
    },
    {
      id: 206,
      type: "Scheduler",
      pos: [9, 10],
      size: [210, 90],
      widgets_values: [{ videopreview: { x: 1 }, keep: true }],
      inputs: [{ name: "latent", link: 40 }],
    },
  ],
  links: [
    [40, 239, 0, 206, 0, "LATENT"],
    [41, 239, 0, 113, 0, "LATENT"],
  ],
  groups: [
    { id: "group-b", scope_path: "", title: "Prompt / Text", bounding: [0, 0, 400, 200], color: "#fff", nodes: [113] },
    { id: "group-a", scope_path: "", title: "Prompt / Text", bounding: [500, 0, 400, 200], color: "#fff", nodes: [206] },
  ],
};

function hash(value) {
  return createHash("sha256")
    .update(canonicalSessionJsonString(value), "utf8")
    .digest("hex");
}

test("browser structural projection matches the Python session authority fixture", () => {
  assert.equal(
    hash(buildStructuralGraphProjection(GRAPH)),
    "e6b91a8b9ac68519e0f865667480628dbc39a5e146cd663560f2bbeb78de302a",
  );
});

test("exec Apply verification ignores the duplicate dynamic-IO widget representation", () => {
  const source = "from PIL import Image\nreturn {\"image\": image}";
  const authoritativeCandidate = {
    nodes: [
      {
        id: 127,
        type: "VAEDecodeTiled",
        mode: 0,
        widgets_values: [512, 64, 4096, 8],
        inputs: [],
        outputs: [{ name: "IMAGE", links: [654] }],
      },
      {
        id: 370,
        type: "vibecomfy.exec",
        mode: 0,
        widgets_values: [
          source,
          { inputs: { image: "IMAGE" }, outputs: { image: "IMAGE" } },
        ],
        inputs: [{ name: "in_0", label: "image: IMAGE", type: "IMAGE", link: 654 }],
        outputs: [{ name: "out_0", label: "image: IMAGE", type: "IMAGE", links: [655] }],
      },
      {
        id: 140,
        type: "VHS_VideoCombine",
        mode: 0,
        widgets_values: { format: "video/h264-mp4" },
        inputs: [{ name: "images", type: "IMAGE", link: 655 }],
        outputs: [],
      },
    ],
    links: [
      [654, 127, 0, 370, 0, "IMAGE"],
      [655, 370, 0, 140, 0, "IMAGE"],
    ],
  };
  const browserRoundTrip = structuredClone(authoritativeCandidate);
  browserRoundTrip.nodes[1].widgets_values[1] = {
    inputs: [["image", "IMAGE"]],
    outputs: [["image", "IMAGE"]],
  };

  const authoritativeHash = hash(buildStructuralGraphProjection(authoritativeCandidate));
  assert.equal(
    authoritativeHash,
    "043a73d8c35c6c82e760dcca837d40f0cfd92b0db76e928aeeff57827e4709fe",
    "browser projection must stay byte-compatible with Python session authority",
  );
  assert.equal(
    hash(buildStructuralGraphProjection(browserRoundTrip)),
    authoritativeHash,
    "ComfyUI normalizing exec io from dicts to entry lists must not roll back a valid Apply",
  );
});

test("layout projection ignores compiler-only group membership and preserves duplicate titles", () => {
  const projection = buildLayoutGraphProjection(GRAPH);
  assert.equal(
    hash(projection),
    "e89f582734c1bc3b59d0402c779b0a171afa6184cc2a5f1600033bc13d84c25c",
  );
  assert.equal(projection.groups.length, 2);
  assert.equal(Object.hasOwn(projection.groups[0], "nodes"), false);
});

test("layout projection rejects nested scopes the browser adapter cannot apply", () => {
  assert.throws(
    () => buildLayoutGraphProjection({
      nodes: [],
      groups: [],
      definitions: { nested: { nodes: [], groups: [] } },
    }),
    (error) => error?.code === "UNSUPPORTED_NESTED_LAYOUT_SCOPE",
  );
  assert.throws(
    () => buildLayoutGraphProjection({
      nodes: [],
      groups: [{ id: "nested-group", scope_path: "subgraph:1", title: "Nested" }],
    }),
    (error) => error?.code === "UNSUPPORTED_NESTED_LAYOUT_SCOPE",
  );
});

test("incident a66422e6 survives native group normalization under layout_v1", async () => {
  const fixture = JSON.parse(await readFile(
    new URL("../fixtures/agent_edit/a66422e6_layout_regression.json", import.meta.url),
    "utf8",
  ));
  assert.equal(
    fixture.historical_candidate_groups.every((group) => group.id == null),
    true,
    "the production failure used duplicate id-less groups",
  );
  const nativeSerialized = {
    ...fixture.candidate,
    groups: fixture.candidate.groups.map(
      ({ nodes: _nodes, scope_path: _scopePath, ...group }) => group,
    ),
  };
  assert.equal(
    hash(buildLayoutGraphProjection(fixture.candidate)),
    hash(buildLayoutGraphProjection(nativeSerialized)),
  );
  assert.equal(
    hash(buildStructuralGraphProjection(fixture.original)),
    hash(buildStructuralGraphProjection(fixture.candidate)),
  );
});
