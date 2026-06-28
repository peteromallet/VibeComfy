"""Internal stage implementations for the agent-edit pipeline.

Each sub-module groups related stage functions together.
"""

from .ingest import (  # noqa: F401
    _stage_convert,
    _stage_ingest,
    _stage_ingest_v2,
    _stage_project_v2,
    _stale_rebaseline_recovery_issue,
    _stamp_identity_on_original,
)
from .agent_delta import (  # noqa: F401
    _edit_lint_enabled,
    _stage_agent,
    _stage_agent_delta,
    _stage_apply_delta,
)
from .load_lower_validate_emit import (  # noqa: F401
    _stage_emit,
    _stage_load_python,
    _stage_lower,
    _stage_validate,
)
from .revision import (  # noqa: F401
    _finalize_revision_evidence_with_candidate,
    _localized_additive_scoped_evidence,
    _revision_evidence_prompt_json,
    _revision_readonly_message,
    _revision_no_candidate_reason,
    _revision_target_node_ids,
    _stage_revision_evidence,
    _stage_revision_readonly_report,
    _write_revision_evidence_artifact,
)
