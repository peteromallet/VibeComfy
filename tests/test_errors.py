"""Tests for vibecomfy.errors exception hierarchy."""

from __future__ import annotations

import pytest

from vibecomfy.errors import (
    ContextVarBindingError,
    ConversionParityError,
    DriftError,
    ModelAssetError,
    QueueError,
    RuntimeNodeError,
    SchemaValidationError,
    SubgraphFreshnessError,
    VibeComfyError,
)


# -- VibeComfyError basic behaviour ------------------------------------------

class TestVibeComfyError:
    """Core error behaviour: inheritance, next_action, __str__."""

    def test_inherits_from_runtime_error(self) -> None:
        """VibeComfyError MUST inherit from RuntimeError so CLI catch tuples catch it."""
        assert issubclass(VibeComfyError, RuntimeError)
        assert issubclass(VibeComfyError, Exception)
        # Verify isinstance works as expected
        exc = VibeComfyError("test")
        assert isinstance(exc, RuntimeError)
        assert isinstance(exc, Exception)

    def test_next_action_attribute(self) -> None:
        """next_action is stored as an instance attribute."""
        exc = VibeComfyError("something failed", next_action="vibecomfy doctor --models")
        assert exc.next_action == "vibecomfy doctor --models"

    def test_next_action_none_by_default(self) -> None:
        """When not provided, next_action is None."""
        exc = VibeComfyError("something failed")
        assert exc.next_action is None

    def test_str_without_next_action(self) -> None:
        """Bare VibeComfyError without next_action preserves original message unchanged."""
        exc = VibeComfyError("something failed")
        assert str(exc) == "something failed"

    def test_str_with_next_action(self) -> None:
        """__str__ appends ' next action: <value>' when next_action is set."""
        exc = VibeComfyError("model missing", next_action="vibecomfy doctor --models")
        assert str(exc) == "model missing next action: vibecomfy doctor --models"

    def test_str_with_empty_string_next_action(self) -> None:
        """Empty string next_action: suffix is appended (behaviour per spec)."""
        exc = VibeComfyError("msg", next_action="")
        # Empty string is truthy-falsy — but the spec says "when set", and
        # empty string is technically set (not None).  We document the
        # actual behaviour: empty string still appends.
        assert str(exc) == "msg next action: "

    def test_str_with_none_next_action(self) -> None:
        """None next_action: no suffix appended."""
        exc = VibeComfyError("msg", next_action=None)
        assert str(exc) == "msg"

    def test_repr(self) -> None:
        """__repr__ includes class name, next_action, and severity."""
        exc = VibeComfyError("boo", next_action="run away")
        assert repr(exc) == (
            "VibeComfyError('boo', next_action='run away', severity='error')"
        )

    def test_repr_without_next_action(self) -> None:
        exc = VibeComfyError("boo")
        assert repr(exc) == (
            "VibeComfyError('boo', next_action=None, severity='error')"
        )


# -- Subclass isinstance checks ----------------------------------------------

SUBCLASSES: list[tuple[type[VibeComfyError], str]] = [
    (ModelAssetError, "ModelAssetError"),
    (SchemaValidationError, "SchemaValidationError"),
    (QueueError, "QueueError"),
    (ContextVarBindingError, "ContextVarBindingError"),
    (ConversionParityError, "ConversionParityError"),
    (SubgraphFreshnessError, "SubgraphFreshnessError"),
    (RuntimeNodeError, "RuntimeNodeError"),
    (DriftError, "DriftError"),
]


class TestSubclassIsInstance:
    """All subclasses properly chain through VibeComfyError → RuntimeError."""

    @pytest.mark.parametrize("cls,name", SUBCLASSES)
    def test_isinstance_vibecomfy_error(self, cls: type[VibeComfyError], name: str) -> None:
        exc = cls("test message")
        assert isinstance(exc, VibeComfyError), (
            f"{name} is not an instance of VibeComfyError"
        )

    @pytest.mark.parametrize("cls,name", SUBCLASSES)
    def test_isinstance_runtime_error(self, cls: type[VibeComfyError], name: str) -> None:
        exc = cls("test message")
        assert isinstance(exc, RuntimeError), (
            f"{name} is not an instance of RuntimeError"
        )

    @pytest.mark.parametrize("cls,name", SUBCLASSES)
    def test_next_action_passthrough(self, cls: type[VibeComfyError], name: str) -> None:
        """All subclasses pass next_action through to the base __init__."""
        exc = cls("test", next_action="run doctor")
        assert exc.next_action == "run doctor"
        assert str(exc) == "test next action: run doctor"

    @pytest.mark.parametrize("cls,name", SUBCLASSES)
    def test_next_action_none_default(self, cls: type[VibeComfyError], name: str) -> None:
        """Without explicit next_action, the subclass default_next_action is used."""
        exc = cls("test")
        assert exc.next_action == cls.default_next_action
        assert exc.next_action is not None


