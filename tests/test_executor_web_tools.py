"""A06 tests for the explicit last-resort ``web_search`` agent tool.

Locks the A06 contracts:

* ``web_search`` is DISABLED by default; disabled calls return a visible typed
  policy rejection (``refused``) — never a silent omission.
* No automatic Hivemind-to-web fallback exists in the tool (source-level).
* Enabled calls are fully typed: ``ok`` / ``no_results`` / ``rate_limited`` /
  ``timeout`` / ``unavailable`` / ``invalid_request``, record evidence ids,
  and the tool trace records the agent's stated unresolved question.

No HTTP: every test injects a fake transport.
"""

from __future__ import annotations

import inspect

import pytest

from vibecomfy.executor.evidence_pack import EvidenceLedger, EvidenceLedgerEntry, EvidencePack
from vibecomfy.executor.tool_contracts import ToolResult, ToolStatus
from vibecomfy.executor.web_tools import (
    TOOL_NAME,
    WebSearchRateLimitError,
    WebSearchTimeoutError,
    WebSearchTool,
    WebSearchTraceEntry,
    _DEFAULT_WEB_RESULT_LIMIT,
    web_search,
)


def _fake_transport(*, results=None, error=None, calls=None):
    def transport(query: str, timeout: float):
        if calls is not None:
            calls.append((query, timeout))
        if error is not None:
            raise error
        return {"results": results or []}

    return transport


# ── Disabled by default: visible typed policy rejection ─────────────────────


def test_disabled_by_default_returns_visible_policy_rejection() -> None:
    result = web_search("wan video workflow best practices")
    assert result.tool_name == TOOL_NAME
    assert result.status is ToolStatus.REFUSED
    assert result.diagnostics
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "web_search_disabled"
    assert "disabled by policy" in diagnostic.message
    # Not a silent omission: the call is recorded in the result payload.
    assert result.result["query"] == "wan video workflow best practices"
    assert result.result["trace"]["status"] == "refused"


def test_function_form_disabled_never_touches_transport() -> None:
    calls: list = []
    result = web_search("wan", transport=_fake_transport(calls=calls))
    assert result.status is ToolStatus.REFUSED
    assert calls == []


def test_tool_instance_disabled_by_default_and_traces_refusal() -> None:
    tool = WebSearchTool()
    result = tool.web_search("wan", unresolved_question="Which Wan checkpoint is current?")
    assert result.status is ToolStatus.REFUSED
    assert len(tool.trace) == 1
    record = tool.trace[0]
    assert record["query"] == "wan"
    assert record["status"] == "refused"
    assert record["unresolved_question"] == "Which Wan checkpoint is current?"
    assert record["diagnostic_codes"] == ["web_search_disabled"]


def test_refusal_trace_records_stated_unresolved_question() -> None:
    result = web_search("ltx video", unresolved_question="Does LTX support i2v?")
    trace = result.result["trace"]
    assert trace["unresolved_question"] == "Does LTX support i2v?"
    assert trace["status"] == "refused"


# ── No automatic Hivemind-to-web fallback ───────────────────────────────────


def test_no_automatic_hivemind_to_web_fallback() -> None:
    import vibecomfy.executor.web_tools as web_tools_module

    source = inspect.getsource(web_tools_module)
    # The tool cannot be auto-triggered by a failed Hivemind search: it never
    # imports or calls Hivemind/research machinery.
    assert "hivemind_clients" not in source
    assert "from .research" not in source
    assert "import research" not in source
    # The call path itself contains no Hivemind reference or fallback wiring.
    call_source = inspect.getsource(WebSearchTool.web_search)
    assert "hivemind" not in call_source.casefold()
    assert "fallback" not in call_source.casefold()


# ── Enabled: typed invalid-request gates ────────────────────────────────────


def test_blank_query_is_invalid_request_without_calling_transport() -> None:
    calls: list = []
    tool = WebSearchTool(enabled=True, transport=_fake_transport(calls=calls))
    result = tool.web_search("   ")
    assert result.status is ToolStatus.INVALID_REQUEST
    assert result.diagnostics[0].code == "web_search_invalid_query"
    assert calls == []


def test_non_string_query_is_invalid_request() -> None:
    result = web_search(123, enabled=True)
    assert result.status is ToolStatus.INVALID_REQUEST
    assert result.diagnostics[0].code == "web_search_invalid_query"


