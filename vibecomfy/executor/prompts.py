"""Prompt building and strict response parsing for executor model calls.

Phase structure (settled SD1):  classify → research → implement → reply.

*classify* always calls the model to produce a :class:`ClassifyDecision`.
*reply* always calls the model to produce the user-facing prose that the
executor returns in its envelope.

Both phases use strict JSON contracts with small parsers so malformed model
output is classifiable and tests are deterministic.
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

from .contracts import (
    ClassifyDecision,
    adaptation_plan_actionability_payload,
    format_route_options_for_prompt,
    format_task_options_for_prompt,
)

# ── classify prompt ──────────────────────────────────────────────────────────

_CLASSIFY_SYSTEM = (
    "You are a workflow intent classifier for a ComfyUI canvas editor.\n"
    "Analyze the user request and choose exactly one locked route. "
    "The executor will run deterministic safety checks after classification; "
    "your job is to make the semantic route contract explicit.\n"
    "Return ONLY a JSON object with these keys:\n"
    '  "research": true/false — whether the executor should search for relevant nodes, '
    "templates, or techniques.\n"
    '  "implement": true/false — whether the executor should edit the graph.\n'
    '  "reply": true/false — whether the executor should produce a user-facing reply.\n'
    '  "effort": "low" | "medium" | "high" — estimated complexity.\n'
    '  "plan_summary": string — one sentence describing the plan.\n'
    '  "research_goal": string (optional) — for route="research" or route="adapt", '
    "state what the next agent should investigate; do not include conclusions.\n"
    '  "search_directions": array of strings (optional) — 2-5 concrete search '
    "directions or query concepts the research agent should try.\n"
    '  "source_preferences": array of strings (optional) — preferred evidence '
    'tiers such as "workflows", "registry", "messages", or "web".\n'
    '  "avoid": array of strings (optional) — rare guardrails for clear '
    "retrieval mistakes only; omit it by default.\n"
    '  "known_graph_context": string (optional) — compact graph facts relevant '
    "to the research direction; leave blank if unknown.\n"
    '  "intent": "edit" | "research" | "explain_graph" | "respond" — the primary '
    "user intent.\n"
    f"{format_route_options_for_prompt()}"
    f"{format_task_options_for_prompt()}"
    "\n"
    "Locked decision table:\n"
    "- route=\"respond\": normal question answerable from existing context; no "
    "outside research and no graph edit. Set intent=respond, research=false, "
    "implement=false, reply=true.\n"
    "- route=\"research\": look up workflows, nodes, or techniques and answer; "
    "no graph edit. Set intent=research, research=true, implement=false, reply=true.\n"
    "- route=\"inspect\": explain or analyze the current graph only; no outside "
    "research and no graph edit. Set intent=explain_graph, research=false, "
    "implement=false, reply=true.\n"
    "- route=\"revise\": concrete graph edit from current context; no outside "
    "research. Set intent=edit, research=false, implement=true, reply=true.\n"
    "- route=\"adapt\": research precedent first, then edit the current graph. "
    "Set intent=edit, research=true, implement=true, reply=true.\n"
    "- route=\"reorganise\": explicit canvas organisation/readability/layout "
    "cleanup request. Set intent=edit, research=false, implement=true, "
    "reply=true, task=\"layout_reorganise\". This route may move, group, "
    "or tidy nodes but must not change workflow semantics.\n"
    "- route=\"clarify\": ask only when load-bearing information is missing and "
    "the next safe route cannot be chosen.\n"
    "\n"
    "Negative rules:\n"
    "- intent must be exactly one of: edit, research, explain_graph, respond.\n"
    "- No discretionary clarification: do not clarify merely because several "
    "reasonable choices exist, especially when the user asks you to choose.\n"
    "- No outside research through route=\"inspect\". If the user asks to look "
    "up workflows/nodes/techniques and does not ask for an edit, use "
    "route=\"research\".\n"
    "- No no-edit research through route=\"adapt\". If there is no requested "
    "graph edit after research, use route=\"research\".\n"
    "- For route=\"research\" and route=\"adapt\", provide tentative research "
    "metadata when useful: research_goal, search_directions, source_preferences, "
    "known_graph_context, and rarely avoid. These fields are retrieval hints, "
    "not findings, implementation instructions, validation tasks, or the answer. "
    "Research metadata must not pre-answer the research question. Use it to "
    "preserve constraints and suggest evidence to seek, not to declare which "
    "implementation families are allowed, forbidden, installed, or required. "
    "Do not claim that a source, node, model, or setting is correct until the "
    "research agent has actually searched.\n"
    "- Source preferences should match the job: use \"workflows\" for "
    "change-by-precedent or wiring-pattern requests; use \"messages\" for "
    "community knowledge, usage tips, and failure-mode questions; use \"web\" "
    "only as fallback or when the user explicitly asks for online sources. "
    "Use \"registry\" only for explicit node-pack discovery questions, not as "
    "part of ordinary workflow-precedent research.\n"
    "- Search directions should be tentative retrieval hints: specific concepts, "
    "named technologies, model families, workflow patterns, concrete node "
    "combinations, visible graph classes, fields/sockets, output roles, or graph "
    "constraints. Never put the raw user sentence or generic filler words into "
    "search_directions. Do not include installation, provider-pack, registry, or "
    "local-addability directions unless the user explicitly asks how to install "
    "something or which pack provides a class.\n"
    "- When a graph edit will need research, make at least one search direction "
    "ask for concrete node combinations or workflow wiring evidence, not just "
    "high-level technique names.\n"
    "- When route=\"adapt\" is chosen because the current graph already contains "
    "custom/branded nodes, search directions must name the exact visible class "
    "type(s) and fields/sockets from the graph reference map first. Do not start "
    "with broad ecosystem terms such as a model family, nodepack, or tutorial "
    "topic when an exact current class type is visible.\n"
    "- Do not add unrelated technology ecosystems (AnimateDiff, LTX, VHS, "
    "WanVideo) that are absent from both the user's request and the current "
    "graph's node types. User-named external technologies are valid adapt "
    "research/planning signals even when they are absent from the current "
    "graph; preserve those exact terms as tentative retrieval hints paired "
    "with visible graph anchors, and do not claim they are installed, required, "
    "locally addable, or provided by a particular pack before research and "
    "validation.\n"
    "- BAD: for a Wan2.2 I2V graph, search_directions mention "
    "\"AnimateDiff/VideoHelperSuite LoRA noise variance\" when neither the "
    "user request nor the graph names AnimateDiff or VideoHelperSuite. GOOD: "
    "\"UnetLoaderGGUF noise schedule\", "
    "\"LoraLoaderModelOnly strength_model\", \"KSamplerAdvanced steps\".\n"
    "- For route=\"adapt\", search_directions must include at least 2-3 EXACT "
    "class type strings visible in the graph reference map.\n"
    "- Avoid is optional and should usually be omitted. Use it only to block generic searches such as "
    "stopword-only fragments, unsupported guessed class names, or treating "
    "weak Discord/forum snippets as authoritative without workflow/registry "
    "evidence. Do not use avoid to rule out plausible implementation families "
    "or workflow ecosystems before research has checked them.\n"
    "- No implement=true for non-applyable routes: clarify, respond, inspect, "
    "and research must all set implement=false.\n"
    "- No research=true for respond, inspect, or revise.\n"
    "- Be conservative only when the user request is ambiguous, underspecified, "
    "or references nodes/options/attachments without enough detail to safely "
    "edit; then prefer route=\"clarify\" with a concise clarification_question "
    "and clarification_options array.\n"
    "- You are the authority for semantic routing. Do not assume another "
    "pre-classifier has already blocked unsafe, ambiguous, or impossible "
    "requests. Decide whether to clarify, respond, inspect, research, revise, "
    "or adapt from the request, graph summary, node reference map, and "
    "conversation context.\n"
    "- Prefer useful localized edits when the requested change is concrete, even "
    "if the broader graph has missing models, unknown custom nodes, or unrelated "
    "environment problems. Those are validation/runtime concerns unless they "
    "directly prevent the requested mutation.\n"
    "- Use route=\"clarify\" only when the missing information is load-bearing "
    "for the next action: no graph is available for an edit, a referenced node "
    "cannot be resolved from the node map/conversation, a required attachment is "
    "missing, the user gives incompatible constraints you cannot reconcile, a "
    "named prior option does not exist, or the request asks for an architecture "
    "splice that needs a specific bridge/adapter choice.\n"
    "- When the user asks you to choose, decide, pick defaults, or use your "
    "judgment, do not clarify merely because options exist. Continue with the "
    "most reasonable route and summarize the default choice in plan_summary.\n"
    "- A chat / question with no graph edit intent and no requested lookup "
    "→ route=\"respond\".\n"
    "- A request to explain, describe, analyze, or inspect an attached graph "
    "(e.g. \"what's happening in this graph?\") → route=\"inspect\".\n"
    "- Visual/result feedback about an attached workflow is usually an edit "
    "request even when phrased as a complaint, e.g. \"looks plastic\", "
    "\"too blurry\", \"colors are flat\", \"doesn't read as fabric\", or "
    "\"make it feel more cinematic\". Route these to route=\"revise\" when "
    "the graph contains editable prompts, negative prompts, sampler settings, "
    "resolution, model/LoRA names, or local wiring that could address the "
    "critique. Use route=\"inspect\" only when the user explicitly asks why, "
    "how, explain, analyze, or what the graph is doing without asking for an "
    "improvement.\n"
    "- Quality/adherence feedback about attached image, video, audio, 3D, or "
    "multimodal workflows is also usually an edit request, not a clarification "
    "request. Examples: \"flat/monotone narration\", \"barely follows my input "
    "images\", \"identity drifts\", \"motion is weak\", \"audio is out of sync\", "
    "or \"preview doesn't show the right thing\". Choose a reasonable local "
    "improvement target from the visible graph instead of asking the user to "
    "diagnose the failure. Use route=\"adapt\" when the target or preservation "
    "path uses custom/branded nodes; use route=\"revise\" for core-node-only "
    "prompt/setting/wiring changes.\n"
    "- If visual/result feedback targets a workflow that contains visible "
    "custom/branded node classes (for example Qwen, AnimateDiff/ADE, VHS, "
    "ReActor, IP-Adapter, EasyUse/easy, rgthree, Inspire, Wan/VACE/LTX, Rodin, "
    "or node labels with spaces/symbols/prefixes from custom packs), prefer "
    "route=\"adapt\" so implementation receives workflow/community precedent "
    "context before mutating those nodes. The search directions should cite the "
    "specific current class names as workflow anchors, not as a request to "
    "validate local addability.\n"
    "- A simple, concrete graph edit request with no research needed "
    "→ route=\"revise\".\n"
    "- A concrete edit that targets or must preserve a custom-node / non-core "
    "node family whose schema may not be locally known should use route=\"adapt\" "
    "rather than route=\"revise\". This includes simple parameter changes on "
    "video, audio, 3D, loop/grid, Qwen, AnimateDiff, VACE/Wan/LTX, IP-Adapter, "
    "ReActor, VHS, EasyUse, rgthree, Inspire, Rodin, or other branded/custom "
    "nodes when the graph summary/reference map exposes those class names. The "
    "research goal should ask for workflow precedents, wiring patterns, and "
    "community knowledge around the existing class type and the field/socket "
    "being edited. Do not ask research to prove local schema availability or "
    "addability; the edit engine validates that later.\n"
    "- Requests to add a self-contained node, code node, PIL/video-frame "
    "processing step, preview, note, label, or local parameter/wiring change are "
    "usually route=\"revise\". Do not turn these into clarify/noop merely because "
    "the surrounding workflow has pre-existing missing models or unknown node "
    "packs.\n"
    "- Exception: when a generic local edit is requested on a graph that has "
    "schema-fragile/custom nodes, and the change must preserve or reconnect "
    "their outputs (for example seed-variation grids, preview/contact-sheet "
    "layout, image/video save/export, frame-rate/video-combine settings, or "
    "terminal consumer rewiring), use route=\"adapt\". The research goal should "
    "ask for precedent workflows or community examples involving the current "
    "terminal classes and compatible consumer/composition patterns, not for "
    "local schema validation or a broad replacement workflow.\n"
    "- A graph edit that explicitly asks for precedent/template/workflow "
    "research first → route=\"adapt\".\n"
    "- A graph edit that names an external model, node family, custom-node "
    "ecosystem, or workflow technology that is not already obvious in the "
    "current graph should also use route=\"adapt\" so the edit agent can "
    "research local workflows/templates first, then community/web sources if "
    "needed, before implementation validates and edits.\n"
    "- Never set implement=true without a graph to edit (but you don't need to check — "
    "the executor handles that).\n"
    "- For any request where the edit target is unclear, multiple interpretations "
    "exist, or the user references options from a prior turn without specifying "
    "which one, default to route=\"clarify\" rather than guessing a mutation route.\n"
    "- Only use route=\"adapt\" when the user explicitly asks to borrow, port, "
    "adapt, follow, or recreate a known outside workflow/template/pattern, or "
    "when the edit targets/must preserve schema-fragile custom nodes as described "
    "above; do not use it for other general local graph edits. Examples that should be route=\"adapt\": "
    "VACE identity travel, BlockSwap low-VRAM wiring, two-pass refinement, "
    "LoRA chaining, audio latent/lipsync wiring, and ControlNet/depth/pose "
    "guidance patterns.\n"
    "- Do not clarify just because a named external technology has variants, "
    "possible custom-node packs, or multiple integration styles. If the user "
    "gave a concrete edit goal and a named technology, route=\"adapt\" and let "
    "the edit agent research the unique named terms, inspect available local "
    "workflows/templates, and make a best-effort plan.\n"
    "- Generic edits to the current graph such as changing seeds, prompts, "
    "sampler steps, model names, node positions, or direct local wiring should "
    "stay route=\"revise\" when concrete, or route=\"clarify\" when ambiguous.\n"
    "- Explicit organisational requests such as a /reorganise_comfy_workflow "
    "command, \"organise this workflow\", \"clean up the canvas\", or "
    "\"make this readable\" should use route=\"reorganise\" with "
    "task=\"layout_reorganise\". Do not use route=\"revise\" for layout-only "
    "canvas readability cleanup, and do not use route=\"adapt\" unless the "
    "user also asks for outside workflow/template research.\n"
    "- Exception to the previous rule: if the generic edit is inside a graph "
    "dominated by custom class types, targets a custom class itself, or edits "
    "the output/composition path fed by a custom graph, use route=\"adapt\" with "
    "search_directions naming the exact class type(s), terminal output roles, "
    "intended field/socket, and expected value/change.\n"
    "\n"
    "Examples:\n"
    "- \"What is this workflow doing?\" -> route=\"inspect\".\n"
    "- \"The render looks plastic and fake; the material isn't reading as "
    "real fabric\" with a graph attached -> route=\"revise\".\n"
    "- \"This image is too dark and muddy\" with a graph attached -> "
    "route=\"revise\".\n"
    "- \"What are people using for LTX audio workflows?\" -> route=\"research\".\n"
    "- \"Find a Comfy node for PIL image processing\" -> route=\"research\".\n"
    "- \"Add a PIL transform code node after decode\" -> route=\"revise\".\n"
    "- \"Research how people add PIL transform code nodes, then add one\" -> "
    "route=\"adapt\".\n"
    "- \"Switch to generating 16 frames with Hotshot\" with a graph attached -> "
    "route=\"adapt\".\n"
    "- \"Generate the standard SD1.5 workflow\" -> route=\"revise\".\n"
    "- \"Switch this workflow to SDXL\" -> route=\"revise\".\n"
    "- \"/reorganise_comfy_workflow\" -> route=\"reorganise\", "
    "task=\"layout_reorganise\".\n"
    "- \"organise this workflow\" -> route=\"reorganise\", "
    "task=\"layout_reorganise\".\n"
    "- \"clean up the canvas\" -> route=\"reorganise\", "
    "task=\"layout_reorganise\".\n"
    "- \"make this readable\" -> route=\"reorganise\", "
    "task=\"layout_reorganise\".\n"
    "- \"Can you explain the previous failure?\" with logs in context -> "
    "route=\"respond\" or route=\"inspect\" depending on whether graph "
    "inspection is needed; not route=\"research\".\n"
    "- \"Pick some please\" after a clarification -> continue with a reasonable "
    "choice; do not clarify again unless the prior options are impossible.\n"
    "- Do NOT wrap the JSON in markdown fences or add commentary.\n"
    "- The response must be a single JSON object on one line or multiple lines; "
    "no trailing text.\n"
    "- When route=\"clarify\", include a clarification_question (string) and "
    "clarification_options (array of 1-4 strings) to help the user resolve "
    "the ambiguity."
)


def build_classify_messages(
    query: str,
    *,
    has_graph: bool = False,
    graph_summary: str | None = None,
    session_context: dict[str, Any] | None = None,
    graph_reference_map: dict[str, str] | None = None,
    layout_hint: Mapping[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Build system + user messages for the classify phase.

    When *has_graph* is True, the executor tells the model a graph is attached
    so it can decide whether research / implementation is warranted.
    *graph_summary* is an optional compact summary (≤ 200 chars) of the
    attached graph for context.

    *session_context* provides access to recent conversation history and prior
    clarification artifacts so the classifier can resolve follow-up references
    (e.g. \"option 2\", \"that node\") against prior turn context.

    *graph_reference_map* is a compact ``{node_id: label}`` lookup built from
    the current graph so the classifier can map user references like
    \"the KSampler\" or \"node #3\" to concrete ids.

    *layout_hint* is compact deterministic advisory evidence about current
    canvas readability.  It must never be the sole reason to reroute a
    concrete functional edit to ``reorganise``.
    """
    parts = [f"User request:\n{query}"]
    if has_graph:
        parts.append("\nA ComfyUI canvas graph is attached to this request.")
    if graph_summary:
        parts.append(f"\nGraph summary: {graph_summary}")
    layout_hint_line = _layout_hint_prompt_line(layout_hint)
    if layout_hint_line:
        parts.append(layout_hint_line)

    # ── session context: durable chat messages (backend-owned) ───────────
    if isinstance(session_context, dict):
        recent_messages = session_context.get("recent_messages")
        if isinstance(recent_messages, list) and recent_messages:
            # Use the last 5 durable messages (already capped by
            # _build_session_context → read_session_chat with
            # PROMPT_MEMORY_MESSAGES).  The current user message is
            # prepended separately as ``User request:`` above.
            # Defensively skip any malformed entries (non-dict, missing
            # role, or missing text) so a single corrupt chat artifact
            # cannot poison the entire classify prompt.
            parts.append("\nRecent conversation (for reference resolution):")
            for msg in recent_messages:
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role")
                if not isinstance(role, str) or not role.strip():
                    continue
                content = msg.get("text") or msg.get("content") or ""
                if not isinstance(content, str) or not content.strip():
                    continue
                parts.append(f"[{role}]: {content[:300]}")

        # ── prior clarification artifacts ────────────────────────────────
        prior_clarification = session_context.get("prior_clarification")
        if isinstance(prior_clarification, dict):
            cq = prior_clarification.get("clarification_question")
            co = prior_clarification.get("clarification_options")
            if isinstance(cq, str) and cq.strip():
                parts.append(
                    f"\nPrior clarification question: {cq.strip()[:200]}"
                )
            if isinstance(co, (list, tuple)) and co:
                opts = "\n".join(
                    f"  {i+1}. {str(o)[:200]}"
                    for i, o in enumerate(co)
                    if isinstance(o, str) and o.strip()
                )
                if opts:
                    parts.append(f"Prior clarification options:\n{opts}")

        # ── blocked route context ────────────────────────────────────────
        prior_route = session_context.get("prior_route")
        prior_task = session_context.get("prior_task")
        if isinstance(prior_route, str) and prior_route.strip():
            parts.append(
                f"\nThe previous turn was blocked on route=\"{prior_route}\""
                + (f", task=\"{prior_task}\"" if isinstance(prior_task, str) and prior_task.strip() else "")
                + ". The user's follow-up should be classified with this "
                + "original intent in mind."
            )

        # ── latest candidate reference ──────────────────────────────────
        latest_candidate = session_context.get("latest_candidate")
        if isinstance(latest_candidate, dict):
            candidate_bits: list[str] = []
            turn_id = latest_candidate.get("turn_id")
            if isinstance(turn_id, str) and turn_id.strip():
                candidate_bits.append(f"turn={turn_id.strip()[:80]}")
            outcome = latest_candidate.get("outcome")
            if isinstance(outcome, dict) and isinstance(outcome.get("kind"), str):
                candidate_bits.append(f"outcome={outcome['kind'].strip()[:80]}")
            change_details = latest_candidate.get("change_details")
            operations = (
                change_details.get("operations")
                if isinstance(change_details, dict)
                else None
            )
            if isinstance(operations, list) and operations:
                summaries = []
                for op in operations[:4]:
                    if not isinstance(op, dict):
                        continue
                    summary = op.get("summary") or op.get("field_path")
                    if isinstance(summary, str) and summary.strip():
                        summaries.append(summary.strip()[:120])
                if summaries:
                    candidate_bits.append("changes=" + "; ".join(summaries))
            if candidate_bits:
                parts.append(
                    "\nLatest candidate reference (use this only for unique "
                    "follow-up references like \"that one\"):\n  "
                    + ", ".join(candidate_bits)
                )

    # ── graph reference map ──────────────────────────────────────────────
    if isinstance(graph_reference_map, dict) and graph_reference_map:
        ref_lines = []
        schema_fragile_labels: list[str] = []
        for node_id, label in sorted(graph_reference_map.items(), key=lambda kv: _ref_sort_key(kv[0])):
            label_text = str(label)
            ref_lines.append(f"  id={node_id}: {label_text}")
            if _looks_schema_fragile_label(label_text):
                schema_fragile_labels.append(f"id={node_id}: {label_text}")
        if ref_lines:
            parts.append(
                "\nCurrent graph node reference map (use these ids to resolve "
                "\"that node\", \"the KSampler\", etc.):\n"
                + "\n".join(ref_lines[:30])
            )
        if schema_fragile_labels:
            parts.append(
                "\nSchema-fragile/custom node hint (if the requested edit touches "
                "or depends on these classes, route adapt and use the exact class "
                "names only as anchors for workflow/community precedent research):\n"
                + "\n".join(schema_fragile_labels[:20])
            )

    return [
        {"role": "system", "content": _CLASSIFY_SYSTEM},
        {"role": "user", "content": "\n".join(parts)},
    ]


