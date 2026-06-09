"""Root-discoverable Sprint C acceptance wrappers.

This module intentionally re-exports only the shipped Sprint C scenarios from
the spec suite under ``docs/.../testing`` so root ``pytest`` discovery sees
them without duplicating test bodies.
"""

from docs.megaplan_chains.node_resolution_epic.testing.test_node_resolution_acceptance import (
    test_c9_faithful_version_pinning,
    test_c10_provenance_less_warns_never_silent_latest,
    test_c11_snapshot_regenerable_per_pack,
    test_c12_ideogram_ports_at_authored_versions,
)