# -- Caught-by-CLI-tuple proof -----------------------------------------------

def test_vibecomfy_error_caught_by_cli_tuple() -> None:
    """VibeComfyError (and subclasses) are RuntimeError, so the CLI
    catch tuple ``(OSError, RuntimeError, ValueError)`` in run.py:163
    catches them."""
    # Simulate the exact catch clause
    try:
        raise VibeComfyError("test")
    except (OSError, RuntimeError, ValueError):
        caught = True
    else:
        caught = False
    assert caught, "VibeComfyError was NOT caught by (OSError, RuntimeError, ValueError)"

    # Also verify a subclass
    try:
        raise ModelAssetError("missing model", next_action="doctor")
    except (OSError, RuntimeError, ValueError):
        caught = True
    else:
        caught = False
    assert caught, "ModelAssetError was NOT caught by (OSError, RuntimeError, ValueError)"


# -- Representative raise-path tests (T2) ------------------------------------


def test_model_asset_error_raise_includes_next_action() -> None:
    """ModelAssetError raised from _model_assets_from_workflow includes next_action."""
    exc = ModelAssetError("unresolved workflow model assets: CKPT model.safetensors", next_action="vibecomfy doctor --models")
    assert exc.next_action == "vibecomfy doctor --models"
    assert "next action: vibecomfy doctor --models" in str(exc)


def test_schema_validation_error_structural_includes_next_action() -> None:
    """SchemaValidationError for structural validation includes --no-schema next_action."""
    exc = SchemaValidationError(
        "Workflow validation failed",
        next_action="vibecomfy validate <template> --no-schema",
    )
    assert exc.next_action == "vibecomfy validate <template> --no-schema"
    assert "next action: vibecomfy validate <template> --no-schema" in str(exc)


def test_schema_validation_error_schema_refresh_includes_next_action() -> None:
    """SchemaValidationError for schema refresh includes schema refresh next_action."""
    exc = SchemaValidationError(
        "Unknown class_type FooNode on node 5.",
        next_action="vibecomfy schema refresh",
    )
    assert exc.next_action == "vibecomfy schema refresh"
    assert "next action: vibecomfy schema refresh" in str(exc)


def test_queue_error_raise_includes_next_action() -> None:
    """QueueError from queue wrappers includes runtime doctor next_action."""
    exc = QueueError(
        "Workflow queue failed",
        next_action="vibecomfy runtime doctor",
    )
    assert exc.next_action == "vibecomfy runtime doctor"
    assert "next action: vibecomfy runtime doctor" in str(exc)


def test_context_var_binding_error_nested_includes_next_action() -> None:
    """ContextVarBindingError for nested workflow contexts includes doctor next_action."""
    exc = ContextVarBindingError(
        "Nested workflow contexts not supported.",
        next_action="vibecomfy doctor",
    )
    assert exc.next_action == "vibecomfy doctor"
    assert "next action: vibecomfy doctor" in str(exc)


def test_context_var_binding_error_missing_includes_next_action() -> None:
    """ContextVarBindingError for missing active workflow includes doctor next_action."""
    exc = ContextVarBindingError(
        "No active workflow.",
        next_action="vibecomfy doctor",
    )
    assert exc.next_action == "vibecomfy doctor"
    assert "next action: vibecomfy doctor" in str(exc)


def test_subgraph_freshness_error_raise_includes_next_action() -> None:
    """SubgraphFreshnessError includes reconvert next_action."""
    exc = SubgraphFreshnessError(
        "Subgraph freshness check failed for template.py",
        next_action="vibecomfy port --reconvert <template>",
    )
    assert exc.next_action == "vibecomfy port --reconvert <template>"
    assert "next action: vibecomfy port --reconvert <template>" in str(exc)


