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
from typing import Any

from .contracts import (
    ClassifyDecision,
    adaptation_plan_actionability_payload,
    format_route_options_for_prompt,
    format_task_options_for_prompt,
    parse_target_node_type,
)
from .stage_contracts import NeedsInput

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
    '  "target_node_type": string (optional) — the exact class_type token being '
    "added, changed, or restored; leave blank when unclear.\n"
    '  "needs_input": object or null — typed decision-critical ambiguity. The '
    'object must contain "decision", "question", "missing_information", '
    '"evidence_ids", "options", and optional "bounded_assumption".\n'
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
    "the next safe route cannot be chosen. Emit needs_input with no bounded_assumption.\n"
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
    "- Do not choose route=\"reorganise\" just because the canvas is messy, "
    "overlapping, newly edited, or could benefit from cleanup. Use "
    "route=\"reorganise\" only when the user explicitly asks to organise, "
    "clean up, tidy, arrange, group, lay out, or improve readability of the "
    "workflow/canvas. For functional graph changes, use route=\"revise\" or "
    "route=\"adapt\" and leave layout reorganisation unrequested.\n"
    "- For route=\"research\" and route=\"adapt\", provide tentative research "
    "metadata when useful: research_goal, search_directions, source_preferences, "
    "known_graph_context, and rarely avoid. These fields are retrieval hints, "
    "not findings, implementation instructions, validation tasks, or the answer. "
    "Research metadata must not pre-answer the research question. Use it to "
    "preserve constraints and suggest evidence to seek, not to declare which "
    "implementation families are allowed, forbidden, installed, or required. "
    "Do not claim that a source, node, model, or setting is correct until the "
    "research agent has actually searched.\n"
    "- Source preferences should match the job and the stage's capabilities: "
    "the research stage serves \"hivemind\", \"messages\", and \"workflows\" "
    "only. Use \"workflows\" for change-by-precedent or wiring-pattern "
    "requests; use \"messages\" for community knowledge, usage tips, and "
    "failure-mode questions. \"web\" and \"registry\" are not available as "
    "source tiers in the current stage — node-pack discovery happens through "
    "the registry_lookup tool, and web search is disabled by default; do not "
    "request them as sources.\n"
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
    "- NEVER choose route=\"clarify\" when the graph summary or user request "
    "names a unique matching node (e.g. \"the SaveImage node\"). A concrete "
    "named target is an edit request: route to route=\"revise\" (or "
    "route=\"adapt\" when the target is a custom-node class) and edit it.\n"
    "- When the user asks you to choose, decide, pick defaults, or use your "
    "judgment, do not clarify merely because options exist. Continue with the "
    "most reasonable route, record that choice as needs_input.bounded_assumption, "
    "and summarize it in plan_summary. A bounded assumption must use a non-clarify route.\n"
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
    "- Widget, edge, and single-node-swap intents are route=\"revise\" "
    "(research=false) even when the target is a custom/branded node. Examples: "
    "set a named widget (steps, fps, frame_rate, strength_model, "
    "motion_bucket_id, batch size), add a missing required input edge when "
    "both endpoints already exist, or swap a same-class checkpoint/model "
    "string that is already in the inventory. Do not send these down "
    "route=\"adapt\".\n"
    "- A concrete edit that must invent architecture around a custom-node / "
    "non-core node family (new node classes, ControlNet/IPAdapter chains, "
    "multi-link rewires, named external workflows not already in the graph) "
    "should use route=\"adapt\" rather than route=\"revise\". The research "
    "goal should ask for workflow precedents, wiring patterns, and community "
    "knowledge around the existing class type and the field/socket being "
    "edited. Do not ask research to prove local schema availability or "
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
    "- Exception to the previous rule: if the generic edit must invent "
    "architecture inside a graph dominated by custom class types (new node "
    "classes, multi-link rewires, or a named external workflow not already "
    "present), use route=\"adapt\" with search_directions naming the exact "
    "class type(s), terminal output roles, intended field/socket, and expected "
    "value/change. A named widget, missing required edge, or same-class model "
    "swap on those custom nodes stays route=\"revise\".\n"
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
    "- \"Set VHS_VideoCombine.frame_rate to 16\" with a graph attached -> "
    "route=\"revise\".\n"
    "- \"Switch to generating 16 frames with Hotshot\" when Hotshot is not "
    "already in the graph -> route=\"adapt\".\n"
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
) -> list[dict[str, str]]:
    """Build system + user messages for the classify phase.

    When *has_graph* is True, the executor tells the model a graph is attached
    so it can decide whether research / implementation is warranted.
    *graph_summary* is the renderer's ``census`` lens (batch 12, Law 4) — the
    compact node/class census with the reference map (node ids + class types,
    derived from the IR via the renderer); classify never sees widgets,
    edges, topology, or a raw-JSON sidecar.

    *session_context* provides access to recent conversation history and prior
    clarification artifacts so the classifier can resolve follow-up references
    (e.g. "option 2", "that node") against prior turn context.
    """
    parts = [f"User request:\n{query}"]
    if has_graph:
        parts.append("\nA ComfyUI canvas graph is attached to this request.")
    if graph_summary:
        parts.append(f"\nGraph census (the attached workflow's node/class census):\n{graph_summary}")

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

    return [
        {"role": "system", "content": _CLASSIFY_SYSTEM},
        {"role": "user", "content": "\n".join(parts)},
    ]


