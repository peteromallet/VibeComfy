"""Fix agent_edit.py: remove moved functions and add re-export."""
import re

PATH = "vibecomfy/comfy_nodes/agent_edit.py"

with open(PATH) as f:
    content = f.read()
    lines = content.splitlines(keepends=True)

# Find all relevant function definitions
markers = {}
for i, line in enumerate(lines):
    for name in [
        "_batch_has_landed_edits",
        "_batch_budget_failure_kind",
        "_stage_agent_batch_repl",
        "_stage_load_python",
        "_stage_summarize",
    ]:
        if f"def {name}(" in line:
            if name not in markers:
                markers[name] = i
            else:
                markers[f"{name}_2"] = i

print("Markers found:")
for k, v in sorted(markers.items(), key=lambda x: x[1]):
    print(f"  L{v+1}: {k}")

# We want to remove:
# - _batch_has_landed_edits (marker to next def - 2 blank lines)
# - _batch_budget_failure_kind (marker to next def - blank lines)
# - _stage_agent_batch_repl (marker to next def)
# And add the re-export after the agent import block

# Strategy: mark the ranges to delete, then build new content
# Find where each function ends (the line before the next 'def ' at same or lesser indent)

def find_function_end(start_idx):
    """Find the end of a function definition (last line before next top-level def/class or EOF).
    
    A top-level definition has no leading whitespace before 'def ' or 'class '.
    """
    for j in range(start_idx + 1, len(lines)):
        line = lines[j]
        if line.startswith("def ") or line.startswith("class "):
            return j
    return len(lines)

# Find ranges to delete
batch_has = markers["_batch_has_landed_edits"]
batch_budget = markers["_batch_budget_failure_kind"]
batch_repl = markers["_stage_agent_batch_repl"]

batch_has_end = find_function_end(batch_has)
batch_budget_end = find_function_end(batch_budget)
batch_repl_end = find_function_end(batch_repl)

print(f"\nDelete ranges:")
print(f"  _batch_has_landed_edits: L{batch_has+1}-L{batch_has_end}")
print(f"  _batch_budget_failure_kind: L{batch_budget+1}-L{batch_budget_end}")
print(f"  _stage_agent_batch_repl: L{batch_repl+1}-L{batch_repl_end}")

# Also capture the blank lines before each function (up to 2 blank lines)
def find_preceding_blanks(start_idx):
    blank_count = 0
    idx = start_idx - 1
    while idx >= 0 and lines[idx].strip() == '':
        blank_count += 1
        idx -= 1
    return start_idx - blank_count

batch_has_start = find_preceding_blanks(batch_has)
batch_budget_start = find_preceding_blanks(batch_budget)
batch_repl_start = find_preceding_blanks(batch_repl)

print(f"  (with blanks) _batch_has_landed_edits: L{batch_has_start+1}-L{batch_has_end}")
print(f"  (with blanks) _batch_budget_failure_kind: L{batch_budget_start+1}-L{batch_budget_end}")
print(f"  (with blanks) _stage_agent_batch_repl: L{batch_repl_start+1}-L{batch_repl_end}")

# Merge overlapping/adjacent ranges
ranges = sorted([
    (batch_has_start, batch_has_end),
    (batch_budget_start, batch_budget_end),
    (batch_repl_start, batch_repl_end),
])

merged = []
for start, end in ranges:
    if merged and start <= merged[-1][1]:
        merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    else:
        merged.append((start, end))

print(f"\nMerged delete ranges: {[(s+1, e) for s, e in merged]}")

# Build new content
new_lines = []
skip_until = 0
for i, line in enumerate(lines):
    if i < skip_until:
        continue
    skip = False
    for start, end in merged:
        if start <= i < end:
            skip = True
            skip_until = end
            break
    if skip:
        # Replace with a single blank line if not at start of file
        if new_lines and new_lines[-1].strip() != '':
            new_lines.append('\n')
        continue
    new_lines.append(line)

# Now add the re-export after the agent import block
# Find "from .stages.agent import ("
re_export_inserted = False
final_lines = []
for i, line in enumerate(new_lines):
    final_lines.append(line)
    if not re_export_inserted and line.strip() == ')' and i > 0:
        # Check if previous lines contain the agent import
        # Look back for "from .stages.agent import ("
        context_start = max(0, i - 10)
        context = ''.join(new_lines[context_start:i+1])
        if 'from .stages.agent import (' in context:
            # This is the closing paren of the agent import
            # Check if batch_repl import already exists
            if 'from .stages.batch_repl import (' not in ''.join(final_lines):
                final_lines.append('\n')
                final_lines.append('from .stages.batch_repl import (\n')
                final_lines.append('    _batch_budget_failure_kind,\n')
                final_lines.append('    _batch_has_landed_edits,\n')
                final_lines.append('    _stage_agent_batch_repl,\n')
                final_lines.append(')\n')
                re_export_inserted = True

new_content = ''.join(final_lines)

with open(PATH, 'w') as f:
    f.write(new_content)

print(f"\nDone. New file: {len(new_content)} bytes, {new_content.count(chr(10))} lines")