def test_enabled_call_requires_stated_unresolved_question() -> None:
    calls: list = []
    tool = WebSearchTool(enabled=True, transport=_fake_transport(calls=calls))
    result = tool.web_search("wan checkpoint")
    assert result.status is ToolStatus.INVALID_REQUEST
    assert result.diagnostics[0].code == "web_search_unresolved_question_required"
    assert calls == []


def test_whitespace_only_unresolved_question_is_invalid_request() -> None:
    tool = WebSearchTool(enabled=True, transport=_fake_transport())
    result = tool.web_search("wan checkpoint", unresolved_question="   ")
    assert result.status is ToolStatus.INVALID_REQUEST
    assert result.diagnostics[0].code == "web_search_unresolved_question_required"


# ── Enabled: typed transport outcomes ───────────────────────────────────────


def test_enabled_success_is_typed_ok_with_evidence() -> None:
    results = [
        {"title": "Wan 2.2 announcement", "url": "https://example.com/wan", "snippet": "…"},
        {"title": "LTX video guide", "url": "https://example.com/ltx", "snippet": "…"},
    ]
    calls: list = []
    tool = WebSearchTool(enabled=True, transport=_fake_transport(results=results, calls=calls))
    result = tool.web_search("wan ltx", unresolved_question="Which model to use?")
    assert result.status is ToolStatus.OK
    assert calls == [("wan ltx", 5.0)]
    assert result.result["count"] == 2
    assert [item["title"] for item in result.result["results"]] == [
        "Wan 2.2 announcement",
        "LTX video guide",
    ]
    assert len(result.evidence_ids) == 2
    assert set(result.evidence_ids) == set(tool.artifacts)
    assert tool.evidence_ids == result.evidence_ids
    for evidence_id in result.evidence_ids:
        artifact = tool.artifacts[evidence_id]
        assert artifact.kind == "web_search_result"
        assert artifact.source == "web"
        assert artifact.body["url"].startswith("https://")
    trace = result.result["trace"]
    assert trace["status"] == "ok"
    assert trace["unresolved_question"] == "Which model to use?"
    assert trace["evidence_ids"] == result.evidence_ids


def test_evidence_ids_are_stable_and_ranked_per_query() -> None:
    results = [
        {"title": "A", "url": "https://example.com/a"},
        {"title": "B", "url": "https://example.com/b"},
    ]
    first = WebSearchTool(enabled=True, transport=_fake_transport(results=results)).web_search(
        "Wan 2.2", unresolved_question="q?"
    )
    second = WebSearchTool(enabled=True, transport=_fake_transport(results=results)).web_search(
        "wan 2.2", unresolved_question="q?"
    )
    assert first.evidence_ids[0] == second.evidence_ids[0]
    assert first.evidence_ids[1] == second.evidence_ids[1]
    assert first.evidence_ids[0] != first.evidence_ids[1]


def test_evidence_ids_resolve_inside_evidence_pack() -> None:
    tool = WebSearchTool(
        enabled=True,
        transport=_fake_transport(results=[{"title": "T", "url": "https://example.com/1", "snippet": "S"}]),
    )
    result = tool.web_search("wan", unresolved_question="q?")
    evidence_id = result.evidence_ids[0]
    pack = EvidencePack(
        artifacts=dict(tool.artifacts),
        ledger=EvidenceLedger(
            entries=(
                EvidenceLedgerEntry(
                    decision="Use web evidence.",
                    conclusion="A web result was retrieved.",
                    evidence_ids=(evidence_id,),
                    uncertainty="Low.",
                ),
            )
        ),
    )
    assert pack.artifacts[evidence_id].body["title"] == "T"
    # Wire round-trip keeps the ledger resolvable against the artifacts.
    rebuilt = EvidencePack.from_dict(pack.to_dict())
    rebuilt.ledger.validate_references(set(rebuilt.artifacts))


def test_timeout_is_typed_timeout_with_diagnostic() -> None:
    tool = WebSearchTool(
        enabled=True,
        transport=_fake_transport(error=WebSearchTimeoutError("boom")),
    )
    result = tool.web_search("wan", unresolved_question="q?")
    assert result.status is ToolStatus.TIMEOUT
    assert result.diagnostics[0].code == "web_search_timeout"
    assert result.result["trace"]["status"] == "timeout"
    assert result.result["trace"]["unresolved_question"] == "q?"


def test_raw_timeout_error_is_typed_timeout() -> None:
    tool = WebSearchTool(enabled=True, transport=_fake_transport(error=TimeoutError("took too long")))
    result = tool.web_search("wan", unresolved_question="q?")
    assert result.status is ToolStatus.TIMEOUT
    assert result.diagnostics[0].code == "web_search_timeout"


