"""Identity sub-package: uid, scope, and slot-codec primitives."""

from .codec import (
    build_reverse_map,
    encode_slot_names,
    to_python_identifier,
    to_raw_name,
)
from .scope import (
    compose_scope_path,
    mint_inner_uid,
    sanitize_subgraph_name,
    sg_key,
)
from .uid import (
    SCOPE_CHAIN_JOIN,
    SCOPE_LOCAL_SEP,
    make_uid,
    mint_local_uid,
    parse_uid,
)

__all__ = [
    # .uid
    "SCOPE_LOCAL_SEP",
    "SCOPE_CHAIN_JOIN",
    "make_uid",
    "parse_uid",
    "mint_local_uid",
    # .scope
    "compose_scope_path",
    "mint_inner_uid",
    "sanitize_subgraph_name",
    "sg_key",
    # .codec
    "to_python_identifier",
    "to_raw_name",
    "encode_slot_names",
    "build_reverse_map",
]
