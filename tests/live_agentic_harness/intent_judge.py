"""LLM intent judge for live agentic harness artifacts.

Provides a DeepSeek-backed text judge that scores a candidate workflow edit
against the scenario's natural-language intent.  The judge is intentionally
separate from the deterministic assessor so it can be enabled/disabled without
changing the core pass/fail logic.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.comfy_nodes.agent.provider import run_model_turn

_PROMPT_PATH = Path(__file__).parents[2] / "vibecomfy" / "intent" / "prompts" / "text_judge.prompt.md"


def _load_prompt() -> str:
    if _PROMPT_PATH.is_file():
        return _PROMPT_PATH.read_text(encoding="utf-8")
    # Fallback rubric if the canonical prompt is missing.
    return (
        "You are a precise evaluator for ComfyUI workflow edits. Given a natural-language\n"
        "intent and a structural diff between a pre-edit and post-edit workflow IR, you\n"
        "must determine whether the edit correctly implements the intent.\n\n"
        "Evaluate the edit against exactly four binary criteria:\n"
        "- correct_node_targeted\n"
        "- correct_parameter_changed\n"
        "- value_semantically_matches_intent\n"
        "- no_orphaned_wiring\n\n"
        "Respond with a JSON object and nothing else:\n"
        '{"pass_": true | false, "criteria": {"correct_node_targeted": true | false, '
        '"correct_parameter_changed": true | false, "value_semantically_matches_intent": true | false, '
        '"no_orphaned_wiring": true | false}, "rationale": "<one or two sentences>"}\n'
        "`pass_` must be true if and only if all four criteria are true."
    )


def _parse_verdict(raw: str) -> dict[str, Any]:
    """Parse the judge's JSON response into a normalized dict."""
    text = raw.strip()
    # Some models wrap JSON in markdown fences; strip them.
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    parsed = json.loads(text)
    criteria = parsed.get("criteria") or {}
    normalized_criteria = {
        "correct_node_targeted": bool(criteria.get("correct_node_targeted")),
        "correct_parameter_changed": bool(criteria.get("correct_parameter_changed")),
        "value_semantically_matches_intent": bool(criteria.get("value_semantically_matches_intent")),
        "no_orphaned_wiring": bool(criteria.get("no_orphaned_wiring")),
    }
    return {
        "pass_": bool(parsed.get("pass_")),
        "criteria": normalized_criteria,
        "rationale": str(parsed.get("rationale", "")),
    }


def _load_implementation_payload(output_dir: Path) -> dict[str, Any] | None:
    path = output_dir / "implementation_payload.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _schema_context_from_payload(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    graph = payload.get("graph")
    if not isinstance(graph, Mapping):
        return None
    compiled_api = graph.get("compiled_api")
    if not isinstance(compiled_api, Mapping):
        # Sidecar-less envelope: the execution view is derived by compiling the
        # IR (compile("api") is a function, not stored data). Only a graph the
        # decoder accepts yields context; anything else stays context-free.
        try:
            from vibecomfy.ingest.normalize import convert_to_vibe_format

            compiled_api = convert_to_vibe_format(dict(graph)).compile("api")
        except Exception:
            return None
    context: dict[str, Any] = {"compiled_api": compiled_api}
    metadata = graph.get("metadata")
    if isinstance(metadata, Mapping):
        widget_index = metadata.get("widget_index") or metadata.get("object_info_index")
        if isinstance(widget_index, Mapping):
            context["widget_index"] = widget_index
    return context