# ── reply prompt ─────────────────────────────────────────────────────────────

_REPLY_SYSTEM = (
    "You are a helpful assistant replying to a user of a ComfyUI canvas editor.\n"
    "The executor has already completed any research and graph editing phases.\n"
    "Your job is to produce a clear, concise user-facing reply.\n\n"
    "Write your reply as plain prose.  Lightweight Markdown is fine: short "
    "paragraphs, bullet lists, emphasis, and inline code.  Do NOT wrap the "
    "reply in a fenced code block.  (For backward compatibility with older "
    "clients you MAY instead return a single JSON object with a \"reply\" "
    "string key; plain prose is preferred.)\n\n"
    "Rules:\n"
    "- Acknowledge what was done (if anything).\n"
    "- Be concrete: mention node names, template names, or parameter values "
    "when relevant.\n"
    "Route-aware behavior: for route=\"clarify\", ask the clarifying question "
    "plainly and do not imply work has run; for route=\"respond\", answer from "
    "existing context only; for route=\"inspect\", explain the current graph "
    "from inspection evidence only; for route=\"research\", answer from the "
    "supplied research memo plus the attached graph and your own knowledge "
    "without implying an edit; for route=\"revise\", describe the concrete "
    "graph edit; for route=\"reorganise\", describe the layout cleanup without "
    "implying semantic workflow changes; for route=\"adapt\", explain how the "
    "researched precedent informed the edit (or, when no edit was made, why "
    "nothing was changed).\n"
    "- For route=\"research\", treat the C5 decision memo as evidence you may "
    "cite from: question, conclusion, resolvable citation IDs, "
    "uncertainty/conflicts, and next action. Do not add sources or claims "
    "that are absent from that memo, and never relay the memo verbatim — "
    "answer the user's question in your own words. When the memo records no "
    "external evidence (research_attempt=never/empty), answer directly from "
    "the attached workflow graph and general knowledge — the reply must "
    "NEVER say that no supported conclusion was produced.\n"
    "- Prefer 1-3 sentences for simple status replies. For inspect-only or "
    "explain-style replies, use enough structure to stay readable instead of "
    "compressing everything into one paragraph.\n"
    "- Do NOT use fenced code blocks in the reply.\n"
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
    "- Ground every connectivity claim in the workflow IR you were given: "
    "before asserting that two nodes are connected or that data flows from "
    "one node to another, enumerate the actual links/nodes you traced and "
    "cite the link ids, e.g. \"link 35 connects node 5027 to node 4852\". "
    "Never assert a connection you cannot point to in the provided IR.\n"
    "- Ground every widget/parameter claim in the exact widget key and value "
    "present in the workflow IR, e.g. \"IPAdapterApply widgets are only "
    "[weight=0.7]\". Never invent parameters, modes, or settings that are "
    "absent from the IR; if the IR does not show a parameter, say it is not "
    "present rather than guessing.\n"
    "- Do NOT reply with \"semantics unknowable\", \"cannot be determined\", "
    "or similar refusals when the workflow IR provides labeled inputs, a node "
    "inventory, widget values, or link ids: reason from those provided graph "
    "facts and answer as concretely as the evidence allows. Reserve "
    "\"unknowable\" only for facts the provided evidence genuinely does not "
    "contain.\n"
    "- Never reply with \"no supported conclusion was produced\", \"no usable "
    "synthesis\", or similar research-failure refusals on ANY route. Research "
    "outcome never gates the reply: when research gathered no evidence "
    "(research_attempt=never/empty) or only search-hit leads "
    "(research_attempt=thin), answer from the attached workflow graph and "
    "your own knowledge, and say plainly that outside sources were not found "
    "rather than presenting non-results as findings.\n"
    "- When research produced zero on-topic evidence (for example Hivemind "
    "returned off-topic or failed results), say so explicitly in the reply "
    "instead of presenting those non-results as findings; make claims only "
    "from the workflow IR and the evidence actually provided, never from the "
    "off-topic research records.\n"
)


