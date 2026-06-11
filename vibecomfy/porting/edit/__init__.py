"""Public API surface for the edit/ sub-package.

Re-exports all public names from the eight constituent modules.
"""

from .session import (
    BatchResult,
    CompactDiagnostic,
    DoneResult,
    EditSession,
    InputSlotInfo,
    NodeDescriptor,
    OutputSlotInfo,
    StatementResult,
)

from .ops import (
    AddNodeOp,
    AgentDeltaTurnResult,
    AnchorRef,
    EDIT_OP_RESPONSE_SCHEMA_V2,
    EditOp,
    EditOpParseError,
    LinkSourceRef,
    LinkTargetRef,
    NodeFieldTarget,
    NodeTarget,
    RemoveLinkOp,
    RemoveNodeOp,
    ReorderOp,
    SetModeOp,
    SetNodeFieldOp,
    UpsertLinkOp,
    normalize_delta_agent_response,
    normalize_delta_test_client_response,
    op_to_dict,
    parse_edit_delta,
    parse_edit_op,
)

from .types import FieldChange

from .ledger import (
    EditLedger,
    ScopeState,
)

from .projection import (
    DEFAULT_MAX_TOKENS,
    ProjectionOptions,
    ProjectionResult,
    USER_STRING_FENCE,
    estimate_tokens,
    render_edit_projection,
)

from .apply import (
    ApplyResult,
    ResolvedAddNodeSpec,
    ResolvedFieldRef,
    ResolvedLinkEndpoint,
    ResolvedNodeRef,
    ResolvedRemoveLinkRef,
    ResolveResult,
    apply_delta,
    resolve_delta,
)

from .lint import (
    LintIndex,
    LintIssue,
    LintNormalization,
    LintResult,
    lint_delta,
)

from .normalize import (
    NORMALIZE_ALLOW_LIST,
    is_normalize_available,
    normalize_allow_list_matches,
    normalize_compare,
    normalize_ui_json,
)
