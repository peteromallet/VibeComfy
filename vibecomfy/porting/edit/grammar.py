"""Single machine-readable grammar for the Python edit surface.

One definition generates every consumer of the surface language:

* the AST admission set the parser walks
* the agent-facing prompt documentation
* the §3 table in ``docs/architecture/python_authoring_edit_surface.md``

There is no second hand-maintained copy of the statement forms, the
admitted AST types, or the forbidden verbs (``reorder``, ``set_title``).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from vibecomfy.executor.tool_specs import AGENT_TOOL_CALL_NAMES


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StatementForm:
    """One statement the surface accepts (or a documented query/control)."""

    form_id: str
    surface: str
    op: str | None
    interpreter: str
    ast_types: tuple[type[ast.AST], ...]
    in_doc_table: bool = True
    in_prompt: bool = True
    # RHS shape that discriminates this assignment form from the others
    # ("mode" | "none" | "graph_ref" | "literal").  Drives the generated
    # statement-shape → op-kind mapping (``op_kind_for_assignment``) so the
    # parser never hand-maintains a second list.  ``None`` for non-assignment
    # forms (add_node is classified as ``node_call`` by statement shape).
    assignment_shape: str | None = None


@dataclass(frozen=True, slots=True)
class ForbiddenForm:
    """A form the surface rejects, with the diagnostic the parser emits."""

    form_id: str
    surface: str
    code: str
    reason: str
    ast_types: tuple[type[ast.AST], ...] = ()
    call_names: tuple[str, ...] = ()
    assign_attrs: tuple[str, ...] = ()


# Designed edit forms — Law 4 / architecture §3.
STATEMENT_FORMS: tuple[StatementForm, ...] = (
    StatementForm(
        form_id="set_node_field",
        surface="`node.field = literal`",
        op="set_node_field",
        interpreter=(
            "fold the RHS as a literal (const/list/dict, or a const-folded "
            "`BinOp`); reject names/calls"
        ),
        ast_types=(ast.Assign, ast.Attribute, ast.Name, ast.Constant, ast.List, ast.Tuple, ast.Dict, ast.BinOp),
        assignment_shape="literal",
    ),
    StatementForm(
        form_id="add_node",
        surface="`var = Class(field=…, inp=src.SLOT, near=…)`",
        op="add_node",
        interpreter=(
            "mint uid, bind `var`, reject `vibecomfy.*` intent classes "
            "(those use `intent_node_properties()`); emit one `upsert_link` per wired input"
        ),
        ast_types=(ast.Assign, ast.Name, ast.Call, ast.keyword, ast.Attribute, ast.Constant),
    ),
    StatementForm(
        form_id="upsert_link",
        surface="`dst.field = src.SLOT` (or bare `src` if unambiguous)",
        op="upsert_link",
        interpreter="resolve slot name→index, type-check (`socket_types_compatible`)",
        ast_types=(ast.Assign, ast.Attribute, ast.Name),
        assignment_shape="graph_ref",
    ),
    StatementForm(
        form_id="remove_link",
        surface="`dst.field = None`",
        op="remove_link",
        interpreter="disconnect the named input",
        ast_types=(ast.Assign, ast.Attribute, ast.Name, ast.Constant),
        assignment_shape="none",
    ),
    StatementForm(
        form_id="remove_node",
        surface="`del node`",
        op="remove_node",
        interpreter="refuse substrate virtuals (§6)",
        ast_types=(ast.Delete, ast.Name),
    ),
    StatementForm(
        form_id="set_mode",
        surface='`node.mode = "bypassed"|"enabled"|"muted"`',
        op="set_mode",
        interpreter="assign the semantic mode",
        ast_types=(ast.Assign, ast.Attribute, ast.Name, ast.Constant),
        assignment_shape="mode",
    ),
    StatementForm(
        form_id="for_macro",
        surface="`for n in <list>: n.field = value`",
        op="macro",
        interpreter=(
            "parse-time expansion to one assignment per element (hard cap ~50); "
            "`range(...)` is the constant-iterator form of the same macro"
        ),
        ast_types=(ast.For, ast.Name, ast.List, ast.Tuple, ast.Call, ast.Constant),
    ),
    StatementForm(
        form_id="query",
        surface="`search(...)`, `python()`, and the named agent tool calls",
        op=None,
        interpreter="side-effect-free catalog / research; no graph op",
        ast_types=(ast.Expr, ast.Call, ast.Name, ast.keyword, ast.Constant),
        in_doc_table=False,
    ),
    StatementForm(
        form_id="done",
        surface="`done()`",
        op=None,
        interpreter="control: commit the session",
        ast_types=(ast.Expr, ast.Call, ast.Name),
        in_doc_table=False,
    ),
    StatementForm(
        form_id="subgraph_interface",
        surface="`subgraph_interface(name=..., inputs=..., outputs=...)`",
        op="subgraph_interface",
        interpreter="reconstruct subgraph signatures onto metadata['definitions']",
        ast_types=(ast.Expr, ast.Call, ast.Name, ast.keyword, ast.Constant, ast.Tuple),
        in_doc_table=False,
        in_prompt=False,
    ),
    StatementForm(
        form_id="refuse",
        surface="`refuse(kind=…, missing_classes=…, evidence=…, message=…)`",
        op=None,
        interpreter="control: finish with a model-selected typed refusal; authority validates evidence",
        ast_types=(ast.Expr, ast.Call, ast.Name, ast.keyword, ast.Constant, ast.List, ast.Tuple, ast.Dict),
        in_doc_table=False,
    ),
)


FORBIDDEN_FORMS: tuple[ForbiddenForm, ...] = (
    ForbiddenForm(
        form_id="import",
        surface="`import` / `from … import`",
        code="import_not_allowed",
        reason="imports cross into runtime evaluation",
        ast_types=(ast.Import, ast.ImportFrom),
    ),
    ForbiddenForm(
        form_id="def",
        surface="`def` / `class` / `async def`",
        code="statement_not_allowed",
        reason="user-defined functions and classes cross into runtime evaluation",
        ast_types=(ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
    ),
    ForbiddenForm(
        form_id="conditional",
        surface="`if` / `if` expressions",
        code="conditional_not_allowed",
        reason="conditionals cross into runtime evaluation",
        ast_types=(ast.If, ast.IfExp),
    ),
    ForbiddenForm(
        form_id="comprehension",
        surface="list/set/dict/generator comprehensions",
        code="comprehension_not_allowed",
        reason="comprehensions cross into runtime evaluation",
        ast_types=(ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp),
    ),
    ForbiddenForm(
        form_id="lambda",
        surface="`lambda`",
        code="lambda_not_allowed",
        reason="lambdas cross into runtime evaluation",
        ast_types=(ast.Lambda,),
    ),
    ForbiddenForm(
        form_id="f_string",
        surface="f-string interpolation",
        code="f_string_not_allowed",
        reason="f-strings interpolate at runtime",
        ast_types=(ast.JoinedStr, ast.FormattedValue),
    ),
    ForbiddenForm(
        form_id="reorder",
        surface="`reorder(...)`",
        code="call_not_allowed",
        reason="reorder is not part of the designed grammar",
        call_names=("reorder",),
    ),
    ForbiddenForm(
        form_id="set_title",
        surface="`node.title = …` / `set_title(...)`",
        code="set_title_not_allowed",
        reason="set_title is not part of the designed grammar",
        call_names=("set_title",),
        assign_attrs=("title",),
    ),
    ForbiddenForm(
        form_id="arithmetic_over_names",
        surface="arithmetic over graph names (e.g. `a.steps + b.steps`)",
        code="expression_not_constant",
        reason="only const-folded literals are allowed; names are not operands",
    ),
)


# ---------------------------------------------------------------------------
# Derived admission sets (generated from STATEMENT_FORMS — no hand list)
# ---------------------------------------------------------------------------

# The documented/prompt set is the union of every form's declared AST types,
# in declaration order (first occurrence wins), plus the parse root
# ``ast.Module`` — a structural constant of ``ast.parse``, not a statement form.
def _documented_ast_types_in_order() -> tuple[type[ast.AST], ...]:
    seen: list[type[ast.AST]] = []
    for form in STATEMENT_FORMS:
        for typ in form.ast_types:
            if typ not in seen:
                seen.append(typ)
    return (ast.Module, *seen)


# Context nodes (Load/Store/Del) and operator nodes (Add, USub, …) are
# implementation companions of the documented types — they appear in every
# parsed tree and are admitted, but they are not a second vocabulary.
_LITERAL_COMPANION_AST_TYPES: tuple[type[ast.AST], ...] = (
    ast.UnaryOp,
    ast.Set,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.UAdd,
    ast.USub,
    ast.Load,
    ast.Store,
    ast.Del,
)

DOCUMENTED_AST_TYPES: frozenset[type[ast.AST]] = frozenset(
    _documented_ast_types_in_order()
)

ADMITTED_AST_TYPES: frozenset[type[ast.AST]] = frozenset(
    {*DOCUMENTED_AST_TYPES, *_LITERAL_COMPANION_AST_TYPES}
)

FORBIDDEN_AST_CODES: dict[type[ast.AST], str] = {}
for _form in FORBIDDEN_FORMS:
    for _typ in _form.ast_types:
        FORBIDDEN_AST_CODES.setdefault(_typ, _form.code)

UNSAFE_CALL_NAMES: frozenset[str] = frozenset(
    {
        "__import__",
        "compile",
        "eval",
        "exec",
        "globals",
        "locals",
        "open",
    }
)

FORBIDDEN_CALL_NAMES: frozenset[str] = frozenset(
    {
        *UNSAFE_CALL_NAMES,
        *(name for form in FORBIDDEN_FORMS for name in form.call_names),
    }
)

FORBIDDEN_ASSIGN_ATTRS: dict[str, str] = {
    attr: form.code
    for form in FORBIDDEN_FORMS
    for attr in form.assign_attrs
}

QUERY_CALL_NAMES: frozenset[str] = frozenset({"python", "research", "search"}) | frozenset(
    AGENT_TOOL_CALL_NAMES
)
CONTROL_CALL_NAMES: frozenset[str] = frozenset({"done", "refuse"})
ALLOWED_VIBECOMFY_CONSTRUCTION_CLASS_TYPES: frozenset[str] = frozenset({"vibecomfy.exec"})

AUTHORING_DOC_RELPATH = "docs/architecture/python_authoring_edit_surface.md"
DOC_TABLE_BEGIN = "<!-- grammar-doc-table:begin -->"
DOC_TABLE_END = "<!-- grammar-doc-table:end -->"
DOC_AST_BEGIN = "<!-- grammar-ast-allow-list:begin -->"
DOC_AST_END = "<!-- grammar-ast-allow-list:end -->"


def documented_ast_type_names() -> tuple[str, ...]:
    """Stable names for the architecture-doc allow-list (generated order)."""
    return tuple(typ.__name__ for typ in _documented_ast_types_in_order())


def admitted_ast_type_names() -> tuple[str, ...]:
    return tuple(sorted(typ.__name__ for typ in ADMITTED_AST_TYPES))


# ---------------------------------------------------------------------------
# Statement-shape → op-kind mapping (generated; the parser consumes it)
# ---------------------------------------------------------------------------

# Assignment forms discriminate on the RHS shape, declared per form above.
# Order by specificity so `node.mode = …` wins over the literal fallback.
_ASSIGNMENT_SHAPE_ORDER = {"mode": 0, "none": 1, "graph_ref": 2, "literal": 3}

_ASSIGNMENT_SHAPE_OPS: tuple[tuple[str, str], ...] = tuple(
    sorted(
        (
            (form.assignment_shape, form.op)
            for form in STATEMENT_FORMS
            if form.assignment_shape is not None and form.op is not None
        ),
        key=lambda item: _ASSIGNMENT_SHAPE_ORDER[item[0]],
    )
)


def op_kind_for_statement(statement: ast.stmt) -> str | None:
    """Map a validated statement shape to its surface op kind.

    This is the single statement-shape list for the whole surface: the parser
    (``_parse.py``) and the resolver (``_resolve.py``) consume it and never
    hand-maintain a second copy.  Shapes mirror ``STATEMENT_FORMS``.
    """
    if isinstance(statement, ast.Assign):
        target = statement.targets[0]
        if isinstance(target, ast.Name) and isinstance(statement.value, ast.Call):
            return "node_call"
        if isinstance(target, ast.Attribute):
            return op_kind_for_assignment(statement.value, target_attr=target.attr)
        return "assign"
    if isinstance(statement, ast.Delete):
        return "remove_node"
    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
        call = statement.value
        if isinstance(call.func, ast.Name) and call.func.id == "subgraph_interface":
            return "subgraph_interface"
        if isinstance(call.func, ast.Name) and call.func.id in CONTROL_CALL_NAMES:
            return call.func.id
        return "query"
    return None


def op_kind_for_assignment(value: ast.expr, *, target_attr: str) -> str:
    """Classify an attribute assignment by its target attr and RHS shape.

    Driven by the per-form ``assignment_shape`` declarations — the op names
    come from ``STATEMENT_FORMS``, never from a hand-written second list.
    """
    forbidden = FORBIDDEN_ASSIGN_ATTRS.get(target_attr)
    if forbidden is not None:
        return forbidden
    for shape, op in _ASSIGNMENT_SHAPE_OPS:
        if shape == "mode":
            if target_attr == "mode":
                return op
        elif shape == "none":
            if isinstance(value, ast.Constant) and value.value is None:
                return op
        elif shape == "graph_ref":
            if isinstance(value, (ast.Name, ast.Attribute)):
                return op
        elif shape == "literal":
            return op
    return "set_node_field"


def form_by_id(form_id: str) -> StatementForm:
    for form in STATEMENT_FORMS:
        if form.form_id == form_id:
            return form
    raise KeyError(form_id)


def forbidden_form_by_id(form_id: str) -> ForbiddenForm:
    for form in FORBIDDEN_FORMS:
        if form.form_id == form_id:
            return form
    raise KeyError(form_id)


def diagnose_unadmitted_ast(tree: ast.AST) -> list[tuple[ast.AST, str, str]]:
    """Walk *tree* and report outermost node types the grammar does not admit."""
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
    issues: list[tuple[ast.AST, str, str]] = []
    for node in ast.walk(tree):
        if type(node) in ADMITTED_AST_TYPES:
            continue
        ancestor = parents.get(id(node))
        nested = False
        while ancestor is not None:
            if type(ancestor) not in ADMITTED_AST_TYPES:
                nested = True
                break
            ancestor = parents.get(id(ancestor))
        if nested:
            continue
        code = FORBIDDEN_AST_CODES.get(type(node), "ast_type_not_allowed")
        typename = type(node).__name__
        if code == "statement_not_allowed":
            message = f"{typename} statements are not allowed."
        elif code == "conditional_not_allowed":
            message = "Conditionals are not allowed."
        elif code == "comprehension_not_allowed":
            message = "Comprehensions are not allowed."
        elif code == "import_not_allowed":
            message = "Imports are not allowed in edit batches."
        elif code == "lambda_not_allowed":
            message = "Lambdas are not allowed."
        elif code == "f_string_not_allowed":
            message = "f-string interpolation is not allowed."
        else:
            message = f"{typename} is not an allowed edit-surface construct."
        issues.append((node, code, message))
    return issues


# ---------------------------------------------------------------------------
# Generated documentation
# ---------------------------------------------------------------------------


def render_doc_table() -> str:
    """Markdown table for python_authoring_edit_surface.md §3."""
    lines = [
        "| Surface (what the agent writes) | Internal op | Interpreter does |",
        "|---|---|---|",
    ]
    for form in STATEMENT_FORMS:
        if not form.in_doc_table:
            continue
        op = f"`{form.op}`" if form.op else ""
        lines.append(f"| {form.surface} | {op} | {form.interpreter} |")
    return "\n".join(lines)


def render_ast_allow_list() -> str:
    """The documented AST set, as it appears in the architecture note."""
    names = ", ".join(
        "For(bounded)" if name == "For" else "BinOp(const)" if name == "BinOp" else name
        for name in documented_ast_type_names()
    )
    return "{" + names + "}"


def render_prompt_doc() -> str:
    """Agent-facing documentation generated from the same forms as the parser."""
    lines = [
        "Edit surface grammar (generated; do not invent verbs).",
        "Write the same Python the view emits. Statements are AST-parsed, never executed.",
        "",
        "Supported:",
    ]
    for form in STATEMENT_FORMS:
        if not form.in_prompt:
            continue
        op = f" → {form.op}" if form.op else ""
        lines.append(f"- {form.surface}{op}")
        lines.append(f"  {form.interpreter}")
    lines.append("")
    lines.append("Forbidden (not in the grammar):")
    for form in FORBIDDEN_FORMS:
        lines.append(f"- {form.surface}  [{form.code}] — {form.reason}")
    lines.append("")
    lines.append(f"AST allow-list: {render_ast_allow_list()}")
    lines.append(
        "Batches are capped (~50 statements / ~64 KiB). "
        "Bounded `for` is a parse-time macro (cap ~50)."
    )
    return "\n".join(lines) + "\n"


def authoring_doc_path(*, repo_root: Path | None = None) -> Path:
    root = repo_root if repo_root is not None else Path(__file__).resolve().parents[3]
    return root / AUTHORING_DOC_RELPATH


def _replace_marked_region(text: str, begin: str, end: str, body: str) -> str:
    start = text.find(begin)
    stop = text.find(end)
    if start < 0 or stop < 0 or stop < start:
        raise ValueError(f"missing grammar markers {begin!r} … {end!r}")
    return text[: start + len(begin)] + "\n" + body + "\n" + text[stop:]


def render_authoring_doc(text: str) -> str:
    """Fill the marked §3 table and AST allow-list regions of the architecture note."""
    updated = _replace_marked_region(text, DOC_TABLE_BEGIN, DOC_TABLE_END, render_doc_table())
    return _replace_marked_region(updated, DOC_AST_BEGIN, DOC_AST_END, render_ast_allow_list())


def sync_authoring_doc(*, repo_root: Path | None = None) -> Path:
    path = authoring_doc_path(repo_root=repo_root)
    path.write_text(render_authoring_doc(path.read_text(encoding="utf-8")), encoding="utf-8")
    return path


def authoring_doc_agrees(text: str) -> bool:
    """True when the architecture note's marked regions match this grammar."""
    try:
        return render_authoring_doc(text) == text
    except ValueError:
        return False