def _ui_nodes_by_id(ui: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    nodes = ui.get("nodes")
    if not isinstance(nodes, list):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        node_id = node.get("id")
        if node_id is not None:
            result[str(node_id)] = node
    return result


def _ui_links_by_id(ui: Mapping[str, Any]) -> dict[Any, Any]:
    links = ui.get("links")
    if not isinstance(links, list):
        return {}
    result: dict[Any, Any] = {}
    for link in links:
        if isinstance(link, list) and link:
            result[link[0]] = link
        elif isinstance(link, Mapping) and "id" in link:
            result[link.get("id")] = link
    return result


def _link_source(link: Any) -> dict[str, Any] | None:
    if isinstance(link, list) and len(link) >= 3:
        return {"node_id": str(link[1]), "slot": link[2]}
    if isinstance(link, Mapping):
        source_id = link.get("origin_id", link.get("source_id", link.get("from_node")))
        source_slot = link.get("origin_slot", link.get("source_slot", link.get("from_slot")))
        if source_id is not None:
            return {"node_id": str(source_id), "slot": source_slot}
    return None


def _linked_inputs_for_node(
    node: Mapping[str, Any],
    *,
    links_by_id: Mapping[Any, Any],
    nodes_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    inputs = node.get("inputs")
    if not isinstance(inputs, list):
        return []
    linked_inputs: list[dict[str, Any]] = []
    for index, input_item in enumerate(inputs):
        if not isinstance(input_item, Mapping):
            continue
        link_id = input_item.get("link")
        if link_id is None:
            continue
        source = _link_source(links_by_id.get(link_id))
        source_node = nodes_by_id.get(source["node_id"]) if source is not None else None
        linked_inputs.append(
            {
                "input_index": index,
                "name": input_item.get("name"),
                "type": input_item.get("type"),
                "link": link_id,
                "source": {
                    **(source or {}),
                    "class_type": source_node.get("type") if isinstance(source_node, Mapping) else None,
                },
            }
        )
    return linked_inputs


def _static_widget_dataflow_context(
    pre_ir: Mapping[str, Any],
    post_ir: Mapping[str, Any],
) -> dict[str, Any] | None:
    pre_nodes = _ui_nodes_by_id(pre_ir)
    post_nodes = _ui_nodes_by_id(post_ir)
    pre_links = _ui_links_by_id(pre_ir)
    post_links = _ui_links_by_id(post_ir)
    widget_deltas: list[dict[str, Any]] = []
    static_removals_with_preserved_dynamic_inputs: list[dict[str, Any]] = []

    for node_id, pre_node in sorted(pre_nodes.items()):
        post_node = post_nodes.get(node_id)
        if post_node is None:
            continue
        pre_widgets = pre_node.get("widgets_values")
        post_widgets = post_node.get("widgets_values")
        if not isinstance(pre_widgets, list) or not isinstance(post_widgets, list):
            continue
        linked_inputs_pre = _linked_inputs_for_node(
            pre_node,
            links_by_id=pre_links,
            nodes_by_id=pre_nodes,
        )
        linked_inputs_post = _linked_inputs_for_node(
            post_node,
            links_by_id=post_links,
            nodes_by_id=post_nodes,
        )
        linked_signature_pre = {
            (item.get("name"), item.get("link"), item.get("source", {}).get("node_id"))
            for item in linked_inputs_pre
        }
        linked_signature_post = {
            (item.get("name"), item.get("link"), item.get("source", {}).get("node_id"))
            for item in linked_inputs_post
        }
        preserved_dynamic_inputs = bool(linked_signature_pre & linked_signature_post)
        for index in range(max(len(pre_widgets), len(post_widgets))):
            old = pre_widgets[index] if index < len(pre_widgets) else None
            new = post_widgets[index] if index < len(post_widgets) else None
            if old == new:
                continue
            delta = {
                "node_id": node_id,
                "class_type": post_node.get("type") or pre_node.get("type"),
                "widget_index": index,
                "old": old,
                "new": new,
                "kind": "static_widget_delta",
                "linked_inputs_pre": linked_inputs_pre,
                "linked_inputs_post": linked_inputs_post,
                "preserved_dynamic_inputs": preserved_dynamic_inputs,
            }
            widget_deltas.append(delta)
            if isinstance(old, str) and old.strip() and (new is None or (isinstance(new, str) and not new.strip())):
                if preserved_dynamic_inputs:
                    static_removals_with_preserved_dynamic_inputs.append(delta)

    if not widget_deltas:
        return None
    return {
        "widget_deltas": widget_deltas,
        "static_widget_removals_with_preserved_dynamic_inputs": static_removals_with_preserved_dynamic_inputs,
        "note": (
            "widgets_values are static node configuration. Linked inputs are dynamic dataflow. "
            "A static text widget removal can be correct when linked dynamic inputs remain connected."
        ),
    }


def judge_edit_intent(
    output_dir: Path | str,
    scenario: Mapping[str, Any],
    *,
    route: str = "deepseek",
    model: str = "deepseek-v4-pro",
) -> dict[str, Any]:
    """Run the DeepSeek text judge on the candidate edit in *output_dir*.

    Returns a dict with ``pass_``, ``criteria``, ``rationale``, and ``metadata``.
    If required artifacts are missing or the model call fails, ``pass_`` is None
    and ``error`` describes why.
    """
    output_dir = Path(output_dir)
    query = str(scenario.get("query", "")).strip()
    if not query:
        return {"pass_": None, "error": "scenario has no query"}

    # The durable turn writes UI artifacts under out/editor_sessions; the response
    # JSON carries the exact paths in its artifacts block.
    response_path = output_dir / "response.json"
    original_ui_path: Path | None = None
    candidate_ui_path: Path | None = None
    if response_path.is_file():
        try:
            response = json.loads(response_path.read_text(encoding="utf-8"))
            artifacts = response.get("artifacts", {}) or {}
            if isinstance(artifacts.get("original_ui"), str):
                original_ui_path = Path(artifacts["original_ui"])
            if isinstance(artifacts.get("candidate_ui"), str):
                candidate_ui_path = Path(artifacts["candidate_ui"])
        except (OSError, json.JSONDecodeError):
            pass

    # Fallback to common in-directory locations if response artifacts are absent.
    if original_ui_path is None:
        original_ui_path = output_dir / "original.ui.json"
    if candidate_ui_path is None:
        candidate_ui_path = output_dir / "candidate.ui.json"

    if not original_ui_path.is_file() or not candidate_ui_path.is_file():
        return {
            "pass_": None,
            "error": f"missing UI artifacts: {original_ui_path} / {candidate_ui_path}",
        }

    try:
        pre_ir = json.loads(original_ui_path.read_text(encoding="utf-8"))
        post_ir = json.loads(candidate_ui_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"pass_": None, "error": f"failed to load UI artifacts: {exc}"}

    system_prompt = _load_prompt()
    implementation_payload = _load_implementation_payload(output_dir)
    schema_context = _schema_context_from_payload(implementation_payload) or {}
    dataflow_context = _static_widget_dataflow_context(pre_ir, post_ir)
    if dataflow_context:
        schema_context["dataflow_context"] = dataflow_context
    if schema_context:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\n## Schema and widget evidence\n"
            "When schema_context is provided, use it to map opaque widget_N fields "
            "to semantic input names. Treat literal widget values as static node "
            "configuration, and linked inputs/edges as dynamic dataflow. Do not guess a "
            "widget's meaning from index order when compiled_api names are available. "
            "If a static widget containing stale or fabricated text is removed while "
            "the relevant linked dynamic input path remains connected, do not treat "
            "that removal as deleting the dynamic dataflow."
        )
    # Optional non-prescriptive "desired outcome" rubric from the scenario. When
    # present, it grounds the judge on what a GOOD result achieves (the outcome +
    # what "smart/complete" means) WITHOUT prescribing exact nodes/params — sound
    # alternative approaches that reach the same outcome count as correct.
    desired = scenario.get("desired")
    if desired:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\n## Scenario-specific desired outcome (non-prescriptive)\n"
            "The scenario author described what a GOOD result looks like below. Use it to "
            "judge whether the edit achieves the desired OUTCOME in a smart, complete way. "
            "This is NOT a recipe of exact nodes/params to use — any sound approach that "
            "achieves the outcome counts as correct. Weigh: did it achieve the outcome, is "
            "it fully wired/complete (no dangling or broken connections, existing pipeline "
            "not broken), and is the approach a sensible one?\n\n"
            f"Desired outcome: {desired.get('outcome', '')}\n"
            f"What 'smart/complete' means here: {desired.get('quality', '')}\n"
            f"Alternative approaches acceptable: {desired.get('alternatives_ok', True)}"
        )
    payload = {"nl_intent": query, "pre_ir": pre_ir, "post_ir": post_ir}
    if desired:
        payload["desired_outcome"] = desired
    if schema_context:
        payload["schema_context"] = schema_context
    user_content = json.dumps(payload, indent=2)

    try:
        response = run_model_turn(
            "evaluate workflow edit against intent",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            route=route,
            model=model,
            response_contract="json",
        )
    except Exception as exc:  # noqa: BLE001
        return {"pass_": None, "error": f"model call failed: {exc}"}

    raw = response.get("content") or ""
    if not raw:
        return {"pass_": None, "error": "model returned empty content"}

    try:
        verdict = _parse_verdict(raw)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        return {
            "pass_": None,
            "error": f"could not parse judge response: {exc}",
            "raw": raw[:500],
        }

    verdict["metadata"] = {
        "route": route,
        "model": model,
        "elapsed_ms": response.get("_profiling", {}).get("elapsed_ms"),
    }
    return verdict
