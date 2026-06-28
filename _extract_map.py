#!/usr/bin/env python3
"""Map function/class positions in edit.py"""
import re

with open('vibecomfy/comfy_nodes/agent/edit.py', 'r') as f:
    lines = f.readlines()

func_starts = {}
for i, line in enumerate(lines, 1):
    m = re.match(r'^(def|class)\s+(\w+)', line)
    if m:
        func_starts[i] = (m.group(1), m.group(2))

for line_num, (kind, name) in sorted(func_starts.items()):
    print(f"{line_num:5d}: {kind} {name}")
