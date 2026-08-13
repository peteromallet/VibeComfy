Implement the approved agent-judgment informational-research path through B01–B05. B06 is the optional web-reliability follow-up. Code transports, normalizes, deduplicates, displays, remembers, hoists, and cites evidence; the agent alone chooses queries and decides whether to search again or call `done()`.

Do not add deterministic loops/iteration, adapt-route message defaults, distillation write-back, FTS, reaction ranking, prefetch, term expansion, relevance scoring, evidence cards, latches, research-call caps, wall-clock stops, or research-only `max_batches=4`. Do not create `vibecomfy/executor/research_iteration.py`.

The worktree has no venv yet. Use `uv run --frozen ...`.

Every batch ends in exactly one binary, read-only oracle checkpoint. Rework the owning batch until `PASS`; do not start batch N+1 until batch N passes.

## B01 — Messages Hivemind client

1. Create `vibecomfy/executor/hivemind_clients.py` with `_hivemind_get_table`, preserving the workflow-client `external_resources?kind=eq.workflow` behavior through `_default_hivemind_client`.

2. Implement `_CHANNEL_GROUPS`, `_FAMILY_TO_GROUP`, `_channel_scope_for_query`, `_distinctive_tokens`, and `_hivemind_single_or_phrase_ilike`. Include `live_updates` and `minimax_h3_chatter`; keep single-token queries and version tokens.

3. Implement `_default_hivemind_messages_client` with:
   - Step A: `unified_feed`, `kind=eq.distillation`.
   - Step B: `unified_feed`, `kind=eq.message`.
   - Step C: channel-scoped `message_feed` when `_raw_message_hits_are_thin`.
   - Step D: channel-scoped individual-token OR fill.
   - Timeout recovery through `daily_summaries`, the densest topic group, and optional 90-day scope.
   - No FTS, unfiltered `limit=1000`, 3-gram expansion, or `external_resources` message search.

4. Implement `_raw_message_hits_are_thin`, `_hivemind_item_id`, `_message_dedupe_key`, `_normalize_hivemind_message_source`, and `_run_hivemind_messages_research`. Keep the runner normalize-only; never fetch Discord attachment URLs as workflow JSON.

5. Implement approved-distillations → pending-distillations → recency display order, dedupe by string ID, and the 12-source presentation cap. Do not implement `_rank_message_rows`, IDF filtering, `score <= 0` filtering, or reaction ranking.

6. Implement `format_community_summary` with extractive message and distillation formatting, six-item/~800-character bounds, and the empty-result sentence.

7. Move/re-export `_default_hivemind_client`, `_query_tokens`, `_QUERY_TOKEN_RE`, `_SEARCH_STOPWORDS`, and `_HIVEMIND_FALLBACK_STOPWORDS` through `vibecomfy/executor/research.py` so existing imports and patches remain valid. Add `hivemind_message` and `hivemind_distillation` to `_source_tier_for_source` / `_TIER_TTL_MAP`; update `_build_summary` for message-only results without `WORKFLOW_RESEARCH_GUIDANCE`.

8. Add `tests/test_executor_hivemind_messages.py` covering table/parameter shapes, raw thinness, channel fallback, `live_updates`, string snowflakes, normalize-only behavior, approved-then-recency ordering, low-IDF row retention, and raw MiniMax-H3 Step-D token matching.

### B01 checkpoint — binary read-only oracle

Acceptance criteria:

- `uv run --frozen pytest tests/test_executor_hivemind_messages.py tests/test_executor_research.py -x -q` passes.
- `uv run --frozen pytest tests/ -x -q` passes.
- Existing workflow-client URL and `kind=eq.workflow` assertions remain unchanged and green.
- Fixtures prove message/distillation sources are normalized, deduplicated, ordered, and capped at 12.
- A low-IDF on-topic row remains visible.
- No workflow-JSON fetch occurs for message attachment URLs.
- No deterministic-loop artifacts or `vibecomfy/executor/research_iteration.py` exist.
- Verdict: `PASS` or owning-batch rework.

