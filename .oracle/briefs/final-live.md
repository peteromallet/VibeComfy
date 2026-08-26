# FINAL REVIEW — one expensive/live validation (registry reachability)

You are Spark. Repo
`/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle` HEAD `d2975269`.
Do NOT edit source. Do NOT commit. Do NOT run pytest.
Do NOT write into `vibecomfy/porting/cache` (the committed capture cache).

Stop condition from `.oracle/agent_goal.md`: `blocked` if the Comfy registry
API is unreachable from this machine (capture e2e needs it). Plan Batch E
task 5 optional host-only: one real UNPROVEN class against the registry;
if down, `blocked`, do not fake schemas. Fixture e2e already mocks the
registry — this probe is the live one.

## Procedure

1. Identity:
```
cd /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
git rev-parse HEAD
```

2. Reachability (no retries storm):
```
curl -sS -o /tmp/comfy-api-head.txt -w "HTTP %{http_code} time %{time_total}\n" \
  --max-time 15 -I https://api.comfy.org/ || echo CURL_FAIL:$?
curl -sS -o /tmp/comfy-api-nodes.json -w "HTTP %{http_code} bytes %{size_download}\n" \
  --max-time 20 "https://api.comfy.org/nodes?limit=1" || echo CURL_FAIL:$?
```
If both fail (timeout/DNS/non-2xx): stop, verdict LIVE-BLOCKED, do not fake.

3. If reachable, ONE live resolve only, against a throwaway cache.
   Do not persist to the repo cache. Example (adjust imports to match code):
```
cd /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
python3 - <<'PY'
from vibecomfy.registry.pack_resolver import resolve_pack
# Use a well-known class that is NOT a core node; IndexTTS or similar.
# If resolve raises, print the exception and exit 0 (probe failed closed).
try:
    ref = resolve_pack("IndexTTS")
    print("RESOLVE_OK", getattr(ref, "slug", None), getattr(ref, "url", None), getattr(ref, "version", None), getattr(ref, "commit", None))
except Exception as e:
    print("RESOLVE_FAIL", type(e).__name__, e)
PY
```
   If `IndexTTS` is the wrong name, try `IndexTTS2` / `LayerMask` once each
   then stop. Do not loop the registry.

4. Do NOT run `vibecomfy schemas ensure` against the committed cache.
   Do NOT clone into `~/.cache/vibecomfy/schema-sandbox` unless resolve
   succeeds AND you isolate:
   `export VIBECOMFY_SCHEMA_SANDBOX=/tmp/vc-oracle-live-sandbox`
   (only if that env var exists in `on_demand.py`; if it does not, SKIP the
   clone and report resolve-only). Never leave a venv behind.

5. Confirm no dirty committed cache:
```
git status --porcelain vibecomfy/porting/cache
```
   If dirty, `git checkout -- vibecomfy/porting/cache`.

## Return (max 300 words)

- HEAD
- curl results (status codes)
- resolve result (slug/url/version or fail)
- clone attempted? yes/no (default no)
- cache dirty? yes/no + restored
- Verdict: LIVE-REACHABLE | LIVE-BLOCKED | LIVE-RESOLVE-FAIL
  (LIVE-BLOCKED is the agent_goal stop condition, not a code defect)
