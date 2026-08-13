Explore area (round 2): Add-node port materialization — do all declared ports exist before link resolution?

Context: B08-cut (deterministic endpoint integrity) fixes C8/C9: add-node links resolve through the same resolver (apply_resolve_add.py:242) and links into nonexistent inputs materialize synthetic inputs instead of rejecting. The plan must know whether declared ports are materialized into the working node before link resolution.

Task: trace the add-node path (apply_resolve_add.py, apply_mutate.py, edit_batch_repl.py add flows, porting/edit/): when a node is added, are its outputs/inputs arrays materialized from the schema BEFORE links resolve? What happens when the schema lacks the node (unknown class)? Report verified facts with file:line, whether port materialization precedes resolution on the add path (and the set path), unknowns, risks, and the minimal fix location for B08 (bounds check at write vs materialize-then-validate). Ranked findings, <300 words.
