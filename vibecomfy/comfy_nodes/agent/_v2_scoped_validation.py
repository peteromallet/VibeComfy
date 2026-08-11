"""Scaffold for the ORACLE-7 session decomposition (T-043, SPINE).

T-045 will move the V2 scoped-validation helper ranges out of
``vibecomfy.comfy_nodes.agent.session`` (submit/candidate graph loading, delta
normalisation, graph indexing, scoped expected_old resolution, and the scoped
validation plan builder) into this module.  When filled, this module's
``__all__`` must list exactly the name set its ranges contribute to the session
namespace so ``session``'s ``from ._v2_scoped_validation import *`` façade
reproduces the identical top-level attributes — the same contract ``edit`` uses
for its ``_frag_*`` fragments.

Currently empty by design: the pinned session surface (S5, frozen manifest
23/31/23) is still defined directly in ``session``, so this module contributes
no names yet and imports cleanly as a no-op.
"""
