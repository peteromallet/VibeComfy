# Megado status — informational-research path

Phase: 6 (complete) — all batches PASSED and verified

Batches:
  B01 317a3cdf  messages client (hivemind_clients.py) + 52 tests
  B02 29c9991d  sources= tier gating (research() + _resolve split)
  B03 2ae42426  research-route omit default (messages+web), followup, memory, community_summary
  B04 ad1a3c3d  hoist research_findings + _run_reply fix (critical)
  B05 289e61d2  real batch-REPL integration test
  B06 f11fd66e  web 429 backoff + cache TTL

Verification:
  - 967 passed / 0 failed across the six research-path test files
  - LIVE acceptance gate PASSED:
    * MiniMax H3 probe: 6 agent-judgment research iterations; cited hicho +
      Gotobius in #minimax_h3_chatter with specific tuning (guidance 1.0,
      8 steps, 0.6 MP); reply = community answer with names/channel/settings
    * LTX 2.5 probe: 7 agent-judgment research iterations; cited VK in
      #ltx_chatter (vid2vid workflow ask); honest thinness admission, no
      invented consensus
  - Both probes ran the real pipeline: classify -> research-route omit-default
    -> messages client -> agent judgment iteration -> hoist -> _run_reply
  - Pre-existing env issues (not regressions): missing corpus JSON on fresh
    worktree (symlinked), arnold venv quirk (used oracle-worktree venv),
    OpenRouter key limit (used _2 key for probes, restored after)

Constraint honored: NO deterministic loops/actions — all search/stop decisions
are agent judgment (user ruling 2026-08-12). No research_iteration.py, no
scoring, no latches, no expansion, no research-call caps.
