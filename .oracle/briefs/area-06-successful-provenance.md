Explore area: Successful-call provenance — same requested/resolved fields on successful calls?

Context: B01 requires complete failed-call evidence (phase, parse reason, token flag, finish reason, preview, model, provider, endpoint). B07/final reporting may need the same fields on successful calls (requested vs resolved model, adapter, base URL, transport) for the comparison report.

Task: check what provenance is persisted on SUCCESSFUL model calls today (worker.py, runtime.py, provider.py, agent_backend.py, artifacts.py — model_response artifacts, flow_metadata, batch turn details) vs failed calls (post-G0-T4). Report: verified field coverage on success paths (file:line), gaps vs the B01 failed-call set, whether the final report's requested/resolved model + transport metrics are derivable from persisted evidence, unknowns, risks, and the minimal additive change to close gaps. Ranked findings, <300 words.
