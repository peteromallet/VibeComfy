from __future__ import annotations

# Lazy-load all submodules via __getattr__ to avoid circular imports during
# startup.  The thin shims at node_packs_lockfile.py etc. trigger loading of
# this package, and eagerly importing _install / _git here would pull in
# vibecomfy.registry (and transitively vibecomfy.ingest) before they are ready.

__all__ = [
    # _defs
    "CustomNodePack",
    "clear_known_node_packs_cache",
    "get_known_node_packs",
    "resolve_node_packs",
    "unresolved_class_types",
    # _git
    "InstalledPackGitRef",
    "find_installed_pack_ref",
    # _install
    "CORE_COMFY_CLASSES",
    "DEFAULT_INSTALL_ROOT",
    "INSTALL_STATE_DIR",
    "InstallBatchResult",
    "InstallResult",
    "InstallStatus",
    "PipPreflightResult",
    "Runner",
    "default_install_root",
    "install_pack",
    "install_required_packs",
    "missing_class_types_for_workflow",
    "missing_packs_for_workflow",
    "preflight_pip_requirements",
    "restore_pack",
    # _lockfile
    "LockEntry",
    "canonical_class_schema_projection",
    "canonical_pack_schema_projection",
    "compute_schema_hash",
    "read_lockfile",
    "upsert_lockfile_entry",
    "write_lockfile",
]

_MODULE_BY_ATTR: dict[str, str] = {}


def _init_module_map() -> dict[str, str]:
    """Build the attr→submodule mapping once."""
    global _MODULE_BY_ATTR
    if _MODULE_BY_ATTR:
        return _MODULE_BY_ATTR

    _defs_names = {
        "CustomNodePack",
        "clear_known_node_packs_cache",
        "get_known_node_packs",
        "resolve_node_packs",
        "unresolved_class_types",
    }
    _git_names = {"InstalledPackGitRef", "find_installed_pack_ref"}
    _install_names = {
        "CORE_COMFY_CLASSES",
        "DEFAULT_INSTALL_ROOT",
        "INSTALL_STATE_DIR",
        "InstallBatchResult",
        "InstallResult",
        "InstallStatus",
        "PipPreflightResult",
        "Runner",
        "default_install_root",
        "install_pack",
        "install_required_packs",
        "missing_class_types_for_workflow",
        "missing_packs_for_workflow",
        "preflight_pip_requirements",
        "restore_pack",
    }
    _lockfile_names = {
        "LockEntry",
        "canonical_class_schema_projection",
        "canonical_pack_schema_projection",
        "compute_schema_hash",
        "read_lockfile",
        "upsert_lockfile_entry",
        "write_lockfile",
    }
    for n in _defs_names:
        _MODULE_BY_ATTR[n] = "._defs"
    for n in _git_names:
        _MODULE_BY_ATTR[n] = "._git"
    for n in _install_names:
        _MODULE_BY_ATTR[n] = "._install"
    for n in _lockfile_names:
        _MODULE_BY_ATTR[n] = "._lockfile"
    return _MODULE_BY_ATTR


def __getattr__(name: str):
    import importlib

    _init_module_map()
    modname = _MODULE_BY_ATTR.get(name)
    if modname is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    mod = importlib.import_module(modname, __package__)
    attr = getattr(mod, name)
    # Cache in the module's globals so __getattr__ is not called again.
    globals()[name] = attr
    return attr