## B02 — `sources=` tier gating

1. Extend `vibecomfy/executor/research.py::research` additively with `sources: tuple[str, ...] | None` and `hivemind_messages_client`.

2. Implement `run_workflows`, `run_messages`, `run_web`, and `run_registry` exactly from `sources`; retain legacy behavior for `sources is None` with messages disabled.

3. Wire `_run_hivemind_messages_research` only when the messages tier is enabled. Ensure explicit messages-only research sets effective `local_limit=0` and skips workflow Hivemind, web, and registry.

4. Implement `VIBECOMFY_MESSAGES_RESEARCH=0` as a messages-client kill switch with warning `"messages tier disabled"`.

5. Update `vibecomfy/porting/edit/_resolve.py::_resolve_query_statement` to split `_default_hivemind_client` from `_default_hivemind_messages_client`. Keep the omitted-source default exactly `("workflows",)` in this batch.

6. Extend `tests/test_executor_research.py` and `tests/test_porting_edit_resolve.py` for the tier matrix, legacy public behavior, single invocation with the original query string, explicit messages/web combinations, and the environment kill switch.

### B02 checkpoint — binary read-only oracle

Acceptance criteria:

- `uv run --frozen pytest tests/test_executor_research.py tests/test_porting_edit_resolve.py -x -q` passes.
- `uv run --frozen pytest tests/ -x -q` passes.
- `sources=("messages",)` invokes the messages fake once with the unchanged user query and invokes no workflow, web, registry, or local tier.
- Public `research("Hotshot XL")` does not invoke the messages client.
- REPL omission still resolves to `("workflows",)`.
- Existing invalid-explicit-source diagnostics remain unchanged.
- No expansion, scoring, latch, retry-by-evidence, network-call-cap, or research-only four-turn artifacts exist.
- Verdict: `PASS` or owning-batch rework.

## B03 — Research-route omit default, prompt, followup, and memory

1. Create `vibecomfy/executor/research_sources.py` with `_ALLOWED_RESEARCH_TIERS`, `_RESEARCH_SOURCE_ALIASES`, `canonicalize_research_sources`, and `resolve_repl_research_sources`. Treat `None` and `()` as omission; research-only omission resolves to `("messages", "web")`, other omission to `("workflows",)`, and explicit non-empty sources win without union.

2. Add `community_summary: str = ""` to `vibecomfy/executor/contracts.py::ResearchResult`; emit it from `to_dict()` only when non-empty.

3. Update `vibecomfy/executor/research.py::research` to assign `format_community_summary(...)` whenever the messages tier ran, including the empty-result sentence.

4. [XHARD] In `vibecomfy/comfy_nodes/agent/edit_batch_repl.py`, compute `canonical_route` and `research_only_route` before constructing `EditSession`; assign `session.research_only` and `session.executor_research_brief`. Add `_dedupe_sources_by_id` and `_fold_research_statement`, and fold live `StatementResult.detail` after resolution. Do not add latch attributes or alter the existing `max_batches` calculation.

5. Update `vibecomfy/porting/edit/_resolve.py::_resolve_query_statement` to call `resolve_repl_research_sources`, pass the split clients and resolved `sources`, and attach `research_result_sources`, `community_summary`, and `research_summary` to `StatementResult.detail`.

6. Update `vibecomfy/porting/edit/_resolve.py::_format_research_query_output` to print `community_summary`, author/channel or distillation metadata, warnings, and up to 12 sources when message kinds are present.

7. Update `vibecomfy/porting/edit/_resolve.py::_research_followup_guidance` with static `_MESSAGES_FOLLOWUP`, gated by:
   `messages` present and `workflows`/`registry` absent.
   Messages+web must suppress workflow guidance; web-only must retain External workflow check.

