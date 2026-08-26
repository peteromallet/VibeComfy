# PROBE — Batch E doctor isolation (read-only)

You are Spark probing doctor isolation for Batch E at HEAD `d2975269` in
`/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle`.
Do NOT edit source. Do not run pytest (other agents own tests).

Executor claim (3): doctor prints ensure command and injects `ensure_command` JSON, does NOT clone/extract.

## What to do

1. Read `git diff 86e4a6ba..d2975269 -- vibecomfy/commands/doctor.py vibecomfy/schema/ensure_capture.py vibecomfy/commands/schemas.py`

2. Doctor isolation — FAIL if doctor (or a helper it newly calls on the unknown-class path) clones, extracts, persists, or boots on-demand:
   ```
   rg -n "OnDemandInstallSchemaProvider|_ensure_clone|extract_pack_schemas|persist_on_demand|clone_and_extract|git clone|subprocess|TemporaryDirectory|venv" vibecomfy/commands/doctor.py
   ```
   Also check any NEW import in the doctor delta. If doctor imports `format_template_gap` / `format_schema_gap` from `ensure_capture.py`, confirm those helpers are pure string formatters (no I/O, no clone). Paste helper bodies.

3. Plan task 3 exact shape:
   - on `unknown_class_type` / missing schema, print ensure command
   - workflow/template path: `vibecomfy schemas ensure <template>` if that’s the input
   - if a manifest is not in hand, still print the templates form plus “or `--manifest <comparison.json>`”
   - JSON injects `ensure_command`
   Cite file:line. FAIL if only one of text/JSON is updated, or if doctor now takes `--manifest` and starts ensuring.

4. Claim (1): `format_schema_gap` is the single source for the exact command `vibecomfy schemas ensure --manifest <path>`.
   ```
   rg -n "vibecomfy schemas ensure --manifest" vibecomfy tests docs/agent-skill/SKILL.md
   ```
   Every Python construction of that command in `vibecomfy/` and `tests/live_agentic_harness/` must go through `format_schema_gap` (test files may assert the string). Flag duplicated f-strings in production code (preflight, validate-coverage, ensure retry_command, doctor). `format_template_gap` is allowed as the template-path sibling.

5. Claim (2): `validate-coverage --manifest` reuses Batch A `missing_live_captures` (or equivalent gap helper in `ensure_capture.py`), does not invent a second gap definition.
   Cite the call. Confirm exit 1 when `--manifest` and gaps exist; template positional keeps exit 0. JSON keys `missing_classes` and `ensure_command`.

6. Confirm doctor is reporting-only: no new CLI flag that triggers capture.

## Return (max 350 words)

- Isolation: PASS/FAIL + evidence (rg + helper bodies)
- Task 3 shape: PASS/FAIL + file:line for text + JSON
- Claim 1 single-source: PASS/FAIL + any duplicated command strings
- Claim 2 validate-coverage reuse: PASS/FAIL + file:line
- Overall: PASS or issue list (blocking vs nit)
