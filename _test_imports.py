import vibecomfy.comfy_nodes.agent.edit as e
print("__all__:", e.__all__)
print("handle_agent_edit:", hasattr(e, "handle_agent_edit"))
print("_SESSION_ROOT:", e._SESSION_ROOT)
symbols = [
    'handle_agent_edit', 'read_session_chat', 'read_session_bundle', 'read_session_json',
    '_field_change_is_noop', '_real_field_changes', '_humanized_edit_message',
    '_format_batch_report', '_display_value', '_json_safe',
    '_BATCH_EXIT_NOOP', '_CHAT_REASONING_MAX_STEPS',
    '_write_turn_chat_artifact', '_latest_session_candidate_payload',
    '_batch_budget_failure_kind', '_compact_diag_to_dict',
    '_resolver_candidates_from_batch_turns',
]
for s in symbols:
    ok = hasattr(e, s)
    if not ok:
        print(f"MISSING: {s}")
    else:
        val = getattr(e, s)
        mod = val.__module__ if hasattr(val, '__module__') else '?'
        print(f"OK: {s} (from {mod})")
