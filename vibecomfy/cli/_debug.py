#!/usr/bin/env python3
"""VibeComfy agent-edit debug / usage-data tool.

One place to fetch EVERYTHING about in-ComfyUI agent-edit usage: every query you
ran, what the agent did, whether it was faithful, whether it actually landed on
the canvas, why anything failed, plus runtime state and a shareable bundle.

The agent-edit feature writes a rich per-turn record under
  <ComfyUI>/out/editor_sessions/<session>/turns/<turn>/
and a per-session lifecycle file
  <ComfyUI>/out/editor_sessions/<session>/session_state.json
This tool reads both and joins them.

Subcommands
-----------
  log      Table of every turn: query, outcome, lifecycle (accepted/rejected/
           candidate/superseded), fidelity, canvas-apply, node count.   [default]
  turn     Deep dump of one turn: query, route/model, gates, the agent's actual
           batch statements + per-statement results, a faithful node-diff
           (submitted vs candidate, normalizing the vibecomfy_uid stamp),
           lifecycle, errors.
  stats    Aggregate: totals, accept rate, faithfulness rate, failure breakdown
           by kind (MalformedModelJSON / StaleStateMismatch / ...).
  status   Live runtime: :PORT listener, /vibecomfy/agent/status, env flags,
           DeepSeek key presence, ComfyUI log tail.
  bundle   Copy ALL sessions + session_states + recent run logs + a status
           snapshot into a timestamped dir and tar.gz, for sharing/triage.
  tail     The most recent N turns (shortcut for `log --tail N`).

Examples
--------
  python3 scripts/vibecomfy_debug.py
  python3 scripts/vibecomfy_debug.py log --failed
  python3 scripts/vibecomfy_debug.py turn 2c0507db            # latest turn
  python3 scripts/vibecomfy_debug.py turn 2c0507db 0002 --batch --diff
  python3 scripts/vibecomfy_debug.py stats
  python3 scripts/vibecomfy_debug.py status
  python3 scripts/vibecomfy_debug.py bundle --out /tmp/vc_debug
  python3 scripts/vibecomfy_debug.py --json log

Env
---
  COMFY_DIR   ComfyUI checkout (default: ~/Documents/reigh-workspace/ComfyUI)
  VIBECOMFY_PORT  agent-edit port for `status` (default 8190)
Stdlib-only for session parsing; status uses httpx when available and falls back
to urllib. Never mutates session data.
"""
from __future__ import annotations
import argparse, datetime, glob, json, os, tarfile, urllib.request, shutil

HOME = os.path.expanduser("~")
COMFY_DIR = os.environ.get("COMFY_DIR", os.path.join(HOME, "Documents/reigh-workspace/ComfyUI"))
SESS_ROOT = os.path.join(COMFY_DIR, "out", "editor_sessions")
REPO_DIR = os.environ.get("VIBECOMFY_REPO", os.path.join(HOME, "Documents/reigh-workspace/vibecomfy"))
RUNS_DIR = os.path.join(REPO_DIR, "out", "runs")
PORT = os.environ.get("VIBECOMFY_PORT", "8190")

def configure_from_env():
    """Refresh path globals from env so tests/CLI invocations can override them."""
    global HOME, COMFY_DIR, SESS_ROOT, REPO_DIR, RUNS_DIR, PORT
    HOME = os.path.expanduser("~")
    COMFY_DIR = os.environ.get("COMFY_DIR", os.path.join(HOME, "Documents/reigh-workspace/ComfyUI"))
    SESS_ROOT = os.path.join(COMFY_DIR, "out", "editor_sessions")
    REPO_DIR = os.environ.get("VIBECOMFY_REPO", os.path.join(HOME, "Documents/reigh-workspace/vibecomfy"))
    RUNS_DIR = os.path.join(REPO_DIR, "out", "runs")
    PORT = os.environ.get("VIBECOMFY_PORT", "8190")

# ---------- io helpers ----------
def _load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None

def _mtime(path, default=0.0):
    try:
        return os.path.getmtime(path)
    except OSError:
        return default

def _ts(epoch):
    return datetime.datetime.fromtimestamp(epoch).strftime("%m-%d %H:%M:%S")

def _short(s, n):
    s = (s or "").strip().replace("\n", " ")
    return s[: n - 1] + "…" if len(s) > n else s

