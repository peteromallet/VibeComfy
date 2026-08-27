# Custody baseline — onboarding-mode run

- Date: 2026-08-26 (local)
- Source ref (immutable): `8a4ff90b356a07d43021e3d6255adae36678b227` = `origin/main` after shipping IR/fast fixes.
- Base branch at fork: `main` (== origin/main, clean).
- Worktree: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle-onboard`, branch `oracle-onboard-20260826`.
- Main checkout status at fork: clean (`## main...origin/main`, no dirty entries).
- Untracked files in main checkout at fork: none relevant (working tree clean per `git status --porcelain | head` empty).
- Other worktrees (protected, DO NOT TOUCH):
  - `../vibecomfy-oracle` branch `oracle-run` — prior schema-campaign megado workspace. Untouched; one stray snapshot file copied there this run was removed.
  - Prunable stale worktrees under `/private/tmp/vc-*` — left alone.
- Remotes: `origin → https://github.com/peteromallet/VibeComfy.git`.
- Protected local work that must survive:
  - `desloppify/worst-offenders` branch + stash `desloppify-keep-final` in the MAIN checkout (51-file refactor WIP). Never mutated from this run.
- Environment identity: darwin 24.4.0 arm64, Apple M2, node v20.19.4, uv-managed `.venv` Python 3.11.14, repo pyproject `vibecomfy 2.8.0`.
- North Star custody: prior campaign-scoped northstar snapshotted (see agent_goal.md header) with sha256 d9b4d1d294e11054bb145ab539f1fea28b1cd031234955c4a5393b49aa9928bd before writing this run's northstar.md.
