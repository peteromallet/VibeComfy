from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vibecomfy.ingest.index import index_workflows, write_index
from vibecomfy.nodes.index import index_custom_node_examples, index_runtime_nodes, write_json


@dataclass(frozen=True)
class SourceSyncResult:
    official: int
    external: int
    nodes: int


def sync_sources(
    *,
    official: str | Path = "workflow_corpus/official",
    external: str | Path = "workflow_corpus/custom_nodes",
    custom_nodes: str | Path = "custom_nodes",
) -> SourceSyncResult:
    official_rows = index_workflows(official)
    external_vendor = index_workflows(external)
    custom_examples = index_custom_node_examples(custom_nodes)
    runtime_nodes = index_runtime_nodes()
    external_rows = external_vendor + custom_examples
    write_index("workflow_index.json", official_rows)
    write_index("external_workflow_index.json", external_rows)
    write_json("node_index.json", runtime_nodes)
    return SourceSyncResult(
        official=len(official_rows),
        external=len(external_rows),
        nodes=len(runtime_nodes),
    )