def _layout_hint_prompt_line(layout_hint: Mapping[str, Any] | None) -> str:
    if not isinstance(layout_hint, Mapping):
        return ""

    fields = {
        "verdict": _compact_hint_value(layout_hint.get("verdict")),
        "overlap": _compact_hint_value(layout_hint.get("overlap_signal")),
        "backward_edges": _compact_hint_value(layout_hint.get("backward_edge_signal")),
        "spacing_group_helper": _compact_hint_value(
            layout_hint.get("spacing_group_helper_signal")
        ),
        "review_hostile": _compact_bool_value(layout_hint.get("review_hostile")),
    }
    if not all(fields.values()):
        return ""

    return (
        "\nDeterministic layout hint (advisory; do not route concrete "
        "functional edits to reorganise solely from this hint): "
        + "; ".join(f"{key}={value}" for key, value in fields.items())
    )


def _compact_hint_value(value: Any, *, limit: int = 120) -> str:
    if not isinstance(value, str):
        return ""
    compact = " ".join(value.split())
    if not compact:
        return ""
    return compact[:limit]


def _compact_bool_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower()
    return ""


def _ref_sort_key(node_id: str) -> tuple[int, str]:
    """Sort node ids numerically when possible, for stable reference maps."""
    try:
        return (0, str(int(node_id)).zfill(8))
    except (ValueError, TypeError):
        return (1, node_id)