def build_reply_messages(
    query: str,
    *,
    plan: ClassifyDecision | None = None,
    research_memo: dict[str, Any] | None = None,
    research_ledger: dict[str, Any] | None = None,
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
    interaction_mode: str | None = None,
    research_attempt: str | None = None,
) -> list[dict[str, str]]:
    """Build system + user messages for the reply phase.

    *plan*, *research_summary*, *implementation_message*, *graph_summary*, and
    *graph_inspection* provide the context the model needs to write an informed
    reply.

    *graph_summary* is the composable renderer's ``surface`` + ``diff`` +
    ``topology`` output (batch 12, Law 4) — the complete Python-surface view,
    the accepted Δ (what changed), and the FULL computed topology with link
    ids.  The cite-link preamble attaches to that renderer output: the model
    cites link ids and named fields exactly as the renderer lists them.

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
            "\nGraph inspection (the workflow IR below is the authoritative "
            "source of node ids, widget values, and link ids; describe the "
            "workflow without suggesting edits, and cite link ids and widget "
            "keys/values from it exactly as listed):\n"
            f"{graph_inspection}"
        )
    elif graph_summary:
        parts.append(
            "\nAttached workflow graph (the authoritative source of node ids, "
            "widget values, and link ids — cite link ids and widget "
            "keys/values from it exactly as listed):\n"
            f"{graph_summary}"
        )
    if effective_route:
        parts.append(f"\nActive route: {effective_route}"
                     + (f", task: {effective_task}" if effective_task else ""))
    if plan is not None:
        parts.append(f"\nExecutor plan: {plan.plan_summary or 'completed'}")
    if interaction_mode == "answer_only":
        parts.append(
            "\nInteraction mode: answer_only — this is a diagnosis/advice turn. "
            "No graph edit was made and none is permitted; answer the user's "
            "question directly without suggesting or implying an edit."
        )
    if research_attempt:
        # Batch 14: the typed attempt is the Python-derived statement of what
        # research actually did; it lets the reply answer honestly from the
        # graph + knowledge on never/empty instead of refusing on thin
        # research.
        parts.append(
            f"\nResearch attempt: {research_attempt} (derived from the "
            "research tool ledger — what research actually did, not a "
            "judgment)."
        )
    if candidate_present:
        parts.append("\nA graph edit candidate was produced and is available for review.")
    if research_memo:
        parts.append(
            "\nC5 research decision memo (evidence you may cite from for this "
            "reply — answer the user's question in your own words, do not "
            f"relay the memo verbatim):\n{json.dumps(research_memo, sort_keys=True)}"
        )
    if research_ledger:
        parts.append(
            "\nC1 research ledger (compact evidence handoff only):\n"
            + json.dumps(research_ledger, sort_keys=True)
        )
    if research_summary:
        parts.append(f"\nResearch findings: {research_summary}")
    if research_sources:
        # B04 citation split: hivemind_message sources are cited by
        # author/channel; hivemind_distillation sources by title/status/
        # confidence.  Never invent authors/channels for distillations.
        source_lines: list[str] = []
        for src in research_sources[:8]:
            source_kind = str(src.get("source") or "")
            if source_kind == "hivemind_message":
                author = str(src.get("author") or "").strip()
                channel = str(src.get("channel") or "").strip()
                if author and channel:
                    label = f"{author} in #{channel}"
                elif author:
                    label = author
                elif channel:
                    label = f"#{channel}"
                else:
                    label = str(src.get("title") or src.get("label") or "unnamed")
            elif source_kind == "hivemind_distillation":
                title = str(
                    src.get("title") or src.get("class_type") or "unnamed"
                ).strip()
                status = str(
                    src.get("distillation_status") or "pending"
                ).strip() or "pending"
                confidence = src.get("confidence")
                conf = f"/{confidence}" if confidence not in (None, "") else ""
                label = f"{title} ({status}{conf})"
            else:
                label = str(src.get("title") or src.get("label") or "unnamed")
            source_lines.append(f"  - {label}")
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


# ── two-step execute prompt (B03) ────────────────────────────────────────────
#
# The two-step pipeline replaces research → implement → reply with a single
# bounded execute phase.  One prompt carries every authoritative design
# section: the locked route/plan/query, the current workflow render lenses,
# RESEARCH, PRECEDENT TRANSLATION, EDITING, REPLY, and SELF-CHECK + the final
# contract.  The STAGES AND AVAILABLE TOOLS section is rendered prominently and
# lists exactly the route-allowed catalog (B02 policy) — no union-catalog
# leakage.  The compact accumulated transcript is FLATTENED into the final user
# payload because ``runtime._split_messages`` keeps only the first system and
# last user message; assistant/tool history passed as ordinary messages would
# be silently dropped.

_NON_EDIT_ROUTES = frozenset(
    {"clarify", "respond", "inspect", "research", "requires_custom_nodes"}
)

_TWO_STEP_EXECUTE_SYSTEM_TEMPLATE = (
    "You are the execute agent for a ComfyUI canvas editor's two-step pipeline.\n"
    "The classifier has already locked the route.  Run ONE bounded execute turn\n"
    "for the current message; the turn may span several model continuations.\n"
    "Each continuation returns exactly one host action JSON object (a tool call,\n"
    "a Python edit batch, or the final SUBMIT contract).  Return ONLY that JSON\n"
    "object — no markdown fences, no commentary.\n"
    "\n"
    "STAGES AND AVAILABLE TOOLS\n"
    "==========================\n"
    "Work in exactly this order:\n"
    "\n"
    "1. RESEARCH — gather the evidence this route is allowed to gather.\n"
    "   Available research tools:\n"
    "__RESEARCH_TOOLS__\n"
    "\n"
    "2. CHANGE — prepare the edit with advisory/schema/layout tools.\n"
    "   Available change tools:\n"
    "__CHANGE_TOOLS__\n"
    "   Python editing on this route: __PYTHON_EDITING__.\n"
    "\n"
    "3. SUBMIT — no tools.  Return the final JSON contract only.\n"
    "\n"
    "Tools not listed for your route are DENIED by the host: a call to an\n"
    "unavailable tool is rejected before it runs.  Use only the tools shown\n"
    "above for this exact route.\n"
    "\n"
    "SAME-WINDOW CONTINUITY\n"
    "======================\n"
    "You are ONE thread-continuous session for this chat window.  Prior turns in\n"
    "the same window are supplied in the PRIOR TURNS block of the user payload;\n"
    "use them to resolve follow-up references (\"that node\", \"option 2\", \"the\n"
    "change I asked for\", etc.).  Do not re-derive work already recorded in the\n"
    "transcript, and never cite a Δ id, lens fact id, or evidence id that was\n"
    "not produced in THIS window.\n"
    "__NON_EDIT_NOTE__"
    "FINAL CONTRACT (SUBMIT)\n"
    "=======================\n"
    "Return a single JSON object with these keys:\n"
    "  \"action\": \"submit\"\n"
    "  \"reply\": string — the user-facing prose.\n"
    "  \"delta_ids\": array of strings — accepted Δ ids, in THIS session only.\n"
    "  \"lens_fact_ids\": array of strings — lens fact ids, in THIS session only.\n"
    "  \"evidence_ids\": array of strings — evidence ids, in THIS session only.\n"
    "  \"edit_applied\": true/false.\n"
    "  \"self_check\": {\"research\": \"never|empty|thin|grounded\", \"confidence\":\n"
    "                  string, \"notes\": string}.\n"
    "__NON_EDIT_CONTRACT__"
    "SELF-CHECK\n"
    "==========\n"
    "Before SUBMIT, verify: (1) every cited id exists in this session's ledger;\n"
    "(2) an edit_applied=true contract cites at least one accepted Δ;\n"
    "(3) the reply prose is concrete and never mentions internal gate names;\n"
    "(4) you used no tool outside this route's allowed catalog.\n"
    "\n"
    "CONTINUATION ACTIONS (while working, before SUBMIT)\n"
    "===================================================\n"
    "Return exactly one of:\n"
    "  - Tool call:     {\"action\": \"tool_call\", \"tool\": \"<name>\", \"args\": {...}}\n"
    "  - Python batch:  {\"action\": \"apply\", \"python\": \"<edit statements>\"}\n"
    "  - Final:         the SUBMIT contract above.\n"
)

_TWO_STEP_NON_EDIT_NOTE = (
    "\n"
    "NON-EDIT ROUTE\n"
    "==============\n"
    "This route may not submit any change: delta_ids must be [] and edit_applied\n"
    "must be false.  Do not emit a Python batch or an apply action.\n"
)

_TWO_STEP_NON_EDIT_CONTRACT = (
    "  For THIS non-edit route: \"delta_ids\": [], \"edit_applied\": false.\n"
)


def _two_step_stage_catalogs(route: str, *, web_search_enabled: bool) -> tuple[str, str, bool]:
    """Return (research_docs, change_docs, python_allowed) for *route*.

    The catalogs are the exact route-allowed tools partitioned by phase — never
    the union catalog, and never ``phase=None`` (which would leak implement
    tools into RESEARCH or research tools into CHANGE).
    """
    from vibecomfy.executor.tool_specs import (  # noqa: PLC0415
        PHASE_IMPLEMENT,
        PHASE_RESEARCH,
        tool_catalog_docs,
    )
    from vibecomfy.executor.two_step import (  # noqa: PLC0415
        TWO_STEP_ROUTE_POLICIES,
        effective_route_tools,
    )

    effective = effective_route_tools(route, web_search_enabled=web_search_enabled)
    research = tool_catalog_docs(phase=PHASE_RESEARCH, allowed_names=effective)
    change = tool_catalog_docs(phase=PHASE_IMPLEMENT, allowed_names=effective)
    policy = TWO_STEP_ROUTE_POLICIES[route]
    return research, change, policy.allows_python_edits


def _build_two_step_execute_system(
    route: str, *, web_search_enabled: bool = False
) -> str:
    research, change, python_allowed = _two_step_stage_catalogs(
        route, web_search_enabled=web_search_enabled
    )
    research_text = research if research else "   (none for this route)"
    change_text = change if change else "   (none for this route)"
    python_text = "ALLOWED" if python_allowed else "NOT ALLOWED"
    non_edit = route in _NON_EDIT_ROUTES
    system = _TWO_STEP_EXECUTE_SYSTEM_TEMPLATE
    system = system.replace("__RESEARCH_TOOLS__", research_text)
    system = system.replace("__CHANGE_TOOLS__", change_text)
    system = system.replace("__PYTHON_EDITING__", python_text)
    system = system.replace(
        "__NON_EDIT_NOTE__", _TWO_STEP_NON_EDIT_NOTE if non_edit else ""
    )
    system = system.replace(
        "__NON_EDIT_CONTRACT__", _TWO_STEP_NON_EDIT_CONTRACT if non_edit else ""
    )
    return system


def build_two_step_execute_messages(
    query: str,
    *,
    route: str,
    plan: ClassifyDecision | None = None,
    graph_render: str | None = None,
    research_context: str | None = None,
    precedent_context: str | None = None,
    editing_context: str | None = None,
    transcript: str | None = None,
    web_search_enabled: bool = False,
) -> list[dict[str, str]]:
    """Build system + user messages for one bounded two-step execute turn.

    The system message carries the static design sections (STAGES AND AVAILABLE
    TOOLS, same-window continuity, the final contract, SELF-CHECK).  The user
    message carries the per-turn design sections — route/plan/query, the
    current workflow render lenses, RESEARCH, PRECEDENT TRANSLATION, EDITING,
    REPLY — plus the FLATTENED compact transcript and the new message.  Only
    the route-allowed catalog is rendered (B02 policy); unavailable tools are
    denied by the host.
    """
    system = _build_two_step_execute_system(
        route, web_search_enabled=web_search_enabled
    )
    parts: list[str] = []

    task = plan.effective_task if plan is not None else ""
    plan_summary = plan.plan_summary if plan is not None else ""
    parts.append(
        "ROUTE / PLAN / QUERY\n"
        "--------------------\n"
        f"Active route: {route}\n"
        f"Task: {task or '(none)'}\n"
        f"Plan: {plan_summary or '(none)'}\n"
        f"User request: {query}"
    )

    parts.append(
        "\nCURRENT WORKFLOW (render lenses)\n"
        "--------------------------------\n"
        f"{graph_render if graph_render else '(no graph attached to this request)'}"
    )

    parts.append(
        "\nRESEARCH\n"
        "--------\n"
        f"{research_context if research_context else '(none yet — gather it if the route allows and the request needs it)'}"
    )

    parts.append(
        "\nPRECEDENT TRANSLATION\n"
        "---------------------\n"
        f"{precedent_context if precedent_context else '(none)'}"
    )

    parts.append(
        "\nEDITING\n"
        "-------\n"
        f"{editing_context if editing_context else '(no edit accepted yet in this session)'}"
    )

    parts.append(
        "\nREPLY\n"
        "-----\n"
        "Produce a concrete, user-facing reply in the SUBMIT contract.  Acknowledge\n"
        "what was done; name nodes, templates, or parameters where relevant.  Never\n"
        "mention internal gate names, provider routes, or pipeline stages."
    )

    parts.append(
        "\nPRIOR TURNS (this window)\n"
        "------------------------\n"
        f"{transcript if transcript else '(none — this is the first message in this window)'}"
    )

    parts.append(
        "\nCURRENT MESSAGE\n"
        "---------------\n"
        f"{query}"
    )

    return [
        {"role": "system", "content": system},
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
    target_node_type = parsed.get("target_node_type")
    clarification_question = parsed.get("clarification_question")
    clarification_options = parsed.get("clarification_options")
    needs_input_payload = parsed.get("needs_input")

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
    if not isinstance(target_node_type, str):
        target_node_type = ""
    target_node_type = target_node_type.strip() or parse_target_node_type(change_goal)
    if not isinstance(clarification_question, str):
        clarification_question = ""
    clarification_question = clarification_question.strip()
    if not isinstance(clarification_options, list):
        clarification_options = []
    clarification_options = tuple(str(o) for o in clarification_options if isinstance(o, str) and o.strip())

    decision = ClassifyDecision(
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
        target_node_type=target_node_type,
        clarification_question=clarification_question,
        clarification_options=clarification_options,
    )
    if isinstance(needs_input_payload, dict):
        needs_input = NeedsInput.from_dict(needs_input_payload)
        if decision.effective_route == "clarify" and needs_input.bounded_assumption:
            raise ValueError(
                "A clarify decision cannot also record a bounded assumption."
            )
        object.__setattr__(decision, "needs_input", needs_input)
    return decision


_ITERATION_LIMIT_SENTINEL_PATTERNS: tuple[str, ...] = (
    r"\biteration limit\b",
    r"\btoken limit\b",
    r"\bturn limit\b",
    r"\bmax(?:imum)? iterations?\b",
    r"\btoo many iterations?\b",
    r"\bbudget (?:was )?exhausted\b",
    r"\bexhausted (?:the |my )?(?:turn|token|iteration) budget\b",
    r"\bcouldn'?t generate\b",
    r"\bcould not generate\b",
    r"\bwas (?:unable|not able) to generate\b",
    r"\bfailed to generate\b",
    r"\bcouldn'?t produce\b",
    r"\bcould not produce\b",
    r"\bwas (?:unable|not able) to produce\b",
    r"\bfailed to produce\b",
    r"\bcouldn'?t (?:write|finish|complete|summarize)\b",
    r"\bcould not (?:write|finish|complete|summarize)\b",
)
_ITERATION_LIMIT_SENTINEL_RE = re.compile(
    "|".join(f"(?:{pattern})" for pattern in _ITERATION_LIMIT_SENTINEL_PATTERNS),
    re.IGNORECASE,
)
# A sentinel is a SHORT first-person failure stub ("I reached the iteration
# limit and couldn't generate a summary."), not a real answer that happens to
# mention a limit.  Require a failure admission verb unless the text is very
# short.
_FAILURE_ADMISSION_RE = re.compile(
    r"\b(couldn'?t|could not|was unable|not able to|unable to|failed|ran out)\b",
    re.IGNORECASE,
)
# Short failure stubs are retryable; longer prose mentioning a limit in
# passing is a real answer.
_ITERATION_LIMIT_SENTINEL_MAX_LEN = 200
_ITERATION_LIMIT_SENTINEL_SHORT_MAX_LEN = 80


def _looks_json_shaped(text: str) -> bool:
    """True when model output starts like JSON transport (object or fence)."""
    stripped = text.strip()
    return stripped.startswith("{") or stripped.startswith("```")


def _is_iteration_limit_sentinel(text: str) -> bool:
    """True for short first-person failure stubs that must stay retryable."""
    if not text or len(text) > _ITERATION_LIMIT_SENTINEL_MAX_LEN:
        return False
    if _ITERATION_LIMIT_SENTINEL_RE.search(text) is None:
        return False
    if len(text) <= _ITERATION_LIMIT_SENTINEL_SHORT_MAX_LEN:
        return True
    return _FAILURE_ADMISSION_RE.search(text) is not None


def _sanitize_reply_prose(text: str) -> str:
    """Trim trailing whitespace per line and collapse blank runs in prose."""
    lines = [line.rstrip() for line in str(text).splitlines()]
    cleaned: list[str] = []
    pending_blank = False
    for line in lines:
        if not line.strip():
            if cleaned and not pending_blank:
                cleaned.append("")
                pending_blank = True
            continue
        pending_blank = False
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def parse_reply_response(raw: str) -> str:
    """Parse a reply model response into a user-facing string.

    First tries the legacy JSON transport (``{"reply": "..."}`` plus the
    ``message`` / ``response`` / ``content`` / ``text`` fallback keys) for
    backward compatibility.  When the output is not JSON-shaped, sanitized
    non-empty prose is accepted verbatim.

    Empty output, JSON-looking-but-malformed output, and iteration-limit
    sentinels remain retryable errors (raised as :class:`ValueError`).
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Reply model returned an empty response.")
    stripped = raw.strip()
    if _looks_json_shaped(stripped):
        parsed = _extract_json_object(stripped)
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
    if _is_iteration_limit_sentinel(stripped):
        raise ValueError(
            "Reply model returned an iteration/token-limit stub instead of an "
            f"answer: {stripped[:200]!r}"
        )
    prose = _sanitize_reply_prose(stripped)
    if not prose:
        raise ValueError("Reply model returned an empty response.")
    return prose


__all__ = [
    "build_classify_messages",
    "build_reply_messages",
    "parse_classify_response",
    "parse_reply_response",
]
