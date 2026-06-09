"""Root-discoverable Sprint B acceptance wrappers.

This module intentionally re-exports only the shipped Sprint B scenarios from
the spec suite under ``docs/.../testing`` so root ``pytest`` discovery sees
them without duplicating test bodies.
"""

from docs.megaplan_chains.node_resolution_epic.testing.test_node_resolution_acceptance import (
    test_b6_ensure_env_installs_and_is_idempotent,
    test_b7_install_robustness,
    test_b8_provenance_determines_pack_set,
    test_b12_ideogram_ports_to_compiling_strict_ready_template,
)
