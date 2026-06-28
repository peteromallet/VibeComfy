#!/usr/bin/env python3
"""Remove extracted functions from edit.py, keeping only the non-extracted ones."""
import re

with open('vibecomfy/comfy_nodes/agent/edit.py', 'r') as f:
    lines = f.readlines()

# Functions that were extracted (to be removed)
extracted = {
    '_total_landed_edit_count',
    '_discovery_stop_message',
    '_format_research_brief_for_prompt',
    '_batch_candidate_graph_changed',
    '_landed_edit_lead',
    '_display_value',
    '_node_label_by_uid',
    '_change_subject',
    '_looks_internal_uid',
    '_link_endpoint_parts',
    '_is_link_endpoint',
    '_resolve_output_slot_name',
    '_resolve_endpoint_label',
    '_ui_node_by_uid',
    '_node_class_label',
    '_ui_display_widget_value_for_field',
    '_node_key_values',
    '_node_phrase',
    '_article_for',
    '_first_link_source_label',
    '_structural_change_phrases',
    '_join_human_list',
    '_human_change_phrase',
    '_sentence_case',
    '_humanized_edit_message',
    '_terminal_answer_message',
    '_humanized_noop_message',
    '_revision_rejected_candidate_message',
    '_revision_candidate_retry_hint',
    '_operation_detail_payload',
    '_change_details_payload',
    '_batch_warning_sentence',
    '_synthesize_batch_repl_message',
    '_normalize_test_client_response',
    '_normalize_test_client_batch_response',
    '_render_batch_diff',
    '_format_statement_source',
    '_iter_ui_nodes',
    '_present_class_types',
    '_format_node_variable_index',
    '_format_available_node_names',
    '_format_query_output',
    '_batch_research_memory_summary',
    '_summarize_precedent_packet',
    '_premature_missing_custom_node_clarify_feedback',
    '_premature_workflow_schema_clarify_feedback',
    '_format_batch_report',
    '_format_batch_report_json',
    '_batch_has_landed_edits',
    '_batch_budget_failure_kind',
    '_json_safe',
    '_field_changes_payload',
    '_write_turn_chat_artifact',
    '_stamped_turn_response_outcome',
    '_stamped_message_outcome',
    '_read_turn_response_payload',
    '_latest_session_candidate_payload',
    '_trim_chat_text',
    '_compact_chat_change_details',
    '_conversation_with_candidate_reference',
    'read_session_chat',
    'read_session_bundle',
    'read_session_json',
    '_compact_diag_to_dict',
}

# Constants to remove (already imported from modules)
constants_to_remove = {
    '_CHAT_REASONING_MAX_STEPS',
    '_CHAT_REASONING_MAX_DIAGS',
    '_CHAT_REASONING_MAX_OPERATIONS',
    '_BUNDLE_TEXT_SUFFIXES',
    '_BUNDLE_MAX_FILE_BYTES',
    '_BUNDLE_MAX_TOTAL_BYTES',
}

# Build a set of line numbers that are part of extracted functions
removal_ranges = []

# Find function boundaries
func_starts = []
for i, line in enumerate(lines):
    m = re.match(r'^(def|class)\s+(\w+)', line)
    if m:
        func_starts.append((i, m.group(1), m.group(2)))

# Add line ranges for extracted functions
for idx, (start, kind, name) in enumerate(func_starts):
    if name in extracted:
        if idx + 1 < len(func_starts):
            end = func_starts[idx + 1][0] - 1
        else:
            end = len(lines) - 1
        # Include preceding blank lines
        while start > 0 and lines[start - 1].strip() == '':
            start -= 1
        removal_ranges.append((start, end))

# Also find and remove the extracted constants
for i, line in enumerate(lines):
    m = re.match(r'^(_CHAT_REASONING_MAX_STEPS|_CHAT_REASONING_MAX_DIAGS|_CHAT_REASONING_MAX_OPERATIONS|_BUNDLE_TEXT_SUFFIXES|_BUNDLE_MAX_FILE_BYTES|_BUNDLE_MAX_TOTAL_BYTES)\s*=', line)
    if m:
        name = m.group(1)
        if name in constants_to_remove:
            removal_ranges.append((i, i))

# Sort and merge overlapping removal ranges
removal_ranges.sort()
merged = []
for start, end in removal_ranges:
    if merged and start <= merged[-1][1] + 1:
        merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    else:
        merged.append((start, end))

# Build new file content
keep_lines = []
removal_set = set()
for start, end in merged:
    for i in range(start, end + 1):
        removal_set.add(i)

for i, line in enumerate(lines):
    if i not in removal_set:
        keep_lines.append(line)

with open('vibecomfy/comfy_nodes/agent/edit.py', 'w') as f:
    f.writelines(keep_lines)

print(f"Removed {len(removal_set)} lines in {len(merged)} ranges")
for start, end in merged:
    print(f"  Lines {start+1}-{end+1}")
