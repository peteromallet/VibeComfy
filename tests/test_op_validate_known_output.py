"""Focused regression for the ``_known_output`` None-guard.

A node whose metadata carries ``_ui.outputs`` but no (or a ``None``)
``output_names`` entry used to crash with ``'NoneType' object is not
iterable`` in the name-set comprehension.  The membership check must be
evaluated only when ``output_names`` is a list or tuple.
"""

from __future__ import annotations

from types import SimpleNamespace

from vibecomfy.porting.edit._op_validate import _known_output


def _node(metadata: object) -> SimpleNamespace:
    return SimpleNamespace(metadata=metadata, class_type="TestNode")


def test_known_output_ui_outputs_without_output_names_does_not_raise() -> None:
    # output_names absent entirely.
    node = _node({"_ui": {"outputs": [{"name": "AUDIO"}, {"name": "VIDEO"}]}})
    assert _known_output(node, "AUDIO", None) is True
    assert _known_output(node, 0, None) is True  # matched via _ui.outputs index

    # output_names present but explicitly None.
    node = _node({"output_names": None, "_ui": {"outputs": ["VIDEO"]}})
    assert _known_output(node, "VIDEO", None) is True
    assert _known_output(node, 9, None) is False


def test_known_output_valid_output_names_still_match_by_name() -> None:
    node = _node(
        {
            "output_names": ["LATENT"],
            "_ui": {"outputs": [{"name": "OTHER"}]},
        }
    )
    assert _known_output(node, "LATENT", None) is True
    assert _known_output(node, "MISSING", None) is False


def test_known_output_falls_through_to_schema_branch_unchanged() -> None:
    node = _node({})
    assert _known_output(node, "ANY", None) is False
    assert _known_output(node, 0, None) is False
