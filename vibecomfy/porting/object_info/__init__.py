"""Structured object_info cache for per-class ComfyUI node schema lookups.

Built from a ComfyUI ``object_info`` JSON dump (e.g. a RunPod snapshot).
Provides deterministic per-pack cache files and a lazy consumer API.
"""

from vibecomfy.porting.object_info.consume import (
    class_defaults,
    class_has_list_output,
    class_input_types,
    class_is_known,
    class_output_count,
    get_class,
    list_classes,
    object_info_widget_order,
    output_names,
    require_class_output_count,
    snapshot_version,
)
from vibecomfy.porting.object_info.serialize import (
    build_cache,
    CACHE_DIR,
    INDEX_PATH,
)

__all__ = [
    "get_class",
    "class_defaults",
    "class_input_types",
    "class_output_count",
    "class_has_list_output",
    "class_is_known",
    "require_class_output_count",
    "snapshot_version",
    "object_info_widget_order",
    "output_names",
    "list_classes",
    "build_cache",
    "CACHE_DIR",
    "INDEX_PATH",
]