# ---------- model ----------
def _normalize_node(node):
    """Strip the systematic vibecomfy_uid stamp + volatile UI fields for a
    faithfulness comparison (only structural identity should count)."""
    import copy
    n = copy.deepcopy(node)
    props = n.get("properties")
    if isinstance(props, dict):
        props.pop("vibecomfy_uid", None)
    for k in ("pos", "size", "flags", "order"):
        n.pop(k, None)
    return json.dumps(n, sort_keys=True)

def _faithful_diff(before_graph, candidate_graph):
    if not isinstance(before_graph, dict) or not isinstance(candidate_graph, dict):
        return None
    o = {x.get("id"): x for x in before_graph.get("nodes", [])}
    c = {x.get("id"): x for x in candidate_graph.get("nodes", [])}
    changed = [i for i in (set(o) & set(c)) if _normalize_node(o[i]) != _normalize_node(c[i])]
    added = sorted(set(c) - set(o))
    removed = sorted(set(o) - set(c))
    return {
        "changed": sorted(changed), "added": added, "removed": removed,
        "before_nodes": len(o), "candidate_nodes": len(c),
        "node_types": {i: (c.get(i) or {}).get("type") for i in added},
    }

def _iter_turns():
    """Yield a joined record per turn (response.json + session_state lifecycle)."""
    for sdir in sorted(glob.glob(os.path.join(SESS_ROOT, "*"))):
        if not os.path.isdir(sdir):
            continue
        sid = os.path.basename(sdir)
        sstate = _load(os.path.join(sdir, "session_state.json")) or {}
        st_turns = sstate.get("turns", {}) if isinstance(sstate, dict) else {}
        baseline = sstate.get("baseline_turn_id")
        for tdir in sorted(glob.glob(os.path.join(sdir, "turns", "*"))):
            if not os.path.isdir(tdir):
                continue
            turn = os.path.basename(tdir)
            resp = _load(os.path.join(tdir, "response.json")) or {}
            req = _load(os.path.join(tdir, "request.json")) or {}
            life = st_turns.get(turn, {}) if isinstance(st_turns, dict) else {}
            gates = resp.get("gates") or {}
            ok = resp.get("ok")
            kind = resp.get("kind")
            unchanged = resp.get("graph_unchanged")
            lstate = life.get("state")  # accepted/rejected/candidate/unknown
            if lstate == "accepted":
                outcome = "✅ APPLIED"
            elif lstate == "rejected":
                outcome = "✗ rejected"
            elif lstate in ("unknown",) and life.get("superseded_by_turn_id"):
                outcome = "↷ superseded"
            elif ok is True and unchanged:
                outcome = "clarify/noop"
            elif ok is True:
                outcome = "candidate"        # ready, not yet applied
            elif kind:
                outcome = f"FAIL:{kind}"
            elif ok is False:
                outcome = "FAIL"
            else:
                outcome = lstate or "?"
            cand = resp.get("graph")
            yield {
                "session": sid, "turn": turn, "dir": tdir,
                "mtime": _mtime(os.path.join(tdir, "response.json"), _mtime(tdir)),
                "task": req.get("task") or resp.get("task") or "",
                "route": req.get("route") or "",
                "protocol": life.get("agent_edit_protocol"),
                "ok": ok, "kind": kind, "outcome": outcome, "lifecycle": lstate,
                "is_baseline": (turn == baseline),
                "accepted_at": life.get("accepted_at"),
                "fid": gates.get("ui_fidelity_ok"),
                "state_match": gates.get("state_match_ok"),
                "queue_validate": gates.get("queue_validate_ok"),
                "canvas_apply": resp.get("canvas_apply_allowed"),
                "queue_allowed": resp.get("queue_allowed"),
                "cand_nodes": len(cand.get("nodes", [])) if isinstance(cand, dict) else None,
                "live_token": life.get("submitted_client_live_canvas_token"),
                "summary": (resp.get("done_summary") or resp.get("message")
                            or resp.get("user_facing_message") or ""),
            }

def _all_turns(args):
    rows = sorted(_iter_turns(), key=lambda r: r["mtime"])
    if getattr(args, "session", None):
        rows = [r for r in rows if r["session"].startswith(args.session)]
    if getattr(args, "failed", False):
        rows = [r for r in rows if r["outcome"] not in ("✅ APPLIED", "candidate")]
    if getattr(args, "tail", 0):
        rows = rows[-args.tail:]
    return rows