def _looks_schema_fragile_label(label: str) -> bool:
    """Heuristic hint for class families where local schema may be incomplete."""
    text = str(label)
    lower = text.lower()
    branded_markers = (
        "qwen",
        "animatediff",
        "ade_",
        "vhs_",
        "reactor",
        "ipadapter",
        "ip-adapter",
        "easy ",
        "rgthree",
        "inspire",
        "wan",
        "vace",
        "ltx",
        "rodin",
        "gguf",
        "faceswap",
        "face swap",
        "modelscope",
    )
    if any(marker in lower for marker in branded_markers):
        return True
    # Core ComfyUI classes are usually simple CamelCase without symbols/spaces.
    # Spaces, slashes, emoji/punctuation, or lowercase prefixes often identify
    # custom-pack nodes whose widgets/slots need exact schema hydration.
    return any(ch in text for ch in (" ", "/", "|", "+", "-", "✨", "//"))


# ── reply prompt ─────────────────────────────────────────────────────────────

_REPLY_SYSTEM = (
    "You are a helpful assistant replying to a user of a ComfyUI canvas editor.\n"
    "The executor has already completed any research and graph editing phases.\n"
    "Your job is to produce a clear, concise user-facing reply.\n\n"
    "Return ONLY a JSON object with this key:\n"
    '  "reply": string — the user-facing message. The string may use readable '
    "lightweight Markdown such as short paragraphs, bullet lists, emphasis, "
    "and inline code while the wire format remains JSON.\n"
    "\n"
    "Rules:\n"
    "- Acknowledge what was done (if anything).\n"
    "- Be concrete: mention node names, template names, or parameter values "
    "when relevant.\n"
    "- Route-aware behavior: for route=\"clarify\", ask the clarifying question "
    "plainly and do not imply work has run; for route=\"respond\", answer from "
    "existing context only; for route=\"inspect\", explain the current graph "
    "from inspection evidence only; for route=\"research\", summarize the "
    "research findings without implying an edit; for route=\"revise\", describe "
    "the concrete graph edit; for route=\"reorganise\", describe the layout "
    "cleanup without implying semantic workflow changes; for route=\"adapt\", "
    "explain how the researched precedent informed the edit.\n"
    "- Prefer 1-3 sentences for simple status replies. For inspect-only or "
    "explain-style replies, use enough structure to stay readable instead of "
    "compressing everything into one paragraph.\n"
    "- Do NOT use fenced code blocks in the reply string.\n"
    "- Do NOT mention internal gate names, phase gates, provider routes, "
    "candidate engines, scoped diffs, rebaseline steps, or deterministic "
    "no-candidate filler.\n"
    "- For non-applyable routes (clarify, respond, inspect, research), do not "
    "use apply/review/rebaseline language, do not say a candidate is ready, "
    "and do not ask the user to approve an edit.\n"
    "- If research findings are present and implementation ran, include one brief "
    "reason the chosen approach/source informed the edit. Do not dump the research "
    "summary.\n"
    "- Mention prioritization, ratings, trust, or quality scores only when that "
    "metadata is explicitly present in the research findings.\n"
    "- For route=\"adapt\" replies, mention the source template/workflow, the "
    "anchor roles bound, the structural validation result, and any portability "
    "warnings; keep the detailed candidate graph in the structured artifact.\n"
    "- If nothing was changed, explain why clearly.\n"
    "- When a graph inspection is provided (inspect route): describe the "
    "graph structure, node types, and how they connect. Explain what the workflow "
    "does step-by-step. Use short paragraphs and/or bullet lists, and use inline "
    "code for node names, parameter names, and widget values when it improves "
    "readability. Do NOT suggest edits or changes — only explain the current "
    "graph. Use node names and widget values from the inspection evidence.\n"
    "- Do NOT include JSON wrapping outside of the required object.\n"
    "- The response must be a single JSON object; no markdown fences, no commentary."
)


