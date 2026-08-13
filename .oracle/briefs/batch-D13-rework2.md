# MEGADO D13 REWORK 2 (oracle blocking issue) — judge verdicts must fail closed

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run focused tests only. D13 is in the tree at `5aa73c53` — fix on top, do not revert.

## The blocking issue (D13 oracle re-verdict)

`tests/live_agentic_harness/intent_judge.py:86` and `:103`: both verdict parsers trust the model's `pass_` field and coerce arbitrary values with `bool()`. Consequences (both reproduced by the oracle):

- `pass_=true` with all criteria false remains a pass.
- JSON strings such as `"false"` become Python `True` (including every criterion).

The assessor then accepts `pass_ is True` at `assessor.py:838` and `:875`. This admits a fabricated refusal or incorrect desired edit despite failing criteria.

## What to change

1. **`intent_judge.py:86` and `:103` parsers**: do NOT trust the model's self-declared `pass_`. Derive the verdict from the CRITERIA:
   - pass iff ALL required criteria are explicitly true (strict boolean parsing — `true`/`false` booleans only; string `"false"`/`"true"` are malformed, not coercible);
   - any criterion false or missing → fail;
   - malformed/contradictory verdict (unparsable criteria, string-typed booleans, missing fields, pass=true with criteria false) → fail closed (treat as not-pass; in the D13 semantics that is a failed desired edit / unsupported refusal, and where the judge is unavailable it is `undetermined` — but malformed OUTPUT is a fail, never a pass).
2. Keep the pass iff all criteria pass contract: grounded refusal = supported blocker + no representable edit + specific next action + no fabricated inability, ALL true; desired edit = the edit matches the desired block.
3. Add regressions:
   - `pass_="false"` string with all criteria true → NOT pass;
   - `pass_=true` with a criterion false → NOT pass;
   - criteria containing string-typed booleans → NOT pass;
   - `pass_=true` with missing criteria → NOT pass;
   - genuine all-true → pass.
4. Confirm `assessor.py:838`/`:875` consume the derived verdict (they should need no change, but verify the `pass_` values they see are now derived, not raw).

## Verification (run, retain output)

```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_intent_judge_schema_context.py tests/test_live_agentic_harness_corpus_manifest.py
```

Expected exit 0. Add fixtures to the intent-judge test file so the slice covers them.

## Report
Return: exact changes (files + line refs), fixture names, pytest output. Do NOT commit.
