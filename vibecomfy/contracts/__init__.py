from __future__ import annotations

# Single source of truth for the public surface and lazy-import routing.
# name → (module, attr)
_EXPORTS = {
    "COMPILED_EDGE_ENDPOINT_RESOLVED": ("vibecomfy.contracts.ir", "COMPILED_EDGE_ENDPOINT_RESOLVED"),
    "ContractDoctorDiagnostic": ("vibecomfy.contracts.doctor", "ContractDoctorDiagnostic"),
    "ContractDoctorReport": ("vibecomfy.contracts.doctor", "ContractDoctorReport"),
    "ContractIssue": ("vibecomfy.contracts.validation", "ContractIssue"),
    "ContractReport": ("vibecomfy.contracts.validation", "ContractReport"),
    "HELPER_EDGE_REWIRED_OR_REPORTED": ("vibecomfy.contracts.ir", "HELPER_EDGE_REWIRED_OR_REPORTED"),
    "INTENT_CODE_MAX_BYTES": ("vibecomfy.contracts.intent_nodes", "INTENT_CODE_MAX_BYTES"),
    "INTENT_LOOP_MAX_ITERATIONS": ("vibecomfy.contracts.intent_nodes", "INTENT_LOOP_MAX_ITERATIONS"),
    "INTENT_NODE_CONTRACT_INVALID_CODE": ("vibecomfy.contracts.intent_nodes", "INTENT_NODE_CONTRACT_INVALID_CODE"),
    "INTENT_NODE_EDITOR_ONLY_CODE": ("vibecomfy.contracts.intent_nodes", "INTENT_NODE_EDITOR_ONLY_CODE"),
    "INTENT_NODE_QUEUE_BLOCKER_CODE": ("vibecomfy.contracts.intent_nodes", "INTENT_NODE_QUEUE_BLOCKER_CODE"),
    "IntentNodeProblem": ("vibecomfy.contracts.intent_nodes", "IntentNodeProblem"),
    "IntentNodeValidationResult": ("vibecomfy.contracts.intent_nodes", "IntentNodeValidationResult"),
    "IR_CONTRACT_ANCHORS": ("vibecomfy.contracts.ir", "IR_CONTRACT_ANCHORS"),
    "IR_CONTRACT_CODES": ("vibecomfy.contracts.ir", "IR_CONTRACT_CODES"),
    "IR_CONTRACT_SHAPE": ("vibecomfy.contracts.ir", "IR_CONTRACT_SHAPE"),
    "IR_CONTRACT_VERSION": ("vibecomfy.contracts.ir", "IR_CONTRACT_VERSION"),
    "IRContractAnchor": ("vibecomfy.contracts.ir", "IRContractAnchor"),
    "LTXFirstLastTwoStageContract": ("vibecomfy.contracts.ltx_first_last", "LTXFirstLastTwoStageContract"),
    "NormalizedRuntimeCodeContract": ("vibecomfy.contracts.intent_nodes", "NormalizedRuntimeCodeContract"),
    "PUBLIC_INPUT_STALE_TARGET": ("vibecomfy.contracts.ir", "PUBLIC_INPUT_STALE_TARGET"),
    "PUBLIC_INPUT_UNREGISTERED": ("vibecomfy.contracts.ir", "PUBLIC_INPUT_UNREGISTERED"),
    "RUNTIME_CODE_CONTRACT_VERSION": ("vibecomfy.contracts.intent_nodes", "RUNTIME_CODE_CONTRACT_VERSION"),
    "RUNTIME_CODE_EXECUTION_MODE": ("vibecomfy.contracts.intent_nodes", "RUNTIME_CODE_EXECUTION_MODE"),
    "RUNTIME_CODE_POLICY_VERSION": ("vibecomfy.contracts.intent_nodes", "RUNTIME_CODE_POLICY_VERSION"),
    "RuntimeCodeContractValidationResult": ("vibecomfy.contracts.intent_nodes", "RuntimeCodeContractValidationResult"),
    "VALIDATION_OK_COMPILES_API": ("vibecomfy.contracts.ir", "VALIDATION_OK_COMPILES_API"),
    "VALIDATION_REPORT_OK_FIELD": ("vibecomfy.contracts.ir", "VALIDATION_REPORT_OK_FIELD"),
    "WorkflowRuntimeContract": ("vibecomfy.contracts.model", "WorkflowRuntimeContract"),
    "build_contract": ("vibecomfy.contracts.model", "build_contract"),
    "intent_node_payload_from_metadata": ("vibecomfy.contracts.intent_nodes", "intent_node_payload_from_metadata"),
    "intent_node_properties": ("vibecomfy.contracts.intent_nodes", "intent_node_properties"),
    "intent_node_properties_from_metadata": ("vibecomfy.contracts.intent_nodes", "intent_node_properties_from_metadata"),
    "is_intent_class_type": ("vibecomfy.contracts.intent_nodes", "is_intent_class_type"),
    "doctor_contract": ("vibecomfy.contracts.doctor", "doctor_contract"),
    "ir_contract_codes": ("vibecomfy.contracts.ir", "ir_contract_codes"),
    "is_ir_contract_code": ("vibecomfy.contracts.ir", "is_ir_contract_code"),
    "require_ir_contract_code": ("vibecomfy.contracts.ir", "require_ir_contract_code"),
    "validate_intent_node_contract": ("vibecomfy.contracts.intent_nodes", "validate_intent_node_contract"),
    "validate_runtime_code_contract": ("vibecomfy.contracts.intent_nodes", "validate_runtime_code_contract"),
    "validate_typed_io_spec": ("vibecomfy.contracts.intent_nodes", "validate_typed_io_spec"),
}

__all__ = tuple(_EXPORTS)


def __getattr__(name: str):
    if name in _EXPORTS:
        module_name, attr_name = _EXPORTS[name]
        from importlib import import_module

        value = getattr(import_module(module_name), attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
