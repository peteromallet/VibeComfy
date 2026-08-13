#!/usr/bin/env python3
"""Daily agentic workflow-source scan for the Hivemind corpus.

Runs AFTER the brain_of_bndc daily summary (11:00 UTC). Deterministic context
gathering (recent Discord workflow links + existing corpus state) feeds a
hermes agent (DeepSeek Flash by default) with ``file,web,terminal`` tools, so
it can git clone candidate repos, find NEW ComfyUI workflow files, classify
them, and report exact URLs. The driver then ingests the agent's findings into
the external-workflow corpus and uploads new rows to Hivemind.

Pipeline:
  1. gather_context   — deterministic: recent Discord messages (Supabase
                        archive), github_scan.json repo inventory, manifest
                        summary, known minimax repos.
  2. run_agent        — launch_hermes_agent.py --toolsets=file,web,terminal
                        --model deepseek:deepseek-v4-flash with a brief that
                        names the context files, the repos to explore, and the
                        output contract (JSON list of {repo, path, url}).
  3. ingest_findings  — download each reported workflow file, run
                        ingest_external_workflows.py, then upload new rows to
                        Hivemind (--skip-existing, idempotent).

Everything is idempotent: re-runs no-op on already-ingested workflows.

Usage:
    python scripts/daily_agentic_workflow_scan.py --dry-run           # agent + report, no ingest/upload
    python scripts/daily_agentic_workflow_scan.py                     # full: agent -> ingest -> upload
    python scripts/daily_agentic_workflow_scan.py --repos "owner/repo,..."  # scope exploration

Requires:
    DEEPSEEK_API_KEY (or the hermes key pool env) for the agent
    SUPABASE_URL + SUPABASE_SERVICE_KEY (brain-of-bndc .env) for Discord context
    GITHUB_TOKEN (optional, for repo enumeration / raw downloads)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

LAUNCHER = Path.home() / ".claude" / "skills" / "subagent-launcher" / "launch_hermes_agent.py"
DEFAULT_ENV_FILE = Path("/Users/peteromalley/Documents/banodoco-workspace/brain-of-bndc/.env")

# Repos that reliably hold minimax/ComfyUI workflows. Extended by the agent at
# runtime (it may discover more); these seed the brief.
SEED_REPOS: tuple[str, ...] = (
    "Comfy-Org/workflow_templates",
    "mdkberry/comfyui_workflows",
    "NikoDemon80/ComfyUI-H3-Motion-Context",
    "Larryvrh/ComfyUI-MiniMax-H3-Turbo",
    "nkxx188/ComfyUI-MiniMaxH3-Easy",
    "huangserva/ComfyUI_MiniMaxH3_Director",
    "xmarre/ComfyUI-Spectrum-MiniMax-H3",
    "T8mars/comfyui-minimax-h3-audio-T8",
    "roadmaus/ComfyUI-MiniMax-Creator",
    "Ercelcan/ComfyUI-MiniMax-Creator",
    "ethanfel/ComfyUI-MiniMaxH3-Contex-Loop",
)

QUALITY_CHANNELS: tuple[str, ...] = (
    "minimax_h3_resources",
    "minimax_h3_chatter",
    "resources",
    "comfyui",
    "wan_comfyui",
)

AGENT_BRIEF_TEMPLATE = """\
You are the daily workflow-source scout for the Banodoco Hivemind knowledge corpus.

# Mission
Find NEW ComfyUI workflow files that are NOT already in the corpus, with a
strong preference for MiniMax H3 / Hailuo workflows. Report each as an exact
URL (raw.githubusercontent.com or github.com blob) plus the file path and a
one-line description.

# Context files (read them first)
- {context_dir}/recent_discord_workflow_links.json — workflow links shared in
  Discord in the last 26h (channel, author, url). These are the freshest leads.
- {context_dir}/repo_inventory.json — repos already scanned and what was found,
  so you do not re-report known files.
- {context_dir}/manifest_summary.json — current corpus state (unique workflows,
  sources, recent workflow titles).
- {context_dir}/seed_repos.txt — known good repos to explore.

# How to explore
- You HAVE a terminal: `git clone --depth 1 <repo> /tmp/explore/<name>` is
  allowed and encouraged. Also use `gh api` / curl / the GitHub git trees API
  when cloning is wasteful (e.g. a repo with one example_workflows dir).
- Look in example_workflows/, workflows/, templates/, *.json at repo root,
  and PNG files (ComfyUI embeds workflow graphs in PNG chunks).
- Prefer files that parse as ComfyUI workflows (JSON with "nodes" list and
  widget values, or API format with numeric keys + class_type, or PNG with an
  embedded "workflow"/"prompt" tEXt chunk).
