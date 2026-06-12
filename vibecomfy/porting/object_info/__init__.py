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
    check_output_arity_consensus,
    get_class,
    get_class_by_identity,
    has_class_identity,
    list_classes,
    ObjectInfoIdentity,
    ObjectInfoLookupResult,
    ObjectInfoLookupWarning,
    object_info_widget_order,
    output_names,
    require_class_output_count,
    reset_cache,
    resolve_class_entry,
    snapshot_version,
)
from vibecomfy.porting.object_info.serialize import (
    build_cache,
    CACHE_DIR,
    INDEX_PATH,
)

__all__ = [
    "get_class",
    "get_class_by_identity",
    "has_class_identity",
    "resolve_class_entry",
    "ObjectInfoIdentity",
    "ObjectInfoLookupResult",
    "ObjectInfoLookupWarning",
    "class_defaults",
    "class_input_types",
    "class_output_count",
    "class_has_list_output",
    "class_is_known",
    "check_output_arity_consensus",
    "require_class_output_count",
    "snapshot_version",
    "object_info_widget_order",
    "output_names",
    "list_classes",
    "reset_cache",
    "build_cache",
    "CACHE_DIR",
    "INDEX_PATH",
]
