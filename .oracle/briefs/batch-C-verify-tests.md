# VERIFY — Batch C acceptance tests (read-only except pytest)

You are ox-alpha verifying Batch C at HEAD `5f3e635f` in
`/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle`.
Do NOT edit source. Tests may run; do not commit.

## What to do

1. `cd /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle`

2. Help text:
   ```
   python3 -m vibecomfy schemas ensure --help
   ```
   If that fails, try `vibecomfy schemas ensure --help`. Paste verbatim.

3. Confirm `clone_and_extract_packs` is gone from the command module:
   ```
   grep -n clone_and_extract_packs vibecomfy/commands/schemas.py || true
   ```
   Empty is expected. Paste verbatim.

4. Run:
   ```
   python3 -m pytest tests/test_schemas_ensure.py tests/test_on_demand_resolver.py tests/test_ensure_capture.py -q --tb=short
   ```
   Paste the full summary line and any failures verbatim.

5. List the new tests that actually call `_cmd_schemas_ensure` (names + one-line what each asserts). Confirm they exist:
   - noop when attested capture exists
   - missing class → mocked registry + mocked clone + real extract → cache file + provenance
   - r2 default: allow_import True even if VIBECOMFY_ON_DEMAND_BOOT unset
   - stub-indexed class is a gap
   - --json failure is non-zero
   - no network in this file (grep urllib/requests/httpx/api.comfy.org in the test file)

6. After pytest, run `git status --porcelain vibecomfy/porting/cache tests/test_schemas_ensure.py vibecomfy/commands/schemas.py`. Report whether the committed cache or any source file was dirtied.

## Return (max 400 words)

- Verbatim help snippet proving `--manifest` is listed
- Verbatim grep result
- Verbatim pytest summary
- Table: required test vs present/absent
- Cache/source dirty after tests: yes/no + paths
- Your verdict on Checkpoint C test/help/grep criteria: PASS or FAIL with evidence
