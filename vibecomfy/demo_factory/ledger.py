"""Campaign ledger for demo_factory.

Append INDEX.md row + events.jsonl event + per-case summary.md + status.json.
The INDEX.md row matches the runbook's 12-column schema. Success rows are only
written after their oracle/proof files are durable.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vibecomfy.demo_factory.case import Case, CaseStage
from vibecomfy.demo_factory.oracle import Verdict

_INDEX_HEADER = (
    "# Demo Candidate Campaign {cid}\n\n"
    "| Case | Attempt | Source | Fault family | Inquiry | Baseline | Fault proof | "
    "Fixer | Repair oracle | Runtime | Verdict | Evidence |\n"
    "|---|---:|---|---|---|---|---|---|---|---|---|---|\n"
)


@dataclass
class CampaignLedger:
    """Campaign ledger for tracking case results."""
    campaign_root: Path
    campaign_json: dict[str, Any] = None

    def __post_init__(self):
        if self.campaign_json is None:
            campaign_file = self.campaign_root / "campaign.json"
            if campaign_file.is_file():
                self.campaign_json = json.loads(campaign_file.read_text(encoding="utf-8"))
            else:
                self.campaign_json = {
                    "campaign_id": self.campaign_root.name,
                    "created_at": _timestamp(),
                    "cases": [],
                }

    def index_path(self) -> Path:
        return self.campaign_root / "INDEX.md"

    def events_path(self) -> Path:
        return self.campaign_root / "events.jsonl"

    def _verdict_cell(self, verdict: Verdict | None) -> str:
        if verdict is None:
            return "—"
        return {
            Verdict.ACCEPTED: "PASS",
            Verdict.ALTERNATIVE_REPAIR: "ALT",
            Verdict.REJECTED: "FAIL",
            Verdict.BASELINE_REJECTED: "BASE_REJ",
            Verdict.INFRA_BLOCKED: "INFRA",
            Verdict.UNDETERMINED: "UNDET",
        }.get(verdict, verdict.value)

    def _stage_columns(self, case: Case) -> tuple[str, str, str, str, str]:
        """Return (baseline, fault_proof, fixer, repair_oracle, runtime) cells."""
        baseline = fault_proof = fixer = repair = runtime = "—"
        stage = case.stage

        if stage == CaseStage.BASELINE_REJECTED:
            baseline = "FAIL"
        elif stage == CaseStage.INFRA_BLOCKED:
            baseline = fault_proof = "PASS"
            fixer = "BLOCKED"
        elif stage == CaseStage.REPAIR_FAILED:
            baseline = fault_proof = "PASS"
            fixer = "FAILED"
        elif stage == CaseStage.COMPLETE:
            baseline = fault_proof = "PASS"
            fixer = "candidate"
            repair = self._verdict_cell(case.oracle_result.verdict if case.oracle_result else case.verdict)
            runtime = "—"
        return baseline, fault_proof, fixer, repair, runtime

    def append_case_row(self, case: Case) -> None:
        """Append a runbook-schema row to INDEX.md for a completed case."""
        if case.stage not in {
            CaseStage.COMPLETE,
            CaseStage.BASELINE_REJECTED,
            CaseStage.REPAIR_FAILED,
            CaseStage.INFRA_BLOCKED,
        }:
            return

        # Never write a success row before its oracle files are durable.
        if case.stage == CaseStage.COMPLETE and case.case_dir:
            if not (case.case_dir / "proof" / "baseline.json").is_file():
                return

        inquiry = (case.inquiry or "").replace("|", "/").replace("\n", " ").strip()
        if len(inquiry) > 60:
            inquiry = inquiry[:57] + "..."

        baseline, fault_proof, fixer, repair, runtime = self._stage_columns(case)
        verdict = self._verdict_cell(case.verdict)
        evidence = f"cases/{case.case_id}/summary.md"

        row = (
            f"| {case.case_id} | {case.attempt} | {case.source} | "
            f"{case.fault_family or '—'} | {inquiry} | {baseline} | {fault_proof} | "
            f"{fixer} | {repair} | {runtime} | {verdict} | {evidence} |\n"
        )

        index_path = self.index_path()
        index_path.parent.mkdir(parents=True, exist_ok=True)
        if not index_path.exists():
            cid = self.campaign_json.get("campaign_id", self.campaign_root.name)
            index_path.write_text(_INDEX_HEADER.format(cid=cid), encoding="utf-8")

        with index_path.open("a", encoding="utf-8") as f:
            f.write(row)

    def append_event(self, event_type: str, data: dict[str, Any]) -> None:
        events_path = self.events_path()
        events_path.parent.mkdir(parents=True, exist_ok=True)
        event = {"timestamp": _timestamp(), "type": event_type, **data}
        with events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def write_case_summary(self, case: Case) -> None:
        if case.case_dir is None:
            return
        summary_path = case.case_dir / "summary.md"
        lines = [
            f"# {case.case_id}\n\n",
            f"- Source: {case.source}\n",
            f"- Fault family: {case.fault_family or '—'}\n",
            f"- Attempt: {case.attempt}\n",
            f"- Stage: {case.stage.value}\n",
            f"- Verdict: {self._verdict_cell(case.verdict)}\n\n",
            "## Inquiry\n\n",
            f"{case.inquiry}\n\n",
        ]
        if case.oracle_result:
            lines.extend([
                "## Oracle\n\n",
                f"- Gates passed: {sum(1 for g in case.oracle_result.gates if g.passed)}/{len(case.oracle_result.gates)}\n\n",
                "### Gate results\n\n",
            ])
            for gate in case.oracle_result.gates:
                mark = "✓" if gate.passed else "✗"
                lines.append(f"- {mark} **{gate.name}**: {gate.reason}\n")
        summary_path.write_text("".join(lines), encoding="utf-8")

    def register_case(self, case: Case) -> None:
        self.append_case_row(case)
        self.append_event("case_completed", {
            "case_id": case.case_id,
            "stage": case.stage.value,
            "verdict": case.verdict.value if case.verdict else None,
            "source": case.source,
            "fault_family": case.fault_family,
        })
        self.write_case_summary(case)

    def get_campaign_stats(self) -> dict[str, Any]:
        events_path = self.events_path()
        if not events_path.exists():
            return {"total": 0, "by_verdict": {}, "by_stage": {}, "good": 0}
        stats: dict[str, Any] = {"total": 0, "by_verdict": {}, "by_stage": {}, "good": 0}
        good_verdicts = {"accepted", "alternative_repair"}
        with events_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") != "case_completed":
                    continue
                stats["total"] += 1
                verdict = event.get("verdict")
                if verdict:
                    stats["by_verdict"][verdict] = stats["by_verdict"].get(verdict, 0) + 1
                    if verdict in good_verdicts:
                        stats["good"] += 1
                stage = event.get("stage")
                if stage:
                    stats["by_stage"][stage] = stats["by_stage"].get(stage, 0) + 1
        return stats


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
