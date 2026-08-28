"""S4 fence extract — Adherence Made Easy.

Tests for grok-strategy-final-wave S4:
- python/yaml fence extraction (506ebd yaml, 1cc457 python)
- search(...) in python/yaml treated as batch ops
- empty-think → infra retry (not product fail)
- typed requires_custom_nodes from prose
"""
import pytest

from vibecomfy.comfy_nodes.agent.provider import extract_batch_fence, MalformedModelJSON
from vibecomfy.comfy_nodes.agent.provider import _typed_empty_attempt, _batch_failure_type
from tests.live_agentic_harness.runner import _provider_infra_failure_class
from vibecomfy.executor.contracts import ModelAttemptEvidence


def test_python_search_treated_as_batch():
    """1cc457: search(...) in ```python fences should be batch ops."""
    text = (
        'I will research.\n\n'
        '```python\n'
        'search(focus_types=["SVD_img2vid_Conditioning"])\n'
        'search(focus_types=["VideoLinearCFGGuidance"])\n'
        '```\n\n'
        'more prose'
    )
    batch, prose = extract_batch_fence(text)
    assert 'search(focus_types' in batch
    assert batch.count('search(') == 2
    assert 'more prose' in prose


def test_yaml_widget_assignment_treated_as_batch():
    """506ebd: yaml fence with widget assignment should be batch op."""
    text = (
        "analysis\n\n"
        "```yaml\n"
        "controlnetloaderadvanced.widget_0='control_v11p_sd15_openpose.pth'\n"
        "```\n\n"
        "done"
    )
    batch, prose = extract_batch_fence(text)
    assert "controlnetloaderadvanced.widget_0" in batch
    assert "analysis" in prose or "done" in prose


def test_multiple_python_search_fences_merge():
    """Multiple python search fences merge in order."""
    text = (
        '```python\nsearch(focus_types=["A"])\n```\n'
        'mid\n'
        '```python\nsearch(focus_types=["B"])\n```\n'
    )
    batch, prose = extract_batch_fence(text)
    assert 'search(focus_types=["A"])' in batch
    assert 'search(focus_types=["B"])' in batch
    assert batch.index('A') < batch.index('B')
    assert 'mid' in prose


def test_yaml_without_batch_like_still_fails():
    """Non-batch yaml (key: value) should still fail closed."""
    text = "here\n```yaml\nkey: value\n```\nmore"
    with pytest.raises(MalformedModelJSON) as exc:
        extract_batch_fence(text)
    assert exc.value.parse_reason == "missing_batch_fence"


def test_empty_think_raises_empty_not_missing():
    """b11a56: empty-think (only <think> block) → parse_reason empty for infra retry."""
    text = "<think>Reasoning: The user wants to modify the workflow...</think>"
    with pytest.raises(MalformedModelJSON) as exc:
        extract_batch_fence(text)
    assert exc.value.parse_reason == "empty"
    # failure type should be empty_response → infra
    assert _batch_failure_type(exc.value) == "empty_response"


def test_empty_think_with_trailing_whitespace():
    text = "<think>thinking</think>   \n\n  "
    with pytest.raises(MalformedModelJSON) as exc:
        extract_batch_fence(text)
    assert exc.value.parse_reason == "empty"


def test_typed_requires_custom_nodes_from_prose():
    """359848: typed requires_custom_nodes in prose should not error."""
    text = "Diagnosis: requires_custom_nodes AnimateDiff is missing, cannot edit.\nNo batch fence here but typed signal."
    batch, prose = extract_batch_fence(text)
    assert batch == ""
    assert "requires_custom_nodes" in prose.lower()


def test_requires_custom_nodes_prose_case_insensitive():
    text = "REQUIRES_CUSTOM_NODES: need custom pack"
    batch, prose = extract_batch_fence(text)
    assert batch == ""


def test_normal_batch_still_works():
    text = '```batch\nadd_node("Foo")\n```'
    batch, prose = extract_batch_fence(text)
    assert batch == 'add_node("Foo")'


def test_empty_think_infra_classification():
    """Harness: empty-think with completion_tokens >0 still infra_empty_response."""
    summary = {
        "model_attempts": [
            {
                "attempt": 1,
                "outcome": "failure",
                "failure_type": "empty_response",
                "parse_reason": "empty",
                "raw_response_preview": "<think>hello</think>",
                "token_usage": {"completion_tokens": 123, "prompt_tokens": 10, "total_tokens": 133},
            }
        ],
        "guard": {"live_agentic_success": False},
    }
    attempt = ModelAttemptEvidence.from_mapping(summary["model_attempts"][0]).to_dict()
    summary["model_attempts"][0] = attempt
    summary["model_attempts"][0]["raw_response_preview"] = "<think>hello</think>"
    summary["model_attempts"][0]["failure_type"] = "empty_response"
    summary["model_attempts"][0]["parse_reason"] = "empty"
    assert _provider_infra_failure_class(summary) == "infra_empty_response"


def test_typed_empty_attempt_think_retry():
    attempts = (
        {
            "failure_type": "empty_response",
            "token_usage": {"completion_tokens": 50},
            "raw_response_preview": "<think>reasoning</think>",
            "parse_reason": "empty",
        },
    )
    assert _typed_empty_attempt(attempts) is True


def test_batch_empty_with_zero_tokens_retry():
    attempts = (
        {
            "failure_type": "empty_response",
            "token_usage": {"completion_tokens": 0},
            "raw_response_preview": "",
        },
    )
    assert _typed_empty_attempt(attempts) is True