- Do NOT report: repo homepages, README.md, .py source files, plain images
  without embedded workflow metadata, or files already in repo_inventory.json.

# Output contract
End with a single JSON array on its own line, nothing after it:
[
  {{"repo": "owner/name", "path": "example_workflows/x.json", "url": "https://raw.githubusercontent.com/owner/name/main/example_workflows/x.json", "description": "one line"}}
]
Include every new workflow you found (up to ~30). If you found none, output
[] and say why in one line before it.
"""


def _load_env(path: Path) -> None:
    """Load KEY=VALUE lines from an env file into os.environ (no clobber)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


# ---- Phase 1: context gathering --------------------------------------------


async def _fetch_discord_links(since: datetime) -> List[Dict[str, Any]]:
    """Query the bot's Supabase archive for workflow links in quality channels."""
    import aiohttp

    base = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_KEY") or ""
    if not base or not service_key:
        print("WARN: SUPABASE_URL/SERVICE_KEY missing — skipping Discord context", file=sys.stderr)
        return []
    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}
    links: List[Dict[str, Any]] = []
    async with aiohttp.ClientSession() as session:
        # discord_messages has no channel_name/author_name columns; fetch ids
        # and resolve names from the lookup tables afterwards.
        params = {
            "select": "message_id,channel_id,author_id,content,created_at,reaction_count",
            "created_at": f"gte.{since.isoformat()}",
            "limit": "500",
        }
        async with session.get(f"{base}/rest/v1/discord_messages", params=params, headers=headers) as resp:
            if resp.status != 200:
                print(f"WARN: discord_messages query returned {resp.status}", file=sys.stderr)
                return []
            rows = await resp.json()

        channel_names: Dict[int, str] = {}
        author_names: Dict[int, str] = {}
        try:
            async with session.get(
                f"{base}/rest/v1/discord_channels", params={"select": "channel_id,channel_name", "limit": "10000"}, headers=headers
            ) as resp:
                if resp.status == 200:
                    ch_rows = await resp.json()
                    for row in ch_rows or []:
                        if row.get("channel_id") is not None:
                            channel_names[int(row["channel_id"])] = str(row.get("channel_name") or row["channel_id"])
        except Exception:  # noqa: BLE001
            pass
        try:
            async with session.get(
                f"{base}/rest/v1/discord_users", params={"select": "user_id,display_name", "limit": "10000"}, headers=headers
            ) as resp:
                if resp.status == 200:
                    u_rows = await resp.json()
                    for row in u_rows or []:
                        if row.get("user_id") is not None:
                            author_names[int(row["user_id"])] = str(row.get("display_name") or row["user_id"])
        except Exception:  # noqa: BLE001
            pass

    url_re = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
    for row in rows or []:
        channel_name = channel_names.get(int(row.get("channel_id") or 0), "")
        if channel_name not in QUALITY_CHANNELS:
            continue
        content = row.get("content") or ""
        for match in url_re.finditer(content):
            url = match.group(0).rstrip(".,;:)]}")
            if re.search(r"(github\.com|raw\.githubusercontent\.com|huggingface\.co|cdn\.discordapp\.com)", url):
                links.append({
                    "url": url,
                    "channel": channel_name,
                    "author": author_names.get(int(row.get("author_id") or 0)),
                    "message_id": row.get("message_id"),
                    "created_at": row.get("created_at"),
                    "context": " ".join(content.split())[:200],
                })
    return links


def _repo_inventory() -> Dict[str, Any]:
    """Summarize the last github_scan.json so the agent skips known files."""
    scan_path = REPO_ROOT / "external_workflows" / "github_scan.json"
    if not scan_path.exists():
        return {"repos": [], "total_workflow_rows": 0}
    try:
        data = json.loads(scan_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"repos": [], "total_workflow_rows": 0}
    results = data.get("results") or []
    workflow_rows = [r for r in results if r.get("status") in {"comfy_workflow", "image_embedded_comfy_workflow"}]
    by_repo: Dict[str, int] = {}
    for row in workflow_rows:
        key = f"{row.get('owner')}/{row.get('repo')}"
        by_repo[key] = by_repo.get(key, 0) + 1
    return {
        "repos": [{"repo": k, "workflow_files": v} for k, v in sorted(by_repo.items(), key=lambda x: -x[1])],
        "total_workflow_rows": len(workflow_rows),
        "scan_generated_at": data.get("summary", {}).get("generated_at"),
    }


