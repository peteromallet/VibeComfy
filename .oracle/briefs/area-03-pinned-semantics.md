Explore area: Pinned-node semantics beyond Set/Get broadcast.

Context: B03 (plan item 6) replaces pinned-output link cardinality checks with semantic terminal-consumer equivalence. The known reproduction is Set/Get broadcast lowering expanding 1 raw link → 4 lowered links (vibecomfy/porting/emit/ui.py pin guard). Before declaring B03 complete, the plan must know the full surface of pin-guard comparisons.

Task: audit the pin-emission guard logic (porting/emit/ui.py — pin_opaque, _raw_ui_payload_for_pin, consumer comparisons), and the graph structures that exercise it (nested subgraphs, multi-output nodes, muted/bypassed helpers, duplicate broadcast names, reroute cycles, broadcast expansion). Report verified facts with file:line, whether the current comparison is cardinality-only everywhere, edge cases that would break a semantic-consumer implementation, unknowns, risks, and a suggested approach for the B03 comparison. Ranked findings, <300 words.
