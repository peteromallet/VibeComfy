"""Characterization gate: deterministic behavioural snapshot suite.

Every test in this directory is gated behind ``@pytest.mark.characterization``
and MUST be run with ``PYTHONHASHSEED=0``.  The sentinel conftest enforces this
at collection time.
"""
