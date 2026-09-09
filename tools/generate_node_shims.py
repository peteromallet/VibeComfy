"""Retired legacy wrapper generator.

Canonical node output is rendered by
``vibecomfy.porting.wrappers.codegen.render_pack``.  This module intentionally
contains no renderer and cannot write ``vibecomfy/nodes``; it remains only so
old invocations fail with an explicit migration instruction.
"""
from __future__ import annotations


def main() -> None:
    raise SystemExit(
        "tools.generate_node_shims is retired; use "
        "vibecomfy nodes generate-wrappers <pack>"
    )


if __name__ == "__main__":
    main()
