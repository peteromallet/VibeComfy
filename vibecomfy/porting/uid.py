"""uid helpers. Signatures are frozen; the M1.5 ':' delimiter defect is fixed
for M2 (SD3, callers-3).

Identity is extrinsic only — NOT a content/WL hash and NOT uuid4.

Separators (SD3): the scope<->local separator is ``#`` and the scope-chain join
is ``/`` — both deliberately distinct from the ``:`` that may appear inside an
``sg_key`` (see ``vibecomfy.porting.scope``).  Flat uids (scope_path == "")
remain byte-identical to M1.5 with NO migration.
"""

from __future__ import annotations

# Scope<->local separator and scope-chain join. Distinct from ':' (sg_key) so a
# chained scope_path round-trips without the M1.5 first-colon partition defect.
SCOPE_LOCAL_SEP = "#"
SCOPE_CHAIN_JOIN = "/"


def make_uid(scope_path: str, local_uid: str) -> str:
    """Compose a fully-qualified uid from a scope path and local uid.

    Returns local_uid verbatim when scope_path is empty (flat uids unchanged),
    else f"{scope_path}{SCOPE_LOCAL_SEP}{local_uid}".
    """
    if scope_path == "":
        return local_uid
    return f"{scope_path}{SCOPE_LOCAL_SEP}{local_uid}"


def parse_uid(uid: str) -> tuple[str, str]:
    """Inverse of make_uid. Returns (scope_path, local_uid).

    Splits on the RIGHTMOST scope<->local separator so a chained scope_path
    (joined with ``/``) survives intact.  Returns ("", uid) for a bare scalar
    with no separator.
    """
    if SCOPE_LOCAL_SEP not in uid:
        return ("", uid)
    scope_path, _, local_uid = uid.rpartition(SCOPE_LOCAL_SEP)
    return (scope_path, local_uid)


def mint_local_uid(raw_ui_node: dict | None, fallback_id: str) -> str:
    """Derive a local uid from a raw litegraph node dict.

    Precedence:
    1. str(properties["vibecomfy_uid"]) if present in raw node
    2. str(raw_ui_node["id"]) — the litegraph integer node id
    3. fallback_id
    """
    if raw_ui_node is None:
        return fallback_id
    properties = raw_ui_node.get("properties") or {}
    vibecomfy_uid = properties.get("vibecomfy_uid")
    if vibecomfy_uid is not None:
        return str(vibecomfy_uid)
    node_id = raw_ui_node.get("id")
    if node_id is not None:
        return str(node_id)
    return fallback_id
