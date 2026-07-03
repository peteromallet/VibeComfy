# VibeComfy Code Smell Audit Final Report

Date: 2026-07-03

## Method

- Wave 1: 12 DeepSeek Pro subagents across broad smell categories.
- Wave 2: 10 DeepSeek Pro subagents focused on verification and remediation sequencing.
- Final organizer: Codex `gpt-5.5`, high reasoning, read-only, organized the verified findings into a PR-sized roadmap.
- Direct checks: `git ls-files`, local env scan, and targeted file inspection.

Raw artifacts:
- `.codex/code-smell-audit/results/wave1/`
- `.codex/code-smell-audit/results/wave2/`
- `.codex/code-smell-audit/draft-plan.md`
- `.codex/code-smell-audit/codex-roadmap.md`

## Pressure-Tested Conclusions

- The draft was directionally right, but several items were too broad for one PR.
- Security/env containment should go first, but must include compatibility tests because Comfy/custom-node startup may depend on environment variables.
- Reorganise classifier fixes must land before validation/compile guardrails, otherwise stricter diagnostics can encode current false classifications.
- Performance work should start with bounded guardrails and stress tests, not immediate algorithm rewrites.
- `_compile` import cleanup needs public shims first, call-site migration second, import-linter third.
- Deep `reorganise/compile.py` splitting should stay delayed; tests currently import private internals like `_build_report` and `_score_existing_group`.
- `local_env.sh` is not a repository secret incident. It is untracked and ignored, so keep it as local hygiene only.

## Recommended Roadmap

### PR 1: Runtime Secret Containment

Scope:
- `vibecomfy/runtime/server_process.py`
- `vibecomfy/comfy_nodes/agent/runtime.py`
- `scripts/runpod_corpus_matrix.py`

Changes:
- Add a Comfy subprocess env builder with an explicit allowlist plus a documented extension point.
- Stop serializing raw `api_key` inside worker `request.json`; pass one chosen key via `HERMES_API_KEY` only.
- Stop embedding `HF_TOKEN` in generated shell script text; require/passthrough remote env instead.

Test gates:
- Unit tests proving `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. are absent from Comfy env unless allowlisted.
- Agent runtime test proving temp request JSON excludes raw keys.
- RunPod matrix test proving generated script text does not contain the token value.
- Run `pytest -q tests/test_runpod_matrix.py tests/test_agent_runtime_adapter.py`.

### PR 2: Reorganise Classifier Characterization and Fixes

Scope:
- `vibecomfy/porting/reorganise/classify.py`
- `tests/test_reorganise_classify.py`

Changes:
- Add characterization tests for `control`, `save`, UID-substring output detection, and sibling groups of 3+.
- Tighten heuristics: `save*` or known output classes only, control prefix/known tokens only, target `class_type` for output edges.
- Generalize sibling detection from exactly two to two or more.

Test gates:
- `pytest -q tests/test_reorganise_classify.py`
- `pytest -q tests/test_reorganise_compile.py::test_compile_layout_plan_classifies_simple_t2i_unassigned_nodes_into_sections`

### PR 3: Validation and Compile Guardrails

Scope:
- `vibecomfy/porting/reorganise/validate.py`
- `vibecomfy/porting/reorganise/compile.py`

Changes:
- Add high-unassigned-ratio diagnostics as warnings first.
- Add majority-unassigned compile failure only for larger workflows and only after classifier fixes land.
- Add role-purity diagnostics as warnings, excluding custom/utility/container sections.

Test gates:
- `pytest -q tests/test_reorganise_validate.py tests/test_reorganise_compile.py tests/test_reorganise_goldens.py`
- Include one large synthetic workflow test and assert deterministic JSON output.

### PR 4: Large Workflow Safety

Scope:
- `vibecomfy/porting/layout/reconcile.py`
- `vibecomfy/porting/layout/placement.py`

Changes:
- Add bounded fallback for `_min_cost_assign` collision groups before factorial blowup.
- Rewrite `_toposort_component` to a dependency-count queue.
- Add 100-node stress tests with a wall-clock guard.
- Delay a spatial index for `place_constrained` until stress tests prove it matters.

Test gates:
- `pytest -q tests/test_layout_store.py tests/test_layout_delta.py tests/test_ui_layout.py`
- New stress tests must assert deterministic output and complete under a tight local threshold.

### PR 5: Public Compile Facades

Scope:
- `vibecomfy/_compile/*`
- `vibecomfy/ir/*`
- `vibecomfy/porting/*`
- tests currently importing `_compile`

Changes:
- Create public re-export modules:
  - `vibecomfy.graph_utils`
  - `vibecomfy.widget_schema`
  - `vibecomfy.ir.resolve`
  - likely `vibecomfy.helpers`
- Migrate non-internal call sites incrementally.
- Keep `_compile` compatibility shims; do not delete yet.
- Add an import-boundary test before adding import-linter enforcement.

Test gates:
- `pytest -q tests/test_foundation_utils.py tests/test_helper_resolve.py tests/test_widget_aliases.py`

### PR 6: Router and CLI UX

Scope:
- `vibecomfy/router/_core.py`
- `vibecomfy/commands/agentic.py`
- `tests/test_router.py`
- `tests/test_cli_misc.py`

Changes:
- Add `list_routes()` / `describe()` and richer `KeyError` guidance.
- Document default route choices in returned metadata or CLI help.
- Treat `agentic` as a product decision: real dispatcher or explicit deprecated pointer with unambiguous messaging.

Test gates:
- `pytest -q tests/test_router.py tests/test_cli_misc.py`

### PR 7: Ingest Contracts, Permissive by Default

Scope:
- `vibecomfy/ingest/normalize.py`
- likely IR/contract type surfaces for node IDs and metadata documentation.

Changes:
- Add `Literal` shape typing and document metadata core.
- Add opt-in `strict=True` returning structured issues for missing `class_type`, non-dict `inputs`, and ambiguous shape.
- Keep default behavior unchanged for community workflow compatibility.

Test gates:
- `pytest -q tests/test_porting_normalize_ingest.py tests/test_ingest_snapshot.py tests/test_exec_normalize.py`

### PR 8: Test Gate Hygiene

Changes:
- Add `fast`/`slow` markers or replace hardcoded `FAST_PYTEST` gradually.
- Pull pure reorganise classifier/validate/parse tests into fast.
- Keep goldens, characterization, and corpus tests slow.

Test gates:
- `make fast`
- `pytest -q tests/test_reorganise_classify.py tests/test_reorganise_validate.py tests/test_reorganise_plan_parse.py`

## Immediate Fixes

- Runtime secret containment.
- RunPod token script embedding.
- Reorganise classifier false positives.
- Factorial assignment bailout.
- Router error guidance.

## Delay or Verify Further

- Deep `compile.py` splitting.
- Strict ingest by default.
- `place_constrained` spatial index.
- Large `scripts/` and `tools/` package migration.
- Legacy agent env-var removal.
- Full snapshot deduplication.

## Dropped Finding

Do not treat local `local_env.sh` as a repository secret incident. It is untracked and ignored; keep it as local hygiene only.