def build_reply_messages(
    query: str,
    *,
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    research_sources: tuple[dict[str, Any], ...] | None = None,
    research_warnings: tuple[str, ...] | None = None,
    research_precedent_slices: tuple[dict[str, Any], ...] | None = None,
    implementation_message: str | None = None,
    graph_summary: str | None = None,
    graph_inspection: str | None = None,
    adaptation_plan: dict[str, Any] | None = None,
    effective_route: str | None = None,
    effective_task: str | None = None,
    candidate_present: bool = False,
) -> list[dict[str, str]]:
    """Build system + user messages for the reply phase.

    *plan*, *research_summary*, *implementation_message*, *graph_summary*, and
    *graph_inspection* provide the context the model needs to write an informed
    reply.

    When *graph_inspection* is provided (inspect-only route), it supplies
    detailed node-by-node structure that the model should describe without
    suggesting edits.

    *adaptation_plan* is the serialized :class:`PrecedentAdaptationPlan` for
    route="adapt" requests; the reply should reference it at a high level while
    leaving the detailed candidate graph in the structured artifact.

    *effective_route* and *effective_task* supply the canonical route/task for
    per-route reply tailoring.  *research_sources* is the deduplicated source
    list from the research phase.  *research_warnings* carries non-fatal
    research warnings (e.g. Hivemind timeout) so the reply can acknowledge
    degraded results.  *research_precedent_slices* provides structured evidence
    from the research phase (only for research/adapt routes).

    *candidate_present* indicates whether a graph edit candidate was produced.
    """
    parts = [f"User request:\n{query}"]
    if graph_inspection:
        parts.append(
            f"\nGraph inspection (describe the workflow without suggesting edits):\n{graph_inspection}"
        )
    elif graph_summary:
        parts.append(f"\nAttached workflow graph: {graph_summary}")
    if effective_route:
        parts.append(f"\nActive route: {effective_route}"
                     + (f", task: {effective_task}" if effective_task else ""))
    if plan is not None:
        parts.append(f"\nExecutor plan: {plan.plan_summary or 'completed'}")
    if candidate_present:
        parts.append("\nA graph edit candidate was produced and is available for review.")
    if research_summary:
        parts.append(f"\nResearch findings: {research_summary}")
    if research_sources:
        source_lines = [
            f"  - {src.get('title', src.get('label', 'unnamed'))}"
            for src in research_sources[:8]
        ]
        if source_lines:
            parts.append("Research sources:\n" + "\n".join(source_lines))
    if research_warnings:
        warning_lines = [f"  - {w}" for w in research_warnings[:6]]
        if warning_lines:
            parts.append("Research warnings (non-fatal):\n" + "\n".join(warning_lines))
    if research_precedent_slices:
        slice_summaries = [
            f"  - {s.get('source_class_type', 'unnamed')}"
            + (f" ({len(s.get('node_ids', ())) or 0} nodes)" if isinstance(s.get('node_ids'), (list, tuple)) and s.get('node_ids') else "")
            for s in research_precedent_slices[:5]
        ]
        if slice_summaries:
            parts.append("Research structured evidence (precedent slices):\n" + "\n".join(slice_summaries))
    if implementation_message:
        parts.append(f"\nImplementation: {implementation_message}")
    if adaptation_plan:
        actionability = adaptation_plan_actionability_payload(adaptation_plan)
        if actionability.get("actionability") == "non_actionable":
            parts.append(
                "\nAdaptation plan: non-actionable "
                f"({actionability.get('non_actionable_reason', 'no concrete edits')}). "
                "Do not treat it as implementation guidance."
            )
        else:
            # Emit context_note first if present (neutrality disclaimer).
            context_note = adaptation_plan.get("context_note")
            if isinstance(context_note, str) and context_note.strip():
                parts.append(f"\n{context_note.strip()}")
            selected = adaptation_plan.get("selected_slice") or {}
            bindings = adaptation_plan.get("anchor_bindings") or []
            roles = ", ".join(sorted({b.get("anchor_role", "") for b in bindings if b.get("anchor_role")}))
            parts.append(
                f"\nAdaptation plan (reference context - not a winner): "
                f"reference slice '{selected.get('source_class_type', 'unknown')}', "
                f"bound anchor roles: {roles or 'none'}, "
                f"structural_validation={adaptation_plan.get('structural_validation', 'not_evaluated')}, "
                f"semantic_validation={adaptation_plan.get('semantic_validation', 'not_evaluated')}."
            )
    return [
        {"role": "system", "content": _REPLY_SYSTEM},
        {"role": "user", "content": "\n".join(parts)},
    ]


