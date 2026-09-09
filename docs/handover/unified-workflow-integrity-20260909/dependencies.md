# Dependencies and agent capability

Inspected skills repository: https://github.com/peteromallet/poms-skills.git

Exact commit: `ef42515942adfb1683cde4b7b2d53d4e56dbe25e`. Relevant working files were committed and byte-identical to that commit. The raw URLs below returned HTTP 200 with the same SHA-256 as the inspected files. This is dependency provenance, not a model execution or installation claim.

## Fetch without overwriting existing skills

Run from a workspace parent, not inside an existing skills installation:

```sh
SKILLS_DEST="$PWD/poms-skills-ef42515942adfb1683cde4b7b2d53d4e56dbe25e"
if test -e "$SKILLS_DEST"; then
  echo "Destination exists; select another unused path instead of overwriting." >&2
  exit 1
fi
git clone --no-checkout https://github.com/peteromallet/poms-skills.git "$SKILLS_DEST"
git -C "$SKILLS_DEST" checkout --detach ef42515942adfb1683cde4b7b2d53d4e56dbe25e
git -C "$SKILLS_DEST" rev-parse HEAD
```

This creates a separate pinned checkout; it does not overwrite user-wide skills or install Python/runtime/model dependencies. Read `megado/SKILL.md` there. Before delivery, also read execution.md, run-config.md and review-packets.md from its references directory. The packet template is already copied here; it is a template, not a completed candidate packet.

## Direct-read fallback

If a skills checkout is unavailable, read the exact pinned files directly:

- [Megado](https://raw.githubusercontent.com/peteromallet/poms-skills/ef42515942adfb1683cde4b7b2d53d4e56dbe25e/megado/SKILL.md)
- [Execution mechanics](https://raw.githubusercontent.com/peteromallet/poms-skills/ef42515942adfb1683cde4b7b2d53d4e56dbe25e/megado/references/execution.md)
- [Run configuration](https://raw.githubusercontent.com/peteromallet/poms-skills/ef42515942adfb1683cde4b7b2d53d4e56dbe25e/megado/references/run-config.md)
- [Review packet assembly](https://raw.githubusercontent.com/peteromallet/poms-skills/ef42515942adfb1683cde4b7b2d53d4e56dbe25e/megado/references/review-packets.md)
- [Review packet template](https://raw.githubusercontent.com/peteromallet/poms-skills/ef42515942adfb1683cde4b7b2d53d4e56dbe25e/megado/templates/review-packet.md)
- [Handover](https://raw.githubusercontent.com/peteromallet/poms-skills/ef42515942adfb1683cde4b7b2d53d4e56dbe25e/megado-handover/SKILL.md)

## Runtime prerequisites

Use Python >=3.11 and the dependencies declared in the project's [pyproject.toml](../../../pyproject.toml), already provisioned in an environment. Validation requires pytest and the relevant project extras; run.yaml parsing requires a YAML reader such as PyYAML. Commands use GNU `timeout` or equivalent hard wall-clock supervision. The source checkout must own imports (`vibecomfy.__file__` inside the chosen checkout). An environment missing dependencies is not a failed implementation test and is not permission to install packages under the current no-install limit.

The sender's native tool inventory includes every configured model in run.yaml and native spawn/followup delegation. The recipient must verify its own delegation capability and access to each exact configured model/reasoning binding before dispatch. Native availability on the sender does not establish availability on the recipient. Report missing capability/model explicitly; do not substitute silently. Only E1 uses the existing XHARD worker assignment; keep other work on the normal route.
