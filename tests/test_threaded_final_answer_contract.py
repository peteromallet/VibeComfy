"""Explicit final-answer custody for threaded no-delta conversations."""

from __future__ import annotations

from typing import Any

import pytest

from tests.test_comfy_nodes_agent_edit import _make_state
from vibecomfy.comfy_nodes.agent import provider as agent_provider
from vibecomfy.comfy_nodes.agent._frag_response_contract import (
    _build_batch_repl_response,
)
from vibecomfy.comfy_nodes.agent._frag_state import TurnContext
from vibecomfy.executor.contracts import (
    ExecutorHostPorts,
    ExecutorRequest,
    ImplementationResult,
)
from vibecomfy.executor.profiles import AgentSpecShape
from vibecomfy.executor.threaded import ThreadedKernel, run_threaded_executor
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec


ANSWER = (
    "The SVD conditioning path uses the image encoder before the sampler; "
    "evidence item workflow:svd confirms that connection."
)
EVIDENCE_REFS = ("workflow:svd", "hivemind_get:svd-guidance")


class TestExplicitThreadedFinalAnswer:
    def test_answer_only_prompt_requires_explicit_terminal_payload(self) -> None:
        messages = agent_provider.build_batch_messages(
            task="Explain this graph",
            python_source="# graph",
            tool_phase="threaded",
            interaction_mode="answer_only",
        )

        system = messages[0]["content"]
        assert "Interaction contract: answer_only" in system
        assert 'done(final_answer="...", evidence_refs=["..."])' in system
        assert "cite only exact ledger IDs" in system

    def test_provider_extracts_terminal_payload_and_leaves_canonical_done(self) -> None:
        result = agent_provider._normalize_batch_response(
            {
                "batch": (
                    "done(final_answer="
                    + repr(ANSWER)
                    + ", evidence_refs="
                    + repr(list(EVIDENCE_REFS))
                    + ")"
                ),
                "message": "Generic completion prose must not become the answer.",
            },
            route="test",
            model="offline",
        )

        assert result.batch == "done()"
        assert result.final_answer == ANSWER
        assert result.evidence_refs == EVIDENCE_REFS
        assert result.to_dict()["final_answer"] == {
            "text": ANSWER,
            "evidence_refs": list(EVIDENCE_REFS),
        }

    def test_durable_noop_response_publishes_explicit_answer_without_narrator(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "vibecomfy.comfy_nodes.agent.edit._narrate_final_message",
            lambda *args, **kwargs: pytest.fail(
                "an explicit terminal answer must not be replaced by narration"
            ),
        )
        state = _make_state(
            route="adapt",
            ui_payload=None,
            batch_exit_mode="noop",
            batch_done_summary="No graph changes.",
            batch_final_answer=ANSWER,
            batch_final_answer_evidence_refs=EVIDENCE_REFS,
        )

        response = _build_batch_repl_response(
            state,
            TurnContext(session_id="threaded-answer", turn_id="0001"),
        )

        assert response["ok"] is True
        assert response["outcome"]["kind"] == "noop"
        assert response["message"] == ANSWER
        assert response["final_answer"] == {
            "text": ANSWER,
            "evidence_refs": list(EVIDENCE_REFS),
        }
        assert response["evidence_refs"] == list(EVIDENCE_REFS)

    def test_threaded_projection_prefers_durable_final_answer_over_generic_message(
        self,
    ) -> None:
        implementation = ImplementationResult(
            message="No workflow edit was applied.",
            durable_response={
                "outcome": {"kind": "noop", "reason": "answer_only"},
                "terminal_state": "no_op",
                "graph_unchanged": True,
                "accepted_batch": [],
                "final_answer": {
                    "text": ANSWER,
                    "evidence_refs": list(EVIDENCE_REFS),
                },
                "evidence_refs": list(EVIDENCE_REFS),
            },
        )
        seen_replies: list[str] = []

        def grounded(reply: str, **kwargs: Any) -> str:
            seen_replies.append(reply)
            return reply

        kernel = ThreadedKernel(
            resolve_spec=lambda profile, stage: AgentSpecShape(
                "hermes", "offline", "medium"
            ),
            run_implement=lambda *args, **kwargs: implementation,
            emit_phase=lambda *args, **kwargs: None,
            enforce_reply_grounding=grounded,
            accepted_delta_ops=lambda result: (),
            implementation_landed_edit=lambda result: False,
            no_candidate_reason=lambda result: "answer_only",
        )
        ports = ExecutorHostPorts(
            handle_agent_edit=lambda *args, **kwargs: {},
            payload_hash=lambda payload: "hash",
            classify_failure=lambda *args, **kwargs: None,
            failure_envelope=lambda *args, **kwargs: None,
            begin_deepseek_usage_capture=lambda: object(),
            snapshot_deepseek_usage_capture=lambda: ({}, False),
            end_deepseek_usage_capture=lambda token: None,
            begin_model_attempt_capture=lambda: object(),
            snapshot_model_attempt_capture=lambda: (),
            end_model_attempt_capture=lambda token: None,
        )

        result = run_threaded_executor(
            ExecutorRequest(
                query="Explain the SVD conditioning path",
                pipeline_mode="threaded",
                interaction_mode="answer_only",
            ),
            kernel=kernel,
            host_ports=ports,
            executor_id="offline",
        )

        assert result.ok is True
        assert result.reply == ANSWER
        assert seen_replies == [ANSWER]
        assert result.to_dict()["final_answer"]["evidence_refs"] == list(
            EVIDENCE_REFS
        )

    def test_handle_agent_edit_closes_no_delta_turn_with_authored_answer(
        self,
        tmp_path: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from vibecomfy.comfy_nodes.agent import edit

        class Provider:
            schema = NodeSchema(
                class_type="LoadImage",
                pack=None,
                inputs={"image": InputSpec("IMAGEUPLOAD", required=True)},
                outputs=[OutputSpec("IMAGE", "IMAGE")],
                source_provider="offline-test",
                confidence=1.0,
            )

            def get_schema(self, class_type: str) -> NodeSchema | None:
                return self.schema if class_type == "LoadImage" else None

            def schemas(self) -> dict[str, NodeSchema]:
                return {"LoadImage": self.schema}

        graph = {
            "last_node_id": 1,
            "last_link_id": 0,
            "nodes": [
                {
                    "id": 1,
                    "type": "LoadImage",
                    "mode": 0,
                    "pos": [0, 0],
                    "size": [210, 58],
                    "widgets_values": ["example.png"],
                    "outputs": [{"name": "IMAGE", "type": "IMAGE"}],
                    "properties": {"vibecomfy_uid": "loadimage"},
                }
            ],
            "links": [],
            "groups": [],
        }
        monkeypatch.setattr(
            edit,
            "run_model_turn",
            lambda **kwargs: pytest.fail("explicit final answer must skip narrator"),
        )

        result = edit.handle_agent_edit(
            {
                "task": "Explain this workflow.",
                "graph": graph,
                "session_id": "explicit-final-answer",
                "pipeline_mode": "threaded",
                "interaction_mode": "answer_only",
                "max_batches": 1,
            },
            schema_provider=Provider(),
            deepseek_client=lambda messages: {
                "message": "Earlier generic prose.",
                "batch": (
                    "done(final_answer="
                    + repr(ANSWER)
                    + ", evidence_refs=['workflow:svd'])"
                ),
            },
            session_root=tmp_path,
        )

        assert result["ok"] is True
        assert result["graph_unchanged"] is True
        assert result["outcome"]["kind"] == "noop"
        assert result["accepted_batch"] == []
        assert result["message"] == ANSWER
        assert result["final_answer"] == {
            "text": ANSWER,
            "evidence_refs": ["workflow:svd"],
        }