8. [XHARD] Add `collected_research_sources`, `collected_research_summary`, and `collected_community_summary` to `vibecomfy/comfy_nodes/agent/_frag_state.py::AgentEditState`. Do not add `collected_evidence_card`.

9. [XHARD] Update `vibecomfy/comfy_nodes/agent/_frag_batch_memory.py::_batch_research_memory_summary` to retain any `research_query`, message/distillation markers, community summaries, and up to five optional `search_directions`.

10. Update `vibecomfy/comfy_nodes/agent/provider.py` research-only prompt: document messages+web omission, omit graph-construction instructions and the four-turn apply-edit cap, and instruct the agent to judge search-again versus `done()`.

11. Update `vibecomfy/executor/core.py::_research_brief_from_plan` canned `avoid` text to forbid invented community consensus.

12. Add `tests/test_executor_research_sources.py`; extend `tests/test_executor_research.py`, `tests/test_porting_edit_resolve.py`, and `tests/test_comfy_nodes_agent_edit.py` for omission, explicit override, community summaries, detail folding, followup routing, 12-source output, memory persistence, and candidate-term visibility.

### B03 checkpoint — binary read-only oracle

Acceptance criteria:

- `uv run --frozen pytest tests/test_executor_research_sources.py tests/test_executor_research.py tests/test_porting_edit_resolve.py tests/test_comfy_nodes_agent_edit.py -x -q` passes.
- `uv run --frozen pytest tests/ -x -q` passes.
- Research-only `None`, `()`, and `sources=[]` resolve to `("messages", "web")`; adapt omission remains `("workflows",)`.
- Explicit `("web",)` and `("workflows",)` are not unioned with messages.
- Classify `source_preferences` remain prompt-visible and are not executed.
- Message results survive into next-turn memory and structured `StatementResult.detail`.
- Messages+web produces only static messages guidance; web-only retains workflow-JSON guidance.
- Existing `max_batches = max(1, int(state.batch_max_turns or 1))` remains; no research-only cap exists.
- No `evidence_card`, strength field, latch, tried-query state, query expansion, or search-direction execution exists.
- Verdict: `PASS` or owning-batch rework.

## B04 — Hoist and research reply path

1. [XHARD] Update `vibecomfy/comfy_nodes/agent/_frag_response_contract.py::_build_batch_repl_response` immediately before `build_legacy_agent_edit_v1` to stamp `research_findings` for the research route. Re-synthesize `summary` and `community_summary` with `format_community_summary` from the deduplicated collected union, capped at 12, with warnings. Preserve `graph_unchanged=True` and `no_candidate_reason="route_not_applyable"`.

2. [XHARD] Add `vibecomfy/executor/core.py::_research_result_from_findings` and hoist findings immediately after `_run_implement`.

3. [XHARD] Change `vibecomfy/executor/core.py::run_executor` so `_implementation_result_is_terminal_no_candidate(...)` does not take the early-return shortcut when `_canonical_route_for_plan(plan) == "research"`. Preserve all inspect, clarify, and non-research noop shortcuts; ensure the research route reaches `_run_reply`.

4. Update `vibecomfy/executor/core.py::_run_reply` to prefer `ResearchResult.community_summary` over `summary`.

5. Update `vibecomfy/executor/prompts.py::build_reply_messages` to cite `hivemind_message` by author/channel and `hivemind_distillation` by title/status/confidence.

6. Update `vibecomfy/executor/prompts.py::_REPLY_SYSTEM` so research replies do not lead with graph-change narration and cannot invent community consensus or citations.

7. Extend `tests/test_executor_flows.py` with research hoist, community-summary preference, and `test_research_route_terminal_no_candidate_still_runs_reply`.

8. Extend `tests/test_executor_contracts.py` with message and distillation citation-shape tests and the research-route reply instruction.

### B04 checkpoint — binary read-only oracle

Acceptance criteria:

- `uv run --frozen pytest tests/test_executor_flows.py tests/test_executor_contracts.py tests/test_comfy_nodes_agent_edit.py -x -q` passes.
- `uv run --frozen pytest tests/ -x -q` passes.
- A terminal-no-candidate research fixture invokes `run_reply_turn`; its user reply is not `implementation_result.message` or “No graph changes were needed.”
- Hoisted `report.research.sources` contains `source=="hivemind_message"` and `_run_reply` receives `community_summary`.
- Message citations expose author/channel; distillations expose title/status/confidence without invented author/channel.
- Live MiniMax H3 and LTX 2.5 probes run at least one model-authored `research()` statement and return message-kind sources from `minimax_h3_chatter`, `ltx_chatter`, `live_updates`, or `daily_summaries`, or a real distillation title/status.
- Live replies cite those sources and do not lead with workflow-template or no-graph-change narration.
- `_should_prefetch_research` remains false for the research route.
- No deterministic-loop artifacts exist.
- Verdict: `PASS` or owning-batch rework.

## B05 — Real batch-REPL integration

1. Add a real `EditSession` integration test in `tests/test_porting_edit_resolve.py` and/or `tests/test_executor_flows.py` with `session.research_only=True` and a fixture model emitting `research("LTX 2.5")` without `sources=`, then `done()`.

2. Patch both `vibecomfy.executor.research._default_hivemind_messages_client` and `vibecomfy.executor.research._default_web_search_client`; use a raw `hivemind_message` fixture for `alice` in `ltx_chatter` and a no-op web result.

3. Assert resolution to `("messages", "web")`, one unchanged `"LTX 2.5"` client call, structured message sources, author/channel query output, static followup text, and live-detail folding into `state.collected_research_sources`.

4. Assert the durable response stamps `research_findings`, `report.research` contains the message source, `run_reply_turn` receives `alice`/`ltx_chatter`, `graph_unchanged=true`, and `apply_eligible=false`.

5. Assert the user-facing reply is not the narrator line and `messages.jsonl` contains one outer `research()` statement.

6. If adding a two-search fixture, assert the client is called twice; never assert that code skips the second call.

### B05 checkpoint — binary read-only oracle

Acceptance criteria:

- `uv run --frozen pytest tests/test_porting_edit_resolve.py tests/test_executor_flows.py -x -q` passes.
- `uv run --frozen pytest tests/ -x -q` passes.
- The integration uses a real `EditSession` and real resolution/fold/hoist plumbing, not hand-populated collected state.
- Both external clients are patched; CI performs no live web request.
- Omitted sources resolve to messages+web and produce a message-kind source through the final reply.
- `messages.jsonl` proves the query was model-authored and not expanded by code.
- Repeated model-authored research calls are not suppressed by latches or caps.
- No deterministic-loop artifacts exist.
- Verdict: `PASS` or owning-batch rework.

## B06 — Optional web 429 backoff and cache TTL

1. Update `vibecomfy/executor/research.py::_default_web_search_client` to retry Brave once after 0.8 seconds on 429, then install a 15-minute skip sentinel; apply the specified 403 handling without adding providers.

2. Update the existing web cache read/write path in `vibecomfy/executor/research.py` to store negative results and honor `expires_at`.

3. Extend `tests/test_executor_research.py` with mocked 429/403, retry timing, sentinel, negative-cache, and expiry cases.

4. Keep web reliability independent from message query choice, REPL iteration, source scoring, and stop decisions.

### B06 checkpoint — binary read-only oracle

Acceptance criteria:

- `uv run --frozen pytest tests/test_executor_research.py -x -q` passes.
- `uv run --frozen pytest tests/ -x -q` passes.
- A mocked 429 causes exactly one retry after 0.8 seconds, then a 15-minute skip sentinel.
- Negative cache entries prevent redundant requests until `expires_at`; expired entries are retried.
- No new provider, query expansion, evidence scoring, REPL retry branch, latch, or research-call cap exists.
- Verdict: `PASS` or owning-batch rework.
