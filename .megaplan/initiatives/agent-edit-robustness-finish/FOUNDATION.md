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
  getter-only LiteGraph properties.

The launch checkout must use this tracked receipt and pass:

```bash
git merge-base --is-ancestor a395c243 agent/agent-edit-robustness-foundation
```

The current Megaplan precondition schema verifies that the receipt is committed
and contains the required repair SHA; it does not itself execute the ancestry
command. Record that command and its zero exit status before R1 starts. The base
branch remains `agent/agent-edit-robustness-foundation`; the receipt changes its
required content, not its name.
