# Intent Oracle — Judge Rubric

Each judge evaluates an edit against four binary criteria. All four must pass
for a PASS verdict; any single failure produces a FAIL verdict (AND-aggregation
within each judge and across the judge panel).

## Criteria

### C1 — correct_node_targeted
The node(s) changed in the post-edit IR are the semantically appropriate nodes
for the stated intent. A change to a pre-processing resize node when the intent
is "use a faster sampler" fails this criterion.

### C2 — correct_parameter_changed
Within the targeted node, the specific parameter (field/key) that was changed is
the one that controls the semantic dimension the intent refers to. Changing
`sampler_name` when the intent says "run more steps" fails this criterion.

### C3 — value_semantically_matches_intent
The new value set on the parameter is semantically consistent with the intent.
Setting `denoise=1.0` when asked for "sharper" output fails this criterion
because `denoise` does not control sharpness; setting `cfg=0` when asked for
"more faithful" fails because cfg=0 disables guidance entirely.

An explicit terminal numeric target tied to the targeted field is authoritative:
when the request says `to N`, `= N`, or `set <field> ... N` and the landed new
value for that field is exactly `N`, this criterion passes even if an accompanying
`increase`/`decrease` verb conflicts with the pre-image direction. Unrelated
numbers and descriptive schedule or handoff phrasing do not qualify.

### C4 — no_orphaned_wiring
The edit leaves the graph in a structurally connected state. No output that was
previously consumed is left unconnected, and no new node is inserted without
wiring its required inputs. An edit that changes a LoadImage filename but leaves
a CLIPVisionEncode input dangling fails this criterion.

## Aggregation

A verdict is PASS only when ALL four criteria return True:
```
verdict = C1 AND C2 AND C3 AND C4
```

Each criterion is independently evaluated and reported in `JudgeVerdict.criteria`.
The rationale field must quote the specific IR diff evidence for each failing
criterion.
