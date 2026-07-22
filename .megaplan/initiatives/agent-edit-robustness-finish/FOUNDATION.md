# Repaired Foundation Receipt

This tracked receipt is the launch boundary for the finish epic. Its presence
on `agent/agent-edit-robustness-foundation` attests which incident-repair stack
the branch must contain; the chain must not launch from the former `7934834f`
tip.

Required repairs, in order:

- `b136188e` — empty-canvas transaction publication;
- `1df7c322` — rejectable invalid review candidates;
- `3dd6fd4a` — native-port-identity link resolution;
- `65415c8b` — native projection normalization;
- `245e6fe1` — separation of compatibility/session hashes from typed witnesses;
- `22b948ce` — chat retention across finalized structural edits;
- `aa0f6d90` — migration from fingerprint-qualified chat scopes;
- `a395c243` — semantic-field resolution through native widgets, including
  getter-only LiteGraph properties;
- `be806105` and `7dd11225` — turn-isolated durable transaction evidence;
- `4f53cceb` and `c03a5f07` — preflight compensation plus preview/Apply planner
  parity;
- `0225b2c4` and `e3fc78d4` — supervised prepared transactions and durable
  Resume Apply;
- `c2f4e5f3` — semantic normalization of native `LoadImage` UI carriers;
- `46047e0b` — typed-only `delta_replay` finalize authority and persistence of
  the exact applied native graph as the next CAS baseline.

The launch checkout must use this tracked receipt and pass:

```bash
git merge-base --is-ancestor 46047e0b agent/agent-edit-robustness-foundation
```

The current Megaplan precondition schema does not itself execute an ancestry
command. The committed `proof/r1-foundation-ancestry.json` records the zero-exit
check against the integration head, and launch preconditions require that proof
to be tracked and successful. The launch head must descend from that integration
head. The base branch remains `agent/agent-edit-robustness-foundation`; the
receipt changes its required content, not its name.
