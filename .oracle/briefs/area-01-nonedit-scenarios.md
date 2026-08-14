Explore area: Semantic quality of the 37 non-edit scenarios.

Context: the 100-scenario corpus (tests/live_agentic_harness/scenarios/) includes non-edit scenarios that currently have no answer-quality judge. The plan must decide which are genuine product scenarios and which are executor-health controls before the final pass-rate denominator is frozen.

Task: inventory the non-edit scenarios (query type, expected outcome, expect_graph_changed=false etc.), check what the harness scores for them (assessor.py, guard.py, intent_judge.py), and report: verified per-scenario facts (with file references), whether any judge/quality gate applies to their answers, unknowns, risks to the measurement denominator, and a suggested classification (product vs health control). Ranked findings, <300 words.
