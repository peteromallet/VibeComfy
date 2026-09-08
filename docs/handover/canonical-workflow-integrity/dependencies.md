# Pinned dependencies and recipient prerequisites

Skills repository: https://github.com/peteromallet/poms-skills.git (public).
Exact inspected and remotely fetchable skills commit: `63825bbb191a0539c0b99832099966ee9f23e3e2`.
The inspected local Megado/handover files match this committed content. No recipient depends on local skill paths. Existing run.yaml bindings/overrides win over defaults in the pinned skill, including the already-declared worker reasoning setting.

Read [Megado](https://github.com/peteromallet/poms-skills/blob/63825bbb191a0539c0b99832099966ee9f23e3e2/megado/SKILL.md), then its [execution mechanics](https://github.com/peteromallet/poms-skills/blob/63825bbb191a0539c0b99832099966ee9f23e3e2/megado/references/execution.md) before delivery. Relevant closure is megado/SKILL.md, references/run-config.md, references/review-packets.md, references/execution.md, templates/run.yaml, templates/review-packet.md, and optional scripts/megado_run_index.py; megado-handover/SKILL.md and its assets/handover-message.md explain this package. Cloning the pinned repository supplies the referenced files. No AgentBox/cloud setup is required.

## No-overwrite fetch/install

From the project checkout, choose a new sibling destination; these commands refuse an existing destination:

```sh
SKILLS_DEST="../poms-skills-63825bbb191a0539c0b99832099966ee9f23e3e2"
test ! -e "$SKILLS_DEST" && test ! -L "$SKILLS_DEST" || exit 1
git clone --no-checkout https://github.com/peteromallet/poms-skills.git "$SKILLS_DEST"
git -C "$SKILLS_DEST" checkout --detach 63825bbb191a0539c0b99832099966ee9f23e3e2
git -C "$SKILLS_DEST" rev-parse HEAD
```

Optional Codex registration after that checkout (existing registrations are preserved):

```sh
mkdir -p "$HOME/.codex/skills"
SKILLS_ABS="$(cd "$SKILLS_DEST" && pwd)"
if [ ! -e "$HOME/.codex/skills/megado" ] && [ ! -L "$HOME/.codex/skills/megado" ]; then ln -s "$SKILLS_ABS/megado" "$HOME/.codex/skills/megado"; fi
if [ ! -e "$HOME/.codex/skills/megado-handover" ] && [ ! -L "$HOME/.codex/skills/megado-handover" ]; then ln -s "$SKILLS_ABS/megado-handover" "$HOME/.codex/skills/megado-handover"; fi
```

Direct-read fallback: read the pinned public links above without installing a skill, or read the exact files from the pinned checkout. Raw fallback: https://raw.githubusercontent.com/peteromallet/poms-skills/63825bbb191a0539c0b99832099966ee9f23e3e2/megado/SKILL.md and the same prefix plus the referenced paths. Do not replace the pin with unverified main or overwrite existing installations.

## Product prerequisites

Python >=3.11 and Git are required; source includes pyproject.toml and uv.lock. An existing suitable environment is preferred. If absent, ordinary local dev setup is:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Run tasklist commands with that environment active. The macOS timeout command may require GNU coreutils; an equivalent process-supervisor timeout is acceptable without changing budgets. No product dependency installation or tests were performed for this handover. Optional agent-panel/Comfy dependencies and platform availability are not assumed; inspect the pinned pyproject when actually needed. No GPU, model download, paid provider, live service or broad Comfy installation is required merely to receive the plan.

Native subagent capability and required model identifiers must be checked on the receiving runtime. In the preparer's runtime, native delegation was available and Luna/Astra were actually used; Sol is advertised but was not exercised in this run. Recipient access to every configured model/reasoning mode, including reserved XHARD slots, is unknown. Report missing capability/model/access explicitly, do not silently substitute. Reserved Sol absence need not stop unrelated normal work, but it prevents assigning Sol work until resolved. GitHub repositories are public; no private source token is required to clone them.
