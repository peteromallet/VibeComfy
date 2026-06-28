#!/usr/bin/env python3
"""Identify line ranges to remove from edit.py after T5 extraction."""
import re

with open('vibecomfy/comfy_nodes/agent/edit.py', 'r') as f:
    lines = f.readlines()

# Find all function/class definitions with their end lines
# A function ends when a non-indented/non-blank line appears that is a new def/class or other top-level statement
# or when we encounter another function at the same indentation level

func_starts = []
for i, line in enumerate(lines):
    m = re.match(r'^(def|class)\s+(\w+)', line)
    if m:
        func_starts.append((i + 1, m.group(1), m.group(2)))

# Print all with end lines (next func start - 1)
for idx, (start, kind, name) in enumerate(func_starts):
    if idx + 1 < len(func_starts):
        end = func_starts[idx + 1][0] - 1
    else:
        end = len(lines)
    print(f"Lines {start}-{end}: {kind} {name}")
