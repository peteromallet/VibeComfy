"""Batch script parsing and execution for workflow operations."""

import copy as copy_module
from typing import Dict, List, Tuple, Any, Optional
from . import workflow as wf_module
from . import editing


def parse_batch_script(script_path: str) -> List[Tuple[int, str, List[str]]]:
    """Parse a batch script file into operations.

    Returns list of (line_num, operation, args).
    """
    with open(script_path) as f:
        lines = f.readlines()

    operations = []
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        parts = line.split()
        if not parts:
            continue

        op = parts[0].lower()
        operations.append((line_num, op, parts[1:]))

    return operations


def execute_batch(wf: Dict, operations: List[Tuple[int, str, List[str]]],
                  dry_run: bool = False) -> Dict:
    """Execute batch operations on a workflow.

    Args:
        wf: Workflow dict (modified in place unless dry_run)
        operations: List of (line_num, operation, args) from parse_batch_script
        dry_run: If True, simulate on a copy without modifying original

    Returns:
        {
            'variables': dict of $name -> node_id,
            'details': list of operation detail strings,
            'errors': list of error messages,
            'warnings': list of warning messages,
        }
    """
    # In dry_run mode, work on a copy so variable resolution works
    if dry_run:
        wf = copy_module.deepcopy(wf)

    variables = {}  # $name -> node_id
    details = []
    errors = []
    warnings = []

    def resolve_var(val):
        """Resolve a variable reference to its node ID."""
        if isinstance(val, str) and val.startswith('$'):
            var_name = val[1:]
            if var_name not in variables:
                return None, f"Undefined variable '{val}'"
            return variables[var_name], None
        try:
            return int(val), None
        except ValueError:
            return None, f"Invalid node ID '{val}'"

    def parse_copy_args(op_args):
        """Parse copy arguments: node_id [as $var] [key=val ...]"""
        var_name = None
        set_values = {}
        i = 1
        while i < len(op_args):
            arg = op_args[i]
            if arg.lower() == 'as' and i + 1 < len(op_args):
                next_arg = op_args[i + 1]
                if next_arg.startswith('$'):
                    var_name = next_arg[1:]
                i += 2
            elif '=' in arg:
                key, val = arg.split('=', 1)
                try:
                    set_values[int(key)] = editing.parse_set_value(val)
                except ValueError:
                    set_values[key] = editing.parse_set_value(val)
                i += 1
            else:
                i += 1
        return var_name, set_values

    def parse_wire_args(op_args):
        """Parse wire arguments: src:slot -> dst:slot"""
        wire_str = ' '.join(op_args)
        wire_str = wire_str.replace('->', ' ').replace('→', ' ')
        parts = wire_str.split()

        if len(parts) < 2:
            return None, None, None, None, "wire requires source and destination"

        try:
            src_parts = parts[0].split(':')
            dst_parts = parts[1].split(':')
            src_id_str, src_slot_spec = src_parts[0], src_parts[1]
            dst_id_str, dst_slot_spec = dst_parts[0], dst_parts[1]
            return src_id_str, src_slot_spec, dst_id_str, dst_slot_spec, None
        except IndexError:
            return None, None, None, None, "Invalid wire format, use 'src:slot -> dst:slot'"

    def parse_create_args(op_args):
        """Parse create arguments: type [as $var] [-i name:type] [-O name:type]"""
        var_name = None
        inputs_def = []
        outputs_def = []

        i = 1
        while i < len(op_args):
            arg = op_args[i]
            if arg.lower() == 'as' and i + 1 < len(op_args):
                next_arg = op_args[i + 1]
                if next_arg.startswith('$'):
                    var_name = next_arg[1:]
                i += 2
            elif arg == '-i' and i + 1 < len(op_args):
                inp_spec = op_args[i + 1]
                if ':' in inp_spec:
                    name, dtype = inp_spec.split(':', 1)
                    inputs_def.append((name, dtype))
                i += 2
            elif arg == '-O' and i + 1 < len(op_args):
                out_spec = op_args[i + 1]
                if ':' in out_spec:
                    name, dtype = out_spec.split(':', 1)
                    outputs_def.append((name, dtype))
                i += 2
            else:
                i += 1

        return var_name, inputs_def, outputs_def

    for line_num, op, op_args in operations:

        if op == 'delete':
            # Resolve all node IDs
            node_ids = []
            for node_id_str in op_args:
                node_id, err = resolve_var(node_id_str)
                if err:
                    errors.append(f"Line {line_num}: {err}")
                    continue
                node_ids.append(node_id)

            if not node_ids:
                continue

            result = editing.delete_nodes(wf, node_ids)
            for w in result['warnings']:
                warnings.append(f"Line {line_num}: {w}")

            if result['deleted_nodes']:
                details.append(f"delete: removed nodes {sorted(result['deleted_nodes'])}")

        elif op == 'copy':
            if not op_args:
                errors.append(f"Line {line_num}: copy requires node ID")
                continue

            node_id, err = resolve_var(op_args[0])
            if err:
                errors.append(f"Line {line_num}: {err}")
                continue

            var_name, set_values = parse_copy_args(op_args)

            result = editing.copy_node(wf, node_id, set_values=set_values or None)
            if result.get('error'):
                errors.append(f"Line {line_num}: {result['error']}")
                continue

            new_id = result['new_id']
            if var_name:
                variables[var_name] = new_id
                details.append(f"copy: {node_id} → ${var_name} (ID {new_id})")
            else:
                details.append(f"copy: {node_id} → {new_id}")
            for warning in result.get('warnings', []):
                details.append(f"  Warning: {warning}")

        elif op == 'wire':
            src_id_str, src_slot_spec, dst_id_str, dst_slot_spec, err = parse_wire_args(op_args)
            if err:
                errors.append(f"Line {line_num}: {err}")
                continue

            src_id, err = resolve_var(src_id_str)
            if err:
                errors.append(f"Line {line_num}: Source {err}")
                continue

            dst_id, err = resolve_var(dst_id_str)
            if err:
                errors.append(f"Line {line_num}: Destination {err}")
                continue

            result = editing.wire_nodes(wf, src_id, src_slot_spec, dst_id, dst_slot_spec)
            if result.get('error'):
                errors.append(f"Line {line_num}: {result['error']}")
                continue

            details.append(f"wire: [{src_id}]:{result['src_slot']} → [{dst_id}]:{result['dst_slot']}")

        elif op == 'set':
            if len(op_args) < 2:
                errors.append(f"Line {line_num}: set requires node ID and values")
                continue

            node_id, err = resolve_var(op_args[0])
            if err:
                errors.append(f"Line {line_num}: {err}")
                continue

            values = {}
            for setter in op_args[1:]:
                if '=' not in setter:
                    continue
                key, val = setter.split('=', 1)
                try:
                    values[int(key)] = editing.parse_set_value(val)
                except ValueError:
                    values[key] = editing.parse_set_value(val)

            result = editing.set_widget_values(wf, node_id, values)
            if result.get('error'):
                errors.append(f"Line {line_num}: {result['error']}")
                continue

            details.append(f"set: node {node_id}")
            for warning in result.get('warnings', []):
                details.append(f"  Warning: {warning}")

        elif op == 'create':
            if not op_args:
                errors.append(f"Line {line_num}: create requires node type")
                continue

            node_type = op_args[0]
            var_name, inputs_def, outputs_def = parse_create_args(op_args)

            result = editing.create_node(wf, node_type,
                                         inputs=inputs_def or None,
                                         outputs=outputs_def or None)

            new_id = result['new_id']
            if var_name:
                variables[var_name] = new_id
                details.append(f"create: {node_type} → ${var_name} (ID {new_id})")
            else:
                details.append(f"create: {node_type} → {new_id}")

        else:
            warnings.append(f"Line {line_num}: Unknown operation '{op}'")

    return {
        'variables': variables,
        'details': details,
        'errors': errors,
        'warnings': warnings,
    }
