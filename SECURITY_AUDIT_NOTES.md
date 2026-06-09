# Security/intent-policy audit notes (wave 9)

The 24-lens audit flagged two HIGH "security bugs". On personal review, BOTH are
**intentional trust distinctions, not vulnerabilities** — deliberately NOT changed
(changing them would break functionality and the trust model).

## A. registry/ready.py:100 — untrusted_source -> user_confirmed promotion for dynamic ready templates
VERDICT: BY-DESIGN. The promotion fires only when `_path_is_dynamic_ready_template(path)` is
true — i.e. the file lives under the user's OWN local plugin roots (`./vibecomfy_extras/ready_templates/`
or `~/.vibecomfy/...`). Content the user placed in their own plugin directory is user-trusted,
analogous to a scratchpad they authored. Removing the promotion would force interactive
confirmation on every plugin-template load, breaking non-interactive/automated use. No change.

## B. scratchpad_loader.py — no AST scanning (unlike agent_generated_loader)
VERDICT: BY-DESIGN. Two-tier trust model, explicitly enforced: `load_scratchpad` REJECTS
`agent_generated` provenance (scratchpad_loader.py:27-32 — "agent_generated provenance is reserved
for ...agent_generated_loader"). User-authored scratchpads get the confirmation gate only;
LLM/agent-generated code is routed through `agent_generated_loader` which DOES the AST scan.
Adding AST scanning here would conflate the tiers and reject legitimate user scratchpads. No change.

## Mechanical fixes actually done in wave 9 (low-risk, no policy change):
- intent_nodes.py: remove the unreachable `ast.comprehension` allowlist entry (comprehensions are
  rejected at the parent node; the entry is dead). Behavior unchanged (comprehensions stay disallowed).
- dedup the shared forbidden-name set between security/agent_generated_loader._FORBIDDEN_NAMES and
  contracts/intent_nodes.RUNTIME_CODE_FORBIDDEN_NAMES (single source of truth; effective sets IDENTICAL).

If the security owner WANTS to tighten A or B, that's a deliberate policy decision with UX/automation
trade-offs — out of scope for a no-break cleanup.