# ---------- commands ----------
def cmd_log(args):
    configure_from_env()
    rows = _all_turns(args)
    if args.json:
        print(json.dumps(rows, indent=2, default=str)); return
    if not rows:
        print(f"(no agent-edit turns under {SESS_ROOT})"); return
    print(f"{'time':14} {'session':10} {'t':4} {'outcome':22} {'proto':9} "
          f"{'fid':5} {'cvApply':7} {'nodes':5}  query")
    print("-" * 134)
    for r in rows:
        star = "*" if r["is_baseline"] else " "
        print(f"{_ts(r['mtime']):14} {r['session'][:10]:10} {r['turn']:4} "
              f"{r['outcome']:22} {str(r['protocol'] or '-'):9} {str(r['fid']):5} "
              f"{str(r['canvas_apply']):7} {str(r['cand_nodes']):5}{star} {_short(r['task'],44)}")
        if r["outcome"].startswith("FAIL") or r["outcome"] == "clarify/noop":
            print(f"{'':62}↳ {_short(r['summary'], 64)}")
    print(f"\n{len(rows)} turn(s).  '*' = current accepted baseline.  "
          f"Deep dump: vibecomfy_debug.py turn <session> [<turn>]")
    print(f"Raw per-turn files: {SESS_ROOT}/<session>/turns/<turn>/")

def cmd_turn(args):
    configure_from_env()
    rows = [r for r in _iter_turns() if r["session"].startswith(args.session)]
    if args.turn:
        rows = [r for r in rows if r["turn"] == args.turn or r["turn"] == args.turn.zfill(4)]
    if not rows:
        print(f"(no matching turn for session={args.session} turn={args.turn})"); return
    r = sorted(rows, key=lambda x: x["mtime"])[-1]
    tdir = r["dir"]
    if args.json:
        out = dict(r)
        out["faithful"] = _faithful_diff(_load(os.path.join(tdir, "original.ui.json")),
                                         _load(os.path.join(tdir, "candidate.ui.json")))
        print(json.dumps(out, indent=2, default=str)); return
    print(f"── session {r['session']}  turn {r['turn']}  ({_ts(r['mtime'])}) ──")
    print(f"  query     : {r['task']}")
    print(f"  route     : {r['route']}    protocol: {r['protocol']}")
    print(f"  outcome   : {r['outcome']}   (lifecycle={r['lifecycle']}, baseline={r['is_baseline']})")
    print(f"  gates     : fidelity={r['fid']} state_match={r['state_match']} "
          f"queue_validate={r['queue_validate']}  canvas_apply_allowed={r['canvas_apply']} "
          f"queue_allowed={r['queue_allowed']}")
    if r["live_token"]:
        print(f"  live token: {r['live_token']}   (live:REV:hash — REV drift drives StaleStateMismatch)")
    print(f"  summary   : {_short(r['summary'], 400)}")
    # faithful diff
    diff = _faithful_diff(_load(os.path.join(tdir, "original.ui.json")),
                          _load(os.path.join(tdir, "candidate.ui.json")))
    if diff:
        print(f"  faithful  : changed={diff['changed']} added={diff['added']}"
              f"{' '+str(diff['node_types']) if diff['node_types'] else ''} "
              f"removed={diff['removed']}  ({diff['before_nodes']}→{diff['candidate_nodes']} nodes)")
    # the agent's actual batch statements + per-statement results
    if args.batch or True:
        aud = _load(os.path.join(tdir, "audit", "audit.json"))
        batch, report = _extract_batch(aud)
        if batch:
            print("  ── agent batch statements ──")
            for ln in batch.splitlines():
                print(f"    | {ln}")
        if report:
            print("  ── per-statement report ──")
            for ln in report.splitlines():
                print(f"    {ln}")
    print(f"  files     : {tdir}/")
    print("              request.json response.json candidate.ui.json original.ui.json")
    print("              model_request.json model_response.json audit/audit.json before.py after.py")

def _extract_batch(aud):
    if not isinstance(aud, dict):
        return None, None
    batch = report = None
    def walk(o):
        nonlocal batch, report
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "batch" and isinstance(v, str) and batch is None:
                    batch = v
                if k == "report" and isinstance(v, str) and report is None:
                    report = v
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(aud)
    return batch, report