def test_rate_limited_is_typed_with_retry_after() -> None:
    tool = WebSearchTool(
        enabled=True,
        transport=_fake_transport(error=WebSearchRateLimitError(retry_after_seconds=12.5)),
    )
    result = tool.web_search("wan", unresolved_question="q?")
    assert result.status is ToolStatus.RATE_LIMITED
    assert result.retry_after_seconds == 12.5
    assert result.diagnostics[0].code == "web_search_rate_limited"
    assert result.result["trace"]["status"] == "rate_limited"
    assert result.result["trace"]["retry_after_seconds"] == 12.5
    assert result.result["trace"]["unresolved_question"] == "q?"


def test_rate_limited_without_retry_after_is_null() -> None:
    tool = WebSearchTool(enabled=True, transport=_fake_transport(error=WebSearchRateLimitError()))
    result = tool.web_search("wan", unresolved_question="q?")
    assert result.status is ToolStatus.RATE_LIMITED
    assert result.retry_after_seconds is None
    assert "retry_after_seconds" not in result.result["trace"]


def test_no_results_is_typed_no_results() -> None:
    tool = WebSearchTool(enabled=True, transport=_fake_transport(results=[]))
    result = tool.web_search("wan", unresolved_question="q?")
    assert result.status is ToolStatus.NO_RESULTS
    assert result.diagnostics[0].code == "web_search_no_results"
    assert result.evidence_ids == ()


def test_non_mapping_transport_response_is_no_results() -> None:
    def transport(query: str, timeout: float):
        return None

    tool = WebSearchTool(enabled=True, transport=transport)
    result = tool.web_search("wan", unresolved_question="q?")
    assert result.status is ToolStatus.NO_RESULTS


def test_transport_failure_is_typed_unavailable() -> None:
    tool = WebSearchTool(enabled=True, transport=_fake_transport(error=RuntimeError("dns broke")))
    result = tool.web_search("wan", unresolved_question="q?")
    assert result.status is ToolStatus.UNAVAILABLE
    assert result.diagnostics[0].code == "web_search_unavailable"


def test_results_are_capped_at_default_limit() -> None:
    many = [
        {"title": f"Result {i}", "url": f"https://example.com/{i}"}
        for i in range(30)
    ]
    tool = WebSearchTool(enabled=True, transport=_fake_transport(results=many))
    result = tool.web_search("wan", unresolved_question="q?")
    assert result.status is ToolStatus.OK
    assert result.result["count"] == _DEFAULT_WEB_RESULT_LIMIT
    assert len(result.evidence_ids) == _DEFAULT_WEB_RESULT_LIMIT
    assert len(tool.artifacts) == _DEFAULT_WEB_RESULT_LIMIT


# ── Trace accumulation and wire forms ───────────────────────────────────────


def test_trace_accumulates_across_calls_in_order() -> None:
    tool = WebSearchTool(
        enabled=True,
        transport=_fake_transport(results=[{"title": "T", "url": "https://e.com/1"}]),
    )
    tool.web_search("first", unresolved_question="q1?")
    tool.web_search("second", unresolved_question="q2?")
    assert [record["query"] for record in tool.trace] == ["first", "second"]
    assert [record["unresolved_question"] for record in tool.trace] == ["q1?", "q2?"]
    assert [record["status"] for record in tool.trace] == ["ok", "ok"]


def test_tool_result_roundtrips_through_wire_form() -> None:
    tool = WebSearchTool(
        enabled=True,
        transport=_fake_transport(results=[{"title": "T", "url": "https://e.com/1", "snippet": "S"}]),
    )
    result = tool.web_search("wan", unresolved_question="q?")
    rebuilt = ToolResult.from_dict(result.to_dict())
    assert rebuilt.to_dict() == result.to_dict()
    assert rebuilt.status is ToolStatus.OK
    assert rebuilt.evidence_ids == result.evidence_ids


def test_trace_entry_roundtrips_through_wire_form() -> None:
    entry = WebSearchTraceEntry(
        query="wan",
        status=ToolStatus.REFUSED,
        unresolved_question="q?",
        diagnostic_codes=("web_search_disabled",),
    )
    rebuilt = WebSearchTraceEntry.from_dict(entry.to_dict())
    assert rebuilt == entry


def test_tool_constructor_validates_config() -> None:
    with pytest.raises(ValueError):
        WebSearchTool(enabled=True, timeout=0)
    with pytest.raises(ValueError):
        WebSearchTool(enabled=True, timeout=-1.0)
    with pytest.raises(ValueError):
        WebSearchTool(enabled="yes")