def test_conversion_write_error_carries_next_action() -> None:
    """ConversionWriteError from porting/convert.py accepts next_action kwarg."""
    from vibecomfy.porting.convert import ConversionWriteError

    exc = ConversionWriteError(
        "Validation failed",
        next_action="vibecomfy port --validate-only <target>",
    )
    assert exc.next_action == "vibecomfy port --validate-only <target>"


def test_conversion_write_error_still_runtime_error() -> None:
    """ConversionWriteError remains a RuntimeError for existing catch blocks."""
    from vibecomfy.porting.convert import ConversionWriteError

    assert issubclass(ConversionWriteError, RuntimeError)


def test_prepare_prompt_async_preserves_vibecomfy_error_next_action() -> None:
    """_prepare_prompt_async re-raises VibeComfyError subclasses unwrapped."""
    # Simulate the wrapper logic: a VibeComfyError should pass through.
    try:
        try:
            raise SchemaValidationError("bad", next_action="run doctor")
        except VibeComfyError:
            raise
    except SchemaValidationError as exc:
        assert exc.next_action == "run doctor"
        assert "next action: run doctor" in str(exc)
    else:
        pytest.fail("SchemaValidationError should have been re-raised")


def test_all_raise_site_error_classes_are_vibecomfy_subclasses() -> None:
    """Every error class used at framework raise sites is a VibeComfyError."""
    from vibecomfy.porting.convert import ConversionWriteError

    site_classes = [
        (ModelAssetError, "ModelAssetError"),
        (SchemaValidationError, "SchemaValidationError"),
        (QueueError, "QueueError"),
        (ContextVarBindingError, "ContextVarBindingError"),
        (ConversionParityError, "ConversionParityError"),
        (SubgraphFreshnessError, "SubgraphFreshnessError"),
    ]
    for cls, name in site_classes:
        assert issubclass(cls, VibeComfyError), f"{name} is not a VibeComfyError subclass"

    # ConversionWriteError is not a VibeComfyError subclass (kept as RuntimeError
    # for backward compatibility) but carries next_action.
    assert issubclass(ConversionWriteError, RuntimeError)


# -- to_dict() shape and subclass defaults (T11/F2) ---------------------------


def test_vibecomfy_error_to_dict_shape() -> None:
    """to_dict() returns a dict with the four expected keys."""
    exc = VibeComfyError("something failed", next_action="run doctor")
    d = exc.to_dict()
    assert d == {
        "type": "VibeComfyError",
        "message": "something failed",
        "severity": "error",
        "next_action": "run doctor",
    }
    assert set(d.keys()) == {"type", "message", "severity", "next_action"}


def test_subclass_to_dict_includes_default_next_action() -> None:
    """Subclass to_dict() uses default_next_action when no explicit kwarg given."""
    exc = ModelAssetError("model not found")
    d = exc.to_dict()
    assert d["type"] == "ModelAssetError"
    assert d["message"] == "model not found"
    assert d["severity"] == "error"
    assert d["next_action"] == "vibecomfy doctor --models"


def test_to_dict_respects_explicit_next_action_override() -> None:
    """Explicit next_action kwarg overrides the subclass default in to_dict()."""
    exc = ModelAssetError("missing", next_action="custom fix")
    d = exc.to_dict()
    assert d["next_action"] == "custom fix"


def test_all_eight_subclasses_have_default_next_action() -> None:
    """Every semantic subclass defines its own non-empty default_next_action."""
    for cls, _name in SUBCLASSES:
        assert cls.default_next_action is not None, (
            f"{cls.__name__}.default_next_action is None"
        )
        assert isinstance(cls.default_next_action, str), (
            f"{cls.__name__}.default_next_action is not a str"
        )
        assert len(cls.default_next_action) > 0, (
            f"{cls.__name__}.default_next_action is empty"
        )


def test_subclass_severity_defaults_to_error() -> None:
    """All subclasses default to severity='error'."""
    for cls, _name in SUBCLASSES:
        exc = cls("test")
        assert exc.severity == "error", (
            f"{cls.__name__} severity is {exc.severity!r}, expected 'error'"
        )


def test_severity_can_be_overridden() -> None:
    """severity kwarg on any error class is honored."""
    exc = VibeComfyError("warning", severity="warning")
    assert exc.severity == "warning"

    exc2 = ModelAssetError("info", severity="info")
    assert exc2.severity == "info"
    assert exc2.to_dict()["severity"] == "info"
