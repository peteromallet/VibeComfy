from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vibecomfy.comfy_nodes.agent.edit import _format_available_node_names, _present_class_types
from vibecomfy.comfy_nodes.agent.provider import build_batch_messages
from vibecomfy.porting.edit.session import EditSession
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.schema.provider import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


class _ProbeSchemaProvider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)

    def schemas(self) -> dict[str, NodeSchema]:
        return self._schemas


def _schema(class_type: str) -> NodeSchema:
    return NodeSchema(
        class_type=class_type,
        pack=None,
        inputs={
            "image": InputSpec("IMAGE", required=False),
            "strength": InputSpec("FLOAT", required=False, default=1.0),
        },
        outputs=[OutputSpec("IMAGE", "IMAGE")],
        source_provider="probe",
        confidence=1.0,
    )


def _load_replay_graph(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(raw, dict) and isinstance(raw.get("nodes"), list):
        return raw
    return None


def _node_types_from_ui(ui: dict[str, Any]) -> list[str]:
    types: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            nodes = value.get("nodes")
            if isinstance(nodes, list):
                for node in nodes:
                    if isinstance(node, dict):
                        class_type = node.get("type") or node.get("class_type")
                        if isinstance(class_type, str) and class_type:
                            types.add(class_type)
                        visit(node)
            for key in ("graphs", "subgraphs"):
                nested = value.get(key)
                if isinstance(nested, list):
                    for item in nested:
                        visit(item)
                elif isinstance(nested, dict):
                    for item in nested.values():
                        visit(item)

    visit(ui)
    return sorted(types)


def _synth_graph(class_types: list[str], provider: _ProbeSchemaProvider) -> dict[str, Any]:
    wf = VibeWorkflow("catalog-size-probe", WorkflowSource("catalog-size-probe"))
    for index, class_type in enumerate(class_types[:20], start=1):
        wf.nodes[str(index)] = VibeNode(str(index), class_type, inputs={"strength": 1.0})
    return emit_ui_json(wf, schema_provider=provider)


def _message_and_catalog_chars(
    *,
    session: EditSession,
    python_source: str,
    signature_catalog: str,
    available_node_names: str = "",
) -> tuple[int, int]:
    messages = build_batch_messages(
        task="Probe catalog prompt size.",
        python_source=python_source,
        signature_catalog=signature_catalog,
        available_node_names=available_node_names,
        budget_remaining=12,
        max_batches=12,
    )
    return len(messages[1]["content"]), len(signature_catalog)


def main() -> None:
    replay = _load_replay_graph(Path("/tmp/replay_big_graph.ui.json"))
    if replay is not None:
        replay_types = _node_types_from_ui(replay)
        extra_types = [f"AvailableOnlyNode{i:03d}" for i in range(250)]
        provider = _ProbeSchemaProvider(
            {name: _schema(name) for name in sorted(set(replay_types + extra_types))}
        )
        session = EditSession(replay, schema_provider=provider)
    else:
        class_types = [f"ProbeNode{i:03d}" for i in range(250)]
        provider = _ProbeSchemaProvider({name: _schema(name) for name in class_types})
        session = EditSession(_synth_graph(class_types, provider), schema_provider=provider)

    python_source = session.render()
    old_catalog = session.search(formatted=True)
    present_types = _present_class_types(session)
    new_catalog = session.search(focus_types=present_types, formatted=True)
    available_names = _format_available_node_names(session.search(formatted=False))

    assert isinstance(old_catalog, str)
    assert isinstance(new_catalog, str)
    old_user_chars, old_catalog_chars = _message_and_catalog_chars(
        session=session,
        python_source=python_source,
        signature_catalog=old_catalog,
    )
    new_user_chars, new_catalog_chars = _message_and_catalog_chars(
        session=session,
        python_source=python_source,
        signature_catalog=new_catalog,
        available_node_names=available_names,
    )
    reduction = 100.0 * (old_user_chars - new_user_chars) / max(old_user_chars, 1)
    catalog_reduction = 100.0 * (old_catalog_chars - new_catalog_chars) / max(old_catalog_chars, 1)

    source = "/tmp/replay_big_graph.ui.json" if replay is not None else "synthetic"
    print(f"source={source}")
    print(f"old_user_message_chars={old_user_chars}")
    print(f"old_catalog_chars={old_catalog_chars}")
    print(f"new_user_message_chars={new_user_chars}")
    print(f"new_catalog_chars={new_catalog_chars}")
    print(f"user_message_reduction_percent={reduction:.1f}")
    print(f"catalog_reduction_percent={catalog_reduction:.1f}")


if __name__ == "__main__":
    main()