def cmd_stats(args):
    configure_from_env()
    rows = list(_iter_turns())
    if not rows:
        print("(no turns)"); return
    from collections import Counter
    total = len(rows)
    applied = sum(1 for r in rows if r["lifecycle"] == "accepted")
    candidates = sum(1 for r in rows if r["ok"] is True)
    fails = Counter(r["kind"] for r in rows if r["ok"] is False and r["kind"])
    clarifies = sum(1 for r in rows if r["outcome"] == "clarify/noop")
    fid_ok = sum(1 for r in rows if r["fid"] is True)
    sessions = len({r["session"] for r in rows})
    out = {
        "sessions": sessions, "turns": total,
        "applied_to_canvas": applied, "candidates_ok": candidates,
        "clarify_or_noop": clarifies, "fidelity_ok": fid_ok,
        "failures_by_kind": dict(fails),
    }
    if args.json:
        print(json.dumps(out, indent=2)); return
    print(f"sessions            : {sessions}")
    print(f"total turns         : {total}")
    print(f"candidates (ok)     : {candidates}")
    print(f"applied to canvas   : {applied}")
    print(f"clarify / noop      : {clarifies}")
    print(f"fidelity_ok turns   : {fid_ok}")
    print(f"failures by kind    :")
    for k, n in fails.most_common():
        print(f"    {n:4}  {k}")
    if not fails:
        print("    (none)")