def prompt_doc_covers_grammar(doc: str | None = None) -> list[str]:
    """Return missing form/forbidden fragments; empty means the prompt matches."""
    text = render_prompt_doc() if doc is None else doc
    missing: list[str] = []
    for form in STATEMENT_FORMS:
        if form.in_prompt and form.surface not in text:
            missing.append(form.form_id)
    for form in FORBIDDEN_FORMS:
        if form.form_id not in text and form.surface not in text:
            missing.append(form.form_id)
    if render_ast_allow_list() not in text:
        missing.append("ast_allow_list")
    return missing


def iter_statement_forms() -> Iterable[StatementForm]:
    return STATEMENT_FORMS


def iter_forbidden_forms() -> Iterable[ForbiddenForm]:
    return FORBIDDEN_FORMS


__all__ = [
    "ADMITTED_AST_TYPES",
    "ALLOWED_VIBECOMFY_CONSTRUCTION_CLASS_TYPES",
    "AUTHORING_DOC_RELPATH",
    "CONTROL_CALL_NAMES",
    "DOCUMENTED_AST_TYPES",
    "DOC_AST_BEGIN",
    "DOC_AST_END",
    "DOC_TABLE_BEGIN",
    "DOC_TABLE_END",
    "FORBIDDEN_ASSIGN_ATTRS",
    "FORBIDDEN_AST_CODES",
    "FORBIDDEN_CALL_NAMES",
    "FORBIDDEN_FORMS",
    "ForbiddenForm",
    "QUERY_CALL_NAMES",
    "STATEMENT_FORMS",
    "StatementForm",
    "UNSAFE_CALL_NAMES",
    "admitted_ast_type_names",
    "authoring_doc_agrees",
    "authoring_doc_path",
    "diagnose_unadmitted_ast",
    "documented_ast_type_names",
    "forbidden_form_by_id",
    "form_by_id",
    "iter_forbidden_forms",
    "iter_statement_forms",
    "op_kind_for_assignment",
    "op_kind_for_statement",
    "prompt_doc_covers_grammar",
    "render_ast_allow_list",
    "render_authoring_doc",
    "render_doc_table",
    "render_prompt_doc",
    "sync_authoring_doc",
]
