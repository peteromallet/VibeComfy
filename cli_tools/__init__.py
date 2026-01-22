"""CLI tools for ComfyUI workflow manipulation."""

from . import workflow
from . import analysis
from . import editing
from . import batch
from . import visualization
from . import fetch

# Convenience exports for common functions
from .workflow import load, save, get_nodes_dict, get_links_dict, build_adjacency
from .analysis import analyze_workflow, find_path, find_upstream, find_downstream, get_node_role
from .editing import copy_node, wire_nodes, delete_nodes, set_widget_values
from .descriptions import NODE_DESCRIPTIONS, get_node_description