def _listener_pid():
    import subprocess
    try:
        return subprocess.run(["lsof", "-nP", f"-iTCP:{PORT}", "-sTCP:LISTEN", "-t"],
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception as e:
        return None, str(e)

def _fetch_runtime_status():
    url = f"http://127.0.0.1:{PORT}/vibecomfy/agent/status"
    try:
        try:
            import httpx
        except Exception:
            httpx = None
        if httpx is not None:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.json(), None
        with urllib.request.urlopen(url, timeout=5) as f:
            return json.load(f), None
    except Exception as e:
        return None, str(e)

def _env_flags():
    flags = ["VIBECOMFY_AGENT_EDIT_V2", "VIBECOMFY_AGENT_EDIT_IDENTITY",
             "VIBECOMFY_AGENT_EDIT_BATCH_REPL", "VIBECOMFY_DEEPSEEK_MODEL"]
    return {f: os.environ.get(f, "-") for f in flags}

def _truthy(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    return str(value).strip().lower() in {"1", "true", "yes", "on", "present", "available"}

def _runtime_live_flags(runtime):
    if not isinstance(runtime, dict):
        return {}
    route_available = (
        runtime.get("route_available")
        if "route_available" in runtime
        else runtime.get("route") is not None
    )
    credential_present = (
        runtime.get("credential_present")
        if "credential_present" in runtime
        else runtime.get("credentials_present", runtime.get("deepseek_key_present"))
    )
    return {
        "route_available": _truthy(route_available),
        "provider_available": _truthy(runtime.get("provider_available")),
        "credential_present": _truthy(credential_present),
        "agent_edit_v2": runtime.get("AGENT_EDIT_V2", runtime.get("agent_edit_v2")),
        "identity": runtime.get("IDENTITY", runtime.get("identity")),
        "batch_repl": runtime.get("BATCH_REPL", runtime.get("batch_repl")),
    }

def _log_tail():
    for name in ("comfy_edit_validate.log", "comfyui_8190.log"):
        p = os.path.join(RUNS_DIR, name)
        if os.path.exists(p):
            with open(p, errors="replace") as f:
                return {"name": name, "path": p, "lines": [ln.rstrip()[:140] for ln in f.readlines()[-12:]]}
    return None

def status_snapshot():
    configure_from_env()
    listener = _listener_pid()
    if isinstance(listener, tuple):
        pid, listener_error = listener
    else:
        pid, listener_error = listener, None
    runtime, runtime_error = _fetch_runtime_status()
    env = _env_flags()
    return {
        "comfy_dir": COMFY_DIR,
        "sessions": SESS_ROOT,
        "port": PORT,
        "listener": {"pid": pid or None, "error": listener_error},
        "runtime": runtime,
        "runtime_error": runtime_error,
        "live_flags": _runtime_live_flags(runtime),
        "env_flags": env,
        "deepseek_key_present": bool(os.environ.get("DEEPSEEK_API_KEY")),
        "log_tail": _log_tail(),
    }

def cmd_status(args):
    snap = status_snapshot()
    if args.json:
        print(json.dumps(snap, indent=2, default=str)); return
    print(f"ComfyUI dir : {COMFY_DIR}")
    print(f"sessions    : {SESS_ROOT}")
    if snap["listener"]["error"]:
        print(f":{PORT} listener: (lsof failed: {snap['listener']['error']})")
    else:
        pid = snap["listener"]["pid"] or ""
        print(f":{PORT} listener: {'pid '+pid if pid else 'NOT LISTENING'}")
    d = snap["runtime"]
    if isinstance(d, dict):
        print(f"runtime     : ok={d.get('ok')} backend={d.get('backend')} "
              f"route={d.get('route')} provider_available={d.get('provider_available')}")
        live = snap["live_flags"]
        if live:
            print("live flags  : " + ", ".join(f"{k}={v}" for k, v in live.items()))
    else:
        print(f"runtime     : (unreachable: {snap['runtime_error']})")
    print("env flags   : " + ", ".join(f"{f}={v}" for f, v in snap["env_flags"].items()))
    print(f"deepseek key: {'present' if os.environ.get('DEEPSEEK_API_KEY') else 'not in env (may be in ~/.hermes/.env)'}")
    tail = snap["log_tail"]
    if tail:
        print(f"\n── tail {tail['name']} ──")
        for ln in tail["lines"]:
            print("  " + ln)

def cmd_bundle(args):
    configure_from_env()
    out = args.out or os.path.join("/tmp", f"vibecomfy_debug_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(out, exist_ok=True)
    # 1) sessions (copy whole tree)
    if os.path.isdir(SESS_ROOT):
        shutil.copytree(SESS_ROOT, os.path.join(out, "editor_sessions"), dirs_exist_ok=True)
    # 2) recent run logs
    logdir = os.path.join(out, "run_logs"); os.makedirs(logdir, exist_ok=True)
    for p in sorted(glob.glob(os.path.join(RUNS_DIR, "*.log")) + glob.glob(os.path.join(RUNS_DIR, "*.out")),
                    key=_mtime, reverse=True)[:8]:
        try:
            shutil.copy2(p, logdir)
        except Exception:
            pass
    # 3) summary + stats snapshot
    rows = sorted(_iter_turns(), key=lambda r: r["mtime"])
    with open(os.path.join(out, "usage_summary.json"), "w") as f:
        json.dump(rows, f, indent=2, default=str)
    # 4) tarball
    tar = out.rstrip("/") + ".tar.gz"
    with tarfile.open(tar, "w:gz") as t:
        t.add(out, arcname=os.path.basename(out))
    print(f"bundle dir : {out}")
    print(f"tarball    : {tar}")
    print(f"contents   : editor_sessions/ ({len(rows)} turns), run_logs/, usage_summary.json")
    print("Share the .tar.gz for full triage.")

def add_debug_subcommands(sub, *, per_subcommand_json=False):
    def add_json(parser):
        if per_subcommand_json:
            parser.add_argument("--json", action="store_true", help="machine-readable output")
        return parser

    pl = sub.add_parser("log", help="table of all turns (default)")
    add_json(pl)
    pl.add_argument("--tail", type=int, default=0); pl.add_argument("--failed", action="store_true")
    pl.add_argument("--session", default=None)

    pt = sub.add_parser("turn", help="deep dump of one turn")
    add_json(pt)
    pt.add_argument("session"); pt.add_argument("turn", nargs="?", default=None)
    pt.add_argument("--batch", action="store_true"); pt.add_argument("--diff", action="store_true")

    add_json(sub.add_parser("stats", help="aggregate usage stats"))
    add_json(sub.add_parser("status", help="live runtime + env"))
    pb = sub.add_parser("bundle", help="export everything for sharing")
    pb.add_argument("--out", default=None)
    ptl = sub.add_parser("tail", help="recent N turns")
    add_json(ptl)
    ptl.add_argument("n", nargs="?", type=int, default=15)

def dispatch(args):
    if not hasattr(args, "json"):
        args.json = False

    if args.cmd in (None, "log"):
        if args.cmd is None:
            args.tail = 0; args.failed = False; args.session = None
        cmd_log(args)
    elif args.cmd == "tail":
        args.tail = args.n; args.failed = False; args.session = None; cmd_log(args)
    elif args.cmd == "turn":
        cmd_turn(args)
    elif args.cmd == "stats":
        cmd_stats(args)
    elif args.cmd == "status":
        cmd_status(args)
    elif args.cmd == "bundle":
        cmd_bundle(args)
    return 0

def main(argv=None):
    p = argparse.ArgumentParser(prog="vibecomfy_debug", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", action="store_true", help="machine-readable output")
    sub = p.add_subparsers(dest="cmd")
    add_debug_subcommands(sub)
    a = p.parse_args(argv)
    return dispatch(a)

if __name__ == "__main__":
    raise SystemExit(main())