def _manifest_summary() -> Dict[str, Any]:
    manifest_path = REPO_ROOT / "external_workflows" / "manifest.json"
    if not manifest_path.exists():
        return {"workflows": 0}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"workflows": 0}
    workflows = data.get("workflows") or []
    sources: Dict[str, int] = {}
    for w in workflows:
        src = ((w.get("primary_source") or {}).get("source")) or "unknown"
        sources[src] = sources.get(src, 0) + 1
    return {
        "workflows": len(workflows),
        "sources": sources,
        "recent_titles": [((w.get("summary") or {}).get("title") or "")[:60] for w in workflows[-15:]],
        "updated_at": data.get("updated_at"),
    }


def gather_context(context_dir: Path, *, lookback_hours: int = 26) -> Dict[str, Any]:
    """Deterministic pre-pass: write context files the agent will read."""
    context_dir.mkdir(parents=True, exist_ok=True)
    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    discord_links = asyncio.run(_fetch_discord_links(since))
    (context_dir / "recent_discord_workflow_links.json").write_text(
        json.dumps(discord_links, indent=2, sort_keys=True), encoding="utf-8"
    )

    inventory = _repo_inventory()
    (context_dir / "repo_inventory.json").write_text(
        json.dumps(inventory, indent=2, sort_keys=True), encoding="utf-8"
    )

    summary = _manifest_summary()
    (context_dir / "manifest_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )

    (context_dir / "seed_repos.txt").write_text("\n".join(SEED_REPOS) + "\n", encoding="utf-8")

    return {
        "context_dir": str(context_dir),
        "discord_links": len(discord_links),
        "known_repos": len(inventory.get("repos", [])),
        "manifest_workflows": summary.get("workflows", 0),
    }


# ---- Phase 2: agentic exploration ------------------------------------------


def _write_brief(context_dir: Path, extra_repos: List[str]) -> Path:
    brief_path = context_dir / "brief.md"
    brief = AGENT_BRIEF_TEMPLATE.format(context_dir=context_dir)
    if extra_repos:
        brief += "\n\n# Extra repos to explore (from --repos)\n" + "\n".join(f"- {r}" for r in extra_repos) + "\n"
    brief_path.write_text(brief, encoding="utf-8")
    return brief_path


def run_agent(context_dir: Path, *, model: str, toolsets: str, extra_repos: List[str], timeout: int) -> str:
    """Launch the hermes agent; returns its final response text."""
    brief_path = _write_brief(context_dir, extra_repos)
    if not LAUNCHER.exists():
        raise FileNotFoundError(f"hermes launcher not found: {LAUNCHER}")

    cmd = [
        sys.executable,
        str(LAUNCHER),
        "--model", model,
        "--toolsets", toolsets,
        "--query_file", str(brief_path),
        "--project-dir", str(REPO_ROOT),
    ]
    print(f"[agent] launching: {' '.join(cmd[:4])} …", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        print(f"[agent] exit {result.returncode}; stderr tail:\n{result.stderr[-2000:]}", file=sys.stderr)
    return result.stdout


def parse_agent_findings(agent_output: str) -> List[Dict[str, Any]]:
    """Extract the final JSON array from the agent's response."""
    if not agent_output:
        return []
    # Last JSON array in the output is the contract.
    matches = list(re.finditer(r"\[\s*\{.*?\}\s*\]", agent_output, re.DOTALL))
    if not matches:
        return []
    try:
        findings = json.loads(matches[-1].group(0))
    except json.JSONDecodeError:
        return []
    return [f for f in findings if isinstance(f, dict) and f.get("url")]


# ---- Phase 3: ingest + upload ----------------------------------------------


def ingest_and_upload(findings: List[Dict[str, Any]], *, dry_run: bool) -> Dict[str, int]:
    """Download each finding, ingest into the corpus, upload new rows."""
    counts = {"findings": len(findings), "ingested": 0, "uploaded": 0, "skipped": 0, "errors": 0}
    if not findings or dry_run:
        return counts

    # Download raw JSON workflows into a scan-shaped file.
    scan_rows: List[Dict[str, Any]] = []
    shadow_dir = REPO_ROOT / "external_workflows" / ".shadow" / "source"
    shadow_dir.mkdir(parents=True, exist_ok=True)
    import hashlib
    import urllib.request

    for f in findings:
        url = f["url"]
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "vibecomfy-agentic-scan/0.1"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            sha = hashlib.sha256(data).hexdigest()
            filename = url.rsplit("/", 1)[-1].split("?", 1)[0]
            saved = shadow_dir / f"{sha[:16]}-{re.sub(r'[^A-Za-z0-9._-]+', '_', filename)}"
            if not saved.exists():
                saved.write_bytes(data)
            scan_rows.append({
                "owner": (f.get("repo") or "unknown").split("/")[0],
                "repo": (f.get("repo") or "unknown").split("/")[-1],
                "path": f.get("path") or filename,
                "filename": filename,
                "source_url": url,
                "url": url,
                "saved_path": str(saved),
                "status": "comfy_workflow",
                "sha256": sha,
                "bytes": len(data),
            })
        except Exception as exc:  # noqa: BLE001
            print(f"[ingest] download failed {url}: {exc}", file=sys.stderr)
            counts["errors"] += 1

    if not scan_rows:
        return counts

    scan_path = REPO_ROOT / "external_workflows" / ".shadow" / "agentic_scan.json"
    scan_path.write_text(json.dumps({"summary": {"source": "github"}, "results": scan_rows}), encoding="utf-8")

    ingest = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "ingest_external_workflows.py"),
         "--scan-json", str(scan_path), "--source", "github",
         "--discovered-by", "agentic-daily-scan", "--skip-errors"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    print(f"[ingest] exit {ingest.returncode}: {ingest.stdout.strip()[-300:]}", file=sys.stderr)
    if ingest.returncode != 0:
        counts["errors"] += 1
        return counts

    # Scope the upload to rows this scan actually created. The uploader builds
    # envelopes for every manifest row, and the scratchpad emitter per row is
    # slow — a full-manifest pass on a 2800+ row corpus stalls for hours. Only
    # newly-ingested rows (no hivemind_upload.status yet) need uploading; the
    # rest are already idempotently skipped.
    manifest = json.loads((REPO_ROOT / "external_workflows" / "manifest.json").read_text(encoding="utf-8"))
    pending = [
        w["workflow_id"]
        for w in manifest.get("workflows", [])
        if (w.get("primary_source") or {}).get("discovered_by") == "agentic-daily-scan"
        and not (w.get("hivemind_upload") or {}).get("status")
    ]
    upload_cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "upload_external_workflows_to_hivemind.py"),
        "--skip-existing", "--sleep", "0.3",
        "--enrich", "--model", os.environ.get("AGENTIC_SCAN_ENRICH_MODEL", "deepseek-chat"),
    ]
    for wid in pending:
        upload_cmd += ["--only", wid]
    upload = subprocess.run(
        upload_cmd,
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    print(f"[upload] exit {upload.returncode}: {upload.stdout.strip()[-500:]}", file=sys.stderr)
    counts["uploaded"] = sum(1 for line in upload.stdout.splitlines() if '"status": "uploaded"' in line)
    counts["skipped"] = sum(1 for line in upload.stdout.splitlines() if '"status": "skipped_existing"' in line)
    counts["errors"] += sum(1 for line in upload.stdout.splitlines() if '"status": "error"' in line)
    return counts


# ---- Main ------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--context-dir", type=Path, default=Path(tempfile.gettempdir()) / "agentic-scan-context")
    parser.add_argument("--model", default="deepseek:deepseek-v4-flash")
    parser.add_argument("--toolsets", default="file,web,terminal")
    parser.add_argument("--repos", default="", help="Comma-separated extra owner/repo to explore")
    parser.add_argument("--lookback-hours", type=int, default=26)
    parser.add_argument("--agent-timeout", type=int, default=1800)
    parser.add_argument("--dry-run", action="store_true", help="Agent + report only; no ingest/upload")
    args = parser.parse_args(argv)

    _load_env(args.env_file)

    print("=== Phase 1: gather context ===", file=sys.stderr)
    context = gather_context(args.context_dir, lookback_hours=args.lookback_hours)
    print(f"context: {json.dumps(context, sort_keys=True)}", file=sys.stderr)

    print("=== Phase 2: agentic exploration ===", file=sys.stderr)
    extra_repos = [r.strip() for r in args.repos.split(",") if r.strip()]
    agent_output = run_agent(args.context_dir, model=args.model, toolsets=args.toolsets,
                             extra_repos=extra_repos, timeout=args.agent_timeout)
    (args.context_dir / "agent_output.md").write_text(agent_output or "", encoding="utf-8")
    print(f"agent output: {len(agent_output)} chars (saved to {args.context_dir / 'agent_output.md'})", file=sys.stderr)

    findings = parse_agent_findings(agent_output)
    print(f"=== Phase 3: {len(findings)} findings ===", file=sys.stderr)
    for f in findings:
        print(f"  {f.get('repo')}:{f.get('path')} | {f.get('description', '')[:60]}", file=sys.stderr)

    counts = ingest_and_upload(findings, dry_run=args.dry_run)
    print(json.dumps({"status": "ok" if not counts["errors"] else "partial", **counts}, sort_keys=True))
    return 0 if not counts["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
