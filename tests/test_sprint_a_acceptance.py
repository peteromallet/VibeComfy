"""Root-discoverable Sprint A acceptance wrappers.

This module intentionally re-exports only the shipped Sprint A scenarios from
the spec suite under ``docs/.../testing`` so root ``pytest`` discovery sees
them without duplicating test bodies.
"""

from docs.megaplan_chains.node_resolution_epic.testing.test_node_resolution_acceptance import (
    test_a1_ideogram_no_silent_miscompile,
    test_a2_fail_closed_on_known_node_arity_disagreement,
    test_a3_core_refresh_does_not_clobber_custom_packs,
    test_a4_io_schema_nodes_covered,
    test_a5_identity_keyed_cache_and_drift,
)

