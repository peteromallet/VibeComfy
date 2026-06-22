"""M5 investigate-tier and execution-tier evidence builders.

Each builder loads a real Wan/LTX base workflow, records synthetic CLI
invocations into ``command_log.jsonl``, and writes the complete evidence pack
so the rubric can verify the agent's diagnosis or execution behaviour.

These cover investigate (no GPU) and execution honesty-negatives (no GPU).
GPU-positive execution scenarios are handled by separate builders.
"""

from __future__ import annotations

from typing import Callable

from tests.agentic_harness.actors_m5.diagnose_broken_graph import (
    build_m5_diagnose_broken_graph_evidence,
)
from tests.agentic_harness.actors_m5.trace_resolution_source import (
    build_m5_trace_resolution_source_evidence,
)
from tests.agentic_harness.actors_m5.readiness_go_no_go import (
    build_m5_readiness_go_no_go_evidence,
)
from tests.agentic_harness.actors_m5.verify_edit_scoped import (
    build_m5_verify_edit_scoped_evidence,
)
from tests.agentic_harness.actors_m5.server_runtime_dead_url import (
    build_m5_server_runtime_dead_url_evidence,
)
from tests.agentic_harness.actors_m5.embedded_run_no_gpu import (
    build_m5_embedded_run_no_gpu_evidence,
)
from tests.agentic_harness.actors_m5.runpod_list_before_terminate import (
    build_m5_runpod_list_before_terminate_evidence,
)
from tests.agentic_harness.actors_m5.two_stage_chain_both_ran import (
    build_m5_two_stage_chain_both_ran_evidence,
)
from tests.agentic_harness.actors_m5.route_intent_map import (
    build_m5_route_intent_map_evidence,
)

_M5_BUILDERS: dict[str, Callable] = {
    "diagnose-broken-graph": build_m5_diagnose_broken_graph_evidence,
    "trace-resolution-source": build_m5_trace_resolution_source_evidence,
    "readiness-go-no-go": build_m5_readiness_go_no_go_evidence,
    "verify-edit-scoped": build_m5_verify_edit_scoped_evidence,
    "server-runtime-dead-url": build_m5_server_runtime_dead_url_evidence,
    "embedded-run-no-gpu": build_m5_embedded_run_no_gpu_evidence,
    "runpod-list-before-terminate": build_m5_runpod_list_before_terminate_evidence,
    "two-stage-chain-both-ran": build_m5_two_stage_chain_both_ran_evidence,
    "route-intent-map": build_m5_route_intent_map_evidence,
}

__all__ = ["_M5_BUILDERS"]
