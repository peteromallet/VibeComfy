"""Public assertion library for testing `VibeWorkflow` graphs and compiled
API dicts.

Seven assertions are exported; every failure raises `AssertionError` with a
message that names the workflow id, the offending node id (where applicable),
and the offending field — the format is pinned in `_helpers.format_failure`.

Doctest examples use the synthetic factory from `vibecomfy.testing.fixtures`
(`make_workflow_factory`) — see T4. The doctests are written so they run
without `pytest`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vibecomfy.handles import Handle

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow

from vibecomfy.testing._helpers import (
    FAILURE_HINT_USE_ASSERT_EDGE,
    format_failure,
    is_api_link,
    is_ir_edge_ref,
    resolve_wf_id,
)
from vibecomfy.testing._schema import SchemaProviderLike

__all__ = [
    "assert_node_present",
    "assert_edge",
    "assert_input_value",
    "assert_output_kind",
    "assert_input_bound",
    "assert_compiles_cleanly",
    "assert_no_dangling_handles",
]


_SENTINEL: Any = object()


def assert_node_present(
    wf: VibeWorkflow,
    class_type: str,
    *,
    count: int | None = None,
) -> None:
    """Assert that `wf` contains at least one (or exactly `count`) node of
    `class_type`.

    >>> from vibecomfy.testing.fixtures import make_workflow_factory
    >>> wf = make_workflow_factory()(class_types=["KSampler"])
    >>> assert_node_present(wf, "KSampler")
    >>> assert_node_present(wf, "KSampler", count=1)
    """
    wf_id = resolve_wf_id(wf)
    matches = [n for n in wf.nodes.values() if n.class_type == class_type]
    got = len(matches)
    if count is None:
        if got < 1:
            raise AssertionError(
                format_failure(
                    wf_id,
                    "assert_node_present",
                    f"no node with class_type={class_type!r} found",
                    node_id=None,
                    field="class_type",
                    expected=class_type,
                    got=got,
                )
            )
    else:
        if got != count:
            raise AssertionError(
                format_failure(
                    wf_id,
                    "assert_node_present",
                    f"node count mismatch for class_type={class_type!r}",
                    node_id=None,
                    field="class_type",
                    expected=count,
                    got=got,
                )
            )


def assert_edge(
    wf: VibeWorkflow,
    from_node_id: str,
    to_node_id: str,
    *,
    to_input: str | None = None,
) -> None:
    """Assert that an edge from `from_node_id` -> `to_node_id` exists. If
    `to_input` is provided, the edge must target that input name.

    >>> from vibecomfy.testing.fixtures import make_workflow_factory
    >>> wf = make_workflow_factory()(edges=[("1", "2", "model")])
    >>> assert_edge(wf, "1", "2")
    >>> assert_edge(wf, "1", "2", to_input="model")
    """
    wf_id = resolve_wf_id(wf)
    from_key = str(from_node_id)
    to_key = str(to_node_id)
    matches = [
        e
        for e in wf.edges
        if str(e.from_node) == from_key and str(e.to_node) == to_key
        and (to_input is None or e.to_input == to_input)
    ]
    if not matches:
        raise AssertionError(
            format_failure(
                wf_id,
                "assert_edge",
                f"no edge {from_key!r} -> {to_key!r}"
                + (f" on input {to_input!r}" if to_input is not None else ""),
                node_id=to_key,
                field=to_input,
                expected=f"edge {from_key}->{to_key}",
                got=[(str(e.from_node), str(e.to_node), e.to_input) for e in wf.edges],
            )
        )


def assert_input_value(
    wf_or_api: VibeWorkflow | dict,
    node_id: str,
    input_name: str,
    expected: Any,
) -> None:
    """Assert that the input/widget at `node_id.input_name` equals `expected`.

    Two explicit modes:

    - IR mode (`isinstance(wf_or_api, VibeWorkflow)`): read `node.inputs[name]`
      then `node.widgets[name]`. Reject `Handle` instances and 2-tuple edge
      refs with a hint pointing at `assert_edge`.
    - API-dict mode (`isinstance(wf_or_api, dict)`): read
      `api[node_id]['inputs'][input_name]`. Reject `[str, int]` link refs with
      the same hint.

    >>> from vibecomfy.testing.fixtures import make_workflow_factory
    >>> wf = make_workflow_factory()(class_types=["KSampler"], widgets={"1": {"cfg": 7.0}})
    >>> assert_input_value(wf, "1", "cfg", 7.0)
    """
    from vibecomfy.workflow import VibeWorkflow  # lazy: avoid testing↔workflow import cycle

    wf_id = resolve_wf_id(wf_or_api)
    if isinstance(wf_or_api, VibeWorkflow):
        node = wf_or_api.nodes.get(str(node_id))
        if node is None:
            raise AssertionError(
                format_failure(
                    wf_id,
                    "assert_input_value",
                    f"node {node_id!r} not found in workflow",
                    node_id=node_id,
                    field=input_name,
                    expected=expected,
                    got=None,
                )
            )
        if input_name in node.inputs:
            got = node.inputs[input_name]
            origin = "inputs"
        elif input_name in node.widgets:
            got = node.widgets[input_name]
            origin = "widgets"
        else:
            raise AssertionError(
                format_failure(
                    wf_id,
                    "assert_input_value",
                    f"input {input_name!r} not present on node {node_id!r}",
                    node_id=node_id,
                    field=input_name,
                    expected=expected,
                    got=None,
                )
            )
        if is_ir_edge_ref(got):
            raise AssertionError(
                format_failure(
                    wf_id,
                    "assert_input_value",
                    f"{origin}[{input_name!r}] holds an edge reference; cannot compare",
                    node_id=node_id,
                    field=input_name,
                    expected=expected,
                    got=got,
                    hint=FAILURE_HINT_USE_ASSERT_EDGE,
                )
            )
        if got != expected:
            raise AssertionError(
                format_failure(
                    wf_id,
                    "assert_input_value",
                    f"{origin}[{input_name!r}] value mismatch",
                    node_id=node_id,
                    field=input_name,
                    expected=expected,
                    got=got,
                )
            )
        return

    if isinstance(wf_or_api, dict):
        node_entry = wf_or_api.get(str(node_id))
        if not isinstance(node_entry, dict):
            raise AssertionError(
                format_failure(
                    wf_id,
                    "assert_input_value",
                    f"node {node_id!r} not found in API dict",
                    node_id=node_id,
                    field=input_name,
                    expected=expected,
                    got=None,
                )
            )
        inputs = node_entry.get("inputs") or {}
        if input_name not in inputs:
            raise AssertionError(
                format_failure(
                    wf_id,
                    "assert_input_value",
                    f"input {input_name!r} not present on API node {node_id!r}",
                    node_id=node_id,
                    field=input_name,
                    expected=expected,
                    got=None,
                )
            )
        got = inputs[input_name]
        if is_api_link(got):
            raise AssertionError(
                format_failure(
                    wf_id,
                    "assert_input_value",
                    f"inputs[{input_name!r}] holds a link reference; cannot compare",
                    node_id=node_id,
                    field=input_name,
                    expected=expected,
                    got=got,
                    hint=FAILURE_HINT_USE_ASSERT_EDGE,
                )
            )
        if got != expected:
            raise AssertionError(
                format_failure(
                    wf_id,
                    "assert_input_value",
                    f"inputs[{input_name!r}] value mismatch",
                    node_id=node_id,
                    field=input_name,
                    expected=expected,
                    got=got,
                )
            )
        return

    raise TypeError(
        "assert_input_value: wf_or_api must be a VibeWorkflow or API dict, "
        f"got {type(wf_or_api).__name__}"
    )


_SAVE_KIND_TO_CLASSES = {
    "SaveImage": ("SaveImage",),
    "image": ("SaveImage",),
    "SaveVideo": ("SaveVideo", "VHS_VideoCombine"),
    "video": ("SaveVideo", "VHS_VideoCombine"),
    "SaveAudio": ("SaveAudio", "SaveAudioMP3", "VHS_AudioSave"),
    "audio": ("SaveAudio", "SaveAudioMP3", "VHS_AudioSave"),
}


def assert_output_kind(wf: VibeWorkflow, expected_kind: str) -> None:
    """Assert that `wf.outputs` contains an output node matching `expected_kind`.

    `expected_kind` accepts either a literal class name (`'SaveImage'`,
    `'SaveAudioMP3'`) or a high-level kind (`'image'`, `'video'`, `'audio'`).

    >>> from vibecomfy.testing.fixtures import make_workflow_factory
    >>> wf = make_workflow_factory()(class_types=["SaveImage"]).finalize_metadata()
    >>> assert_output_kind(wf, "image")
    >>> assert_output_kind(wf, "SaveImage")
    """
    wf_id = resolve_wf_id(wf)
    accepted = _SAVE_KIND_TO_CLASSES.get(expected_kind, (expected_kind,))
    found = [o for o in wf.outputs if o.output_type in accepted]
    if not found:
        got_classes = [o.output_type for o in wf.outputs]
        raise AssertionError(
            format_failure(
                wf_id,
                "assert_output_kind",
                f"no output node matches kind {expected_kind!r}",
                node_id=None,
                field="output_type",
                expected=list(accepted),
                got=got_classes,
            )
        )


def assert_input_bound(
    wf: VibeWorkflow,
    input_name: str,
    *,
    node_id: str | None = None,
    field: str | None = None,
    default: Any = _SENTINEL,
) -> None:
    """Assert that `wf.inputs[input_name]` is registered, optionally pinned to
    a specific `node_id`/`field`/`default`.

    >>> from vibecomfy.testing.fixtures import make_workflow_factory
    >>> wf = make_workflow_factory()(class_types=["CLIPTextEncode"], widgets={"1": {"text": "hi"}})
    >>> wf.register_input("prompt", "1", "text", value="hi")  # doctest: +ELLIPSIS
    VibeWorkflow(...)
    >>> assert_input_bound(wf, "prompt")
    >>> assert_input_bound(wf, "prompt", node_id="1", field="text")
    """
    wf_id = resolve_wf_id(wf)
    binding = wf.inputs.get(input_name)
    if binding is None:
        raise AssertionError(
            format_failure(
                wf_id,
                "assert_input_bound",
                f"input {input_name!r} is not registered",
                node_id=node_id,
                field=field,
                expected=input_name,
                got=list(wf.inputs.keys()),
            )
        )
    if node_id is not None and str(binding.node_id) != str(node_id):
        raise AssertionError(
            format_failure(
                wf_id,
                "assert_input_bound",
                f"input {input_name!r} is bound to a different node",
                node_id=binding.node_id,
                field=binding.field,
                expected=node_id,
                got=binding.node_id,
            )
        )
    if field is not None and binding.field != field:
        raise AssertionError(
            format_failure(
                wf_id,
                "assert_input_bound",
                f"input {input_name!r} is bound to a different field",
                node_id=binding.node_id,
                field=binding.field,
                expected=field,
                got=binding.field,
            )
        )
    if default is not _SENTINEL and binding.default != default:
        raise AssertionError(
            format_failure(
                wf_id,
                "assert_input_bound",
                f"input {input_name!r} default mismatch",
                node_id=binding.node_id,
                field=binding.field,
                expected=default,
                got=binding.default,
            )
        )


def assert_compiles_cleanly(
    wf: VibeWorkflow,
    *,
    schema_provider: SchemaProviderLike | None = None,
) -> None:
    """Assert `wf.compile('api')` succeeds AND `wf.validate(schema_provider=...)`
    reports no `severity=='error'` issues and no `code=='api_compile_failed'`
    warnings.

    The compile and the validate are run in separate try/except blocks: a
    compile exception is always surfaced as an `AssertionError` naming the
    workflow id; a validate exception is reraised as an `AssertionError` for
    the same reason. `code=='api_compile_failed'` issues are treated as hard
    errors even when `wf.validate` records them at `severity='warning'`.

    >>> from vibecomfy.testing.fixtures import make_workflow_factory
    >>> wf = make_workflow_factory()(class_types=["SaveImage"])
    >>> assert_compiles_cleanly(wf)
    """
    wf_id = resolve_wf_id(wf)
    try:
        wf.compile("api")
    except Exception as exc:  # noqa: BLE001 — re-raised as AssertionError
        raise AssertionError(
            format_failure(
                wf_id,
                "assert_compiles_cleanly",
                f"wf.compile('api') raised {type(exc).__name__}: {exc}",
                node_id=None,
                field=None,
                expected="clean compile",
                got=repr(exc),
            )
        ) from exc

    try:
        report = wf.validate(schema_provider=schema_provider)
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(
            format_failure(
                wf_id,
                "assert_compiles_cleanly",
                f"wf.validate raised {type(exc).__name__}: {exc}",
                node_id=None,
                field=None,
                expected="clean validate",
                got=repr(exc),
            )
        ) from exc

    offending: list[str] = []
    for issue in report.issues:
        if issue.severity == "error" or issue.code == "api_compile_failed":
            offending.append(f"{issue.code}:{issue.severity}:{issue.message}")
    if offending:
        raise AssertionError(
            format_failure(
                wf_id,
                "assert_compiles_cleanly",
                "wf.validate produced blocking issues",
                node_id=None,
                field=None,
                expected="no errors and no api_compile_failed",
                got=offending,
            )
        )


def assert_no_dangling_handles(wf: VibeWorkflow) -> None:
    """Assert that every `Handle` produced has been wired and every edge
    endpoint references a node that exists.

    Flags:

    - any `node.inputs[name]` whose value `isinstance(_, Handle)` (a handle
      that was never consumed by `connect()`/`replace_edge()`); and
    - any edge in `wf.edges` whose `from_node`/`to_node` is absent from
      `wf.nodes`.

    >>> from vibecomfy.testing.fixtures import make_workflow_factory
    >>> wf = make_workflow_factory()(class_types=["KSampler"])
    >>> assert_no_dangling_handles(wf)
    """
    wf_id = resolve_wf_id(wf)
    problems: list[str] = []
    for node_id, node in wf.nodes.items():
        for input_name, value in list(node.inputs.items()):
            if isinstance(value, Handle):
                problems.append(
                    format_failure(
                        wf_id,
                        "assert_no_dangling_handles",
                        f"inputs[{input_name!r}] still holds an unwired Handle",
                        node_id=node_id,
                        field=input_name,
                        expected="connected edge",
                        got=value,
                    )
                )
    for index, edge in enumerate(wf.edges):
        if str(edge.from_node) not in wf.nodes:
            problems.append(
                format_failure(
                    wf_id,
                    "assert_no_dangling_handles",
                    f"edge #{index} from_node {edge.from_node!r} missing from wf.nodes",
                    node_id=edge.from_node,
                    field=edge.to_input,
                    expected="node present",
                    got=None,
                )
            )
        if str(edge.to_node) not in wf.nodes:
            problems.append(
                format_failure(
                    wf_id,
                    "assert_no_dangling_handles",
                    f"edge #{index} to_node {edge.to_node!r} missing from wf.nodes",
                    node_id=edge.to_node,
                    field=edge.to_input,
                    expected="node present",
                    got=None,
                )
            )
    if problems:
        raise AssertionError("\n".join(problems))
