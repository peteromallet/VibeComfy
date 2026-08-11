"""CLI entrypoint for demo_factory."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click


def _export_ready_ui(ready_id: str) -> dict | None:
    """Emit a schema'd golden UI graph for a ready template via offline port export.

    Thin delegation to the internal helper in ``run_campaign.py`` (the Click
    CLI is the user-facing surface; campaign machinery lives internal). The
    import is deferred so ``python -m vibecomfy.demo_factory --help`` does not
    pull the heavy campaign module chain.
    """
    from vibecomfy.demo_factory.run_campaign import _export_ready_ui as _export

    return _export(ready_id)


@click.group()
def cli() -> None:
    """VibeComfy demo scenario factory CLI."""
    pass


@cli.command()
@click.option(
    "--transcript",
    type=click.Path(exists=True, path_type=Path),
    help="Path to transcript run_dir with original.ui.json, candidate.ui.json, request.json",
)
@click.option(
    "--ready",
    type=str,
    help="Ready template ID (e.g., image/basic_image_upscale)",
)
@click.option(
    "--fault",
    type=str,
    help="Fault family for synthetic injection (e.g., final-output-bypass)",
)
@click.option(
    "--campaign",
    type=click.Path(path_type=Path),
    default=Path("out/demo-candidate-factory"),
    help="Campaign root directory",
)
@click.option(
    "--tag",
    type=str,
    default="demo-factory",
    help="Run tag for evidence directory",
)
def run_case(
    transcript: Path | None,
    ready: str | None,
    fault: str | None,
    campaign: Path,
    tag: str,
) -> None:
    """Run a single demo scenario case.

    Either --transcript or (--ready + --fault) must be provided.
    """
    # Get campaign root (latest timestamped dir under campaign base)
    if campaign.is_file() or (campaign.is_dir() and not (campaign / "campaign.json").exists()):
        # Find latest campaign dir
        campaign_base = campaign
        campaign_dirs = sorted(
            [d for d in campaign_base.iterdir() if d.is_dir() and (d / "campaign.json").exists()],
            reverse=True,
        )
        if not campaign_dirs:
            click.echo(f"No campaign found under {campaign_base}")
            sys.exit(1)
        campaign_root = campaign_dirs[0]
    else:
        campaign_root = campaign

    click.echo(f"Using campaign root: {campaign_root}")

    # Load and run case
    from vibecomfy.demo_factory.case import run_synthetic_case, run_transcript_case
    from vibecomfy.demo_factory.ledger import CampaignLedger

    if transcript:
        # Transcript case
        click.echo(f"Running transcript case: {transcript}")
        case = run_transcript_case(
            transcript_run_dir=transcript,
            output_base=campaign_root,
            tag=tag,
        )
    elif ready and fault:
        # Emit a schema'd golden UI graph via offline `port export` (object_info cache).
        golden = _export_ready_ui(ready)
        if golden is None:
            click.echo(f"Failed to export ready template {ready}")
            sys.exit(1)

        click.echo(f"Running synthetic case: {ready} with fault {fault}")
        case = run_synthetic_case(
            golden=golden,
            fault_family=fault,
            output_base=campaign_root,
            tag=tag,
        )
    else:
        click.echo("Either --transcript or (--ready + --fault) must be provided")
        sys.exit(1)

    # Register in ledger
    ledger = CampaignLedger(campaign_root)
    ledger.register_case(case)

    # Report verdict
    click.echo(f"\nCase {case.case_id} complete:")
    click.echo(f"  Stage: {case.stage.value}")
    click.echo(f"  Verdict: {case.verdict.value if case.verdict else 'pending'}")

    if case.oracle_result:
        click.echo(f"\nGate results:")
        for gate in case.oracle_result.gates:
            status = "✓" if gate.passed else "✗"
            click.echo(f"  {status} {gate.name}: {gate.reason}")

    # Campaign stats
    stats = ledger.get_campaign_stats()
    click.echo(f"\nCampaign stats: {stats['total']} cases total")
    for verdict, count in stats.get("by_verdict", {}).items():
        click.echo(f"  {verdict}: {count}")


@cli.command()
@click.option(
    "--campaign",
    type=click.Path(path_type=Path),
    default=Path("out/demo-candidate-factory"),
    help="Campaign root directory",
)
def stats(campaign: Path) -> None:
    """Show campaign statistics."""
    # Get campaign root
    if campaign.is_file() or (campaign.is_dir() and not (campaign / "campaign.json").exists()):
        campaign_base = campaign
        campaign_dirs = sorted(
            [d for d in campaign_base.iterdir() if d.is_dir() and (d / "campaign.json").exists()],
            reverse=True,
        )
        if not campaign_dirs:
            click.echo(f"No campaign found under {campaign_base}")
            sys.exit(0)
        campaign_root = campaign_dirs[0]
    else:
        campaign_root = campaign

    from vibecomfy.demo_factory.ledger import CampaignLedger

    ledger = CampaignLedger(campaign_root)
    stats = ledger.get_campaign_stats()

    click.echo(f"Campaign: {campaign_root.name}")
    click.echo(f"Total cases: {stats['total']}")
    click.echo("\nBy verdict:")
    for verdict, count in stats.get("by_verdict", {}).items():
        click.echo(f"  {verdict}: {count}")
    click.echo("\nBy stage:")
    for stage, count in stats.get("by_stage", {}).items():
        click.echo(f"  {stage}: {count}")


@cli.command()
@click.option(
    "--ready",
    type=str,
    help="Ready template ID (e.g., image/basic_image_upscale)",
)
@click.option(
    "--workflow-list",
    type=click.Path(exists=True, path_type=Path),
    help="File with one ready template ID per line (for batch creative runs)",
)
@click.option(
    "--campaign",
    type=click.Path(path_type=Path),
    default=Path("out/demo-candidate-factory"),
    help="Campaign root directory",
)
@click.option(
    "--tag",
    type=str,
    default="demo-factory",
    help="Run tag for evidence directory",
)
def run_creative(
    ready: str | None,
    workflow_list: Path | None,
    campaign: Path,
    tag: str,
) -> None:
    """Run a creative LLM-proposed bug injection case.

    The creative engine uses DeepSeek to propose per-workflow, realistic,
    subtle, single-cause defects. Either --ready or --workflow-list must be provided.
    """
    # Get campaign root
    if campaign.is_file() or (campaign.is_dir() and not (campaign / "campaign.json").exists()):
        campaign_base = campaign
        campaign_dirs = sorted(
            [d for d in campaign_base.iterdir() if d.is_dir() and (d / "campaign.json").exists()],
            reverse=True,
        )
        if not campaign_dirs:
            click.echo(f"No campaign found under {campaign_base}, creating new one")
            campaign_base.mkdir(parents=True, exist_ok=True)
            campaign_root = campaign_base / "20260723-001"
            campaign_root.mkdir(parents=True, exist_ok=True)
            (campaign_root / "campaign.json").write_text(json.dumps({
                "schema_version": "demo_factory_campaign_v1",
                "campaign_id": "20260723-001",
                "created_at": _timestamp(),
                "status": "running",
            }, indent=2), encoding="utf-8")
        else:
            campaign_root = campaign_dirs[0]
    else:
        campaign_root = campaign

    click.echo(f"Using campaign root: {campaign_root}")

    from vibecomfy.demo_factory.case import run_creative_case
    from vibecomfy.demo_factory.ledger import CampaignLedger

    # Collect workflow IDs
    workflow_ids = []
    if ready:
        workflow_ids.append(ready)
    if workflow_list:
        workflow_ids.extend([
            line.strip() for line in workflow_list.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ])

    if not workflow_ids:
        click.echo("Either --ready or --workflow-list must be provided")
        sys.exit(1)

    # Run cases
    ledger = CampaignLedger(campaign_root)
    for workflow_id in workflow_ids:
        click.echo(f"\nRunning creative case for: {workflow_id}")

        golden = _export_ready_ui(workflow_id)
        if golden is None:
            click.echo(f"Failed to export ready template {workflow_id}")
            continue

        case = run_creative_case(
            golden=golden,
            workflow_label=workflow_id,
            output_base=campaign_root,
            tag=tag,
        )

        ledger.register_case(case)

        click.echo(f"\nCase {case.case_id} complete:")
        click.echo(f"  Stage: {case.stage.value}")
        click.echo(f"  Verdict: {case.verdict.value if case.verdict else 'pending'}")

        if case.oracle_result:
            click.echo(f"\nGate results:")
            for gate in case.oracle_result.gates:
                status = "✓" if gate.passed else "✗"
                click.echo(f"  {status} {gate.name}: {gate.reason}")

    # Campaign stats
    stats = ledger.get_campaign_stats()
    click.echo(f"\nCampaign stats: {stats['total']} cases total")
    for verdict, count in stats.get("by_verdict", {}).items():
        click.echo(f"  {verdict}: {count}")


def _timestamp() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    cli()