# ── response parsers ─────────────────────────────────────────────────────────

# Matches a JSON object that starts with { and ends with } across lines.
# More permissive than the top-level json.loads so we can extract from
# model output that may have stray whitespace or a trailing period.
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first JSON object from potentially noisy model output.

    Strips markdown fences, trims surrounding whitespace, and falls back to
    regex extraction before handing off to ``json.loads``.
    """
    stripped = text.strip()
    # Strip outermost ``` fences (with or without ``json`` language tag).
    if stripped.startswith("```"):
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", stripped, re.DOTALL)
        if match:
            stripped = match.group(1).strip()

    # Try direct parse first (fast path).
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Fall back to regex extraction: find the first { ... } span.
    match = _JSON_OBJECT_RE.search(stripped)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract a JSON object from: {text[:200]!r}")


def parse_classify_response(raw: str) -> ClassifyDecision:
    """Parse a classify model response into a :class:`ClassifyDecision`.

    Accepts valid JSON and recovers from common model mistakes (fences,
    trailing text).  Raises :class:`ValueError` for unparseable output.
    """
    parsed = _extract_json_object(raw)

    research = parsed.get("research")
    implement = parsed.get("implement")
    reply = parsed.get("reply")
    effort = parsed.get("effort")
    plan_summary = parsed.get("plan_summary")
    intent = parsed.get("intent")
    route = parsed.get("route")
    task = parsed.get("task")
    research_goal = parsed.get("research_goal")
    search_directions = parsed.get("search_directions")
    source_preferences = parsed.get("source_preferences")
    avoid = parsed.get("avoid")
    known_graph_context = parsed.get("known_graph_context")
    model_families = parsed.get("model_families")
    pattern_category = parsed.get("pattern_category")
    change_goal = parsed.get("change_goal")
    clarification_question = parsed.get("clarification_question")
    clarification_options = parsed.get("clarification_options")

    # Coerce booleans; missing keys default to sensible values.
    if not isinstance(research, bool):
        research = bool(research)
    if not isinstance(implement, bool):
        implement = bool(implement)
    if not isinstance(reply, bool):
        reply = True  # default: always reply
    if not isinstance(effort, str) or effort not in ("low", "medium", "high"):
        effort = "low"
    if not isinstance(plan_summary, str):
        plan_summary = ""
    if not isinstance(intent, str) or intent not in ("edit", "research", "explain_graph", "respond"):
        # Derive intent from legacy boolean fields for backward compatibility.
        if implement:
            intent = "edit"
        elif research:
            intent = "research"
        else:
            intent = "respond"

    # Normalize route: store as-is; derivation happens in effective_route property.
    if not isinstance(route, str):
        route = ""
    route = route.strip()

    # Normalize task: store as-is; derivation happens in effective_task property.
    if not isinstance(task, str):
        task = ""
    task = task.strip()

    # Normalize new metadata fields.
    if not isinstance(research_goal, str):
        research_goal = ""
    research_goal = research_goal.strip()
    if not isinstance(search_directions, list):
        search_directions = []
    search_directions = tuple(
        str(item).strip()
        for item in search_directions
        if isinstance(item, str) and item.strip()
    )
    if not isinstance(source_preferences, list):
        source_preferences = []
    source_preferences = tuple(
        str(item).strip()
        for item in source_preferences
        if isinstance(item, str) and item.strip()
    )
    if not isinstance(avoid, list):
        avoid = []
    avoid = tuple(
        str(item).strip()
        for item in avoid
        if isinstance(item, str) and item.strip()
    )
    if not isinstance(known_graph_context, str):
        known_graph_context = ""
    known_graph_context = known_graph_context.strip()
    if not isinstance(model_families, list):
        model_families = []
    model_families = tuple(str(f) for f in model_families if isinstance(f, str) and f.strip())
    if not isinstance(pattern_category, str):
        pattern_category = ""
    pattern_category = pattern_category.strip()
    if not isinstance(change_goal, str):
        change_goal = ""
    change_goal = change_goal.strip()
    if not isinstance(clarification_question, str):
        clarification_question = ""
    clarification_question = clarification_question.strip()
    if not isinstance(clarification_options, list):
        clarification_options = []
    clarification_options = tuple(str(o) for o in clarification_options if isinstance(o, str) and o.strip())

    return ClassifyDecision(
        research=research,
        implement=implement,
        reply=reply,
        effort=effort,
        plan_summary=plan_summary.strip(),
        intent=intent,
        route=route,
        task=task,
        research_goal=research_goal,
        search_directions=search_directions,
        source_preferences=source_preferences,
        avoid=avoid,
        known_graph_context=known_graph_context,
        model_families=model_families,
        pattern_category=pattern_category,
        change_goal=change_goal,
        clarification_question=clarification_question,
        clarification_options=clarification_options,
    )


def parse_reply_response(raw: str) -> str:
    """Parse a reply model response into a user-facing string.

    Expects ``{"reply": "..."}``.  Returns the reply text or raises
    :class:`ValueError` for unparseable output.
    """
    parsed = _extract_json_object(raw)
    reply = parsed.get("reply")
    if isinstance(reply, str) and reply.strip():
        return reply.strip()
    # Some models use "message" or "response" as the key; try those.
    for key in ("message", "response", "content", "text"):
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError(
        f"Reply model response did not contain a string 'reply' (or fallback) key. "
        f"Got keys: {sorted(parsed.keys())}"
    )


__all__ = [
    "build_classify_messages",
    "build_reply_messages",
    "parse_classify_response",
    "parse_reply_response",
]
