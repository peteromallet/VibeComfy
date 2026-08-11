"""Scaffold for the ORACLE-7 session decomposition (T-043, SPINE).

T-046 will move the ``_turn_state_machine`` extraction range out of
``vibecomfy.comfy_nodes.agent.session`` (the V2 turn-state transition
validation and the ``_mutate_turn_state`` state machine) into this module.
When filled, this module's ``__all__`` must list exactly the name set its range
contributes to the session namespace so ``session``'s
``from ._turn_state_machine import *`` façade reproduces the identical
top-level attributes — the same contract ``edit`` uses for its ``_frag_*``
fragments.  The extracted range contains one ``write_state_atomic`` call site,
so it must late-bind that name at call time (see T-043 ground truth S6).

Currently empty by design: the pinned session surface (S5, frozen manifest
23/31/23) is still defined directly in ``session``, so this module contributes
no names yet and imports cleanly as a no-op.
"""
