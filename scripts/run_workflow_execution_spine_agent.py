#!/usr/bin/env python3
"""Run one routed execution-spine card and persist a typed receipt.

The wrapper is deliberately dependency-free. It is the sole post-bootstrap
launch surface, so all policy checks happen before the child launcher starts.

Evidence-role briefs must tell the agent to record only its own wrapper PID
and wrapper start timestamp from ``active-allowances.json``, plus the receipt
path. They must not ask the agent to record its own ``end_ts`` or receipt
digest. Dirty-state exception lists must enumerate
``docs/plans/workflow-execution-spine-consolidation-evidence/receipts/``,
``docs/plans/._*`` artifacts, and the known pre-existing documents:
``docs/plans/codebase-structural-cleanup-execution-log-2026-08-20.md``,
``docs/plans/goal-codebase-structural-cleanup-2026-08-20.md``, and
``docs/plans/._goal-workflow-execution-spine-consolidation-2026-08-20.md``.

Evidence briefs also follow validator-enforced digest-pin discipline. An
evidence agent that appends to the execution log must refresh
``manifest.tasks[5].recovery_note.sha256`` to the new log digest. An agent
that edits ``test-shards.json`` must refresh every manifest pin referencing
it: ``tasks[5].evidence_links[*].sha256`` and
``tasks[6].shard_integrity.sha256``. Every evidence brief must require the
read-only validator and prove exit 0 on the committed state before finishing.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import fnmatch
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import re
import tempfile
import time
from collections.abc import Iterable
from pathlib import Path

HERMES_LAUNCHER = "/root/.codex/skills/subagent-launcher/launch_hermes_agent.py"
STALE_SECONDS = 6 * 60 * 60
DEAD_PID_GRACE_SECONDS = 60
ROUTE_LAUNCHERS = {
    "codex:gpt-5.6-luna": (HERMES_LAUNCHER, "openrouter/meta/muse-spark-1.2-contributor"),
    "grok-4.6": (HERMES_LAUNCHER, "openrouter/meta/muse-spark-1.2-contributor"),
    "stealth/ox-alpha": (HERMES_LAUNCHER, "stealth/ox-alpha:max"),
    "codex:gpt-5.6-sol": (HERMES_LAUNCHER, "codex:gpt-5.6-sol"),
    "ox-alpha": (HERMES_LAUNCHER, "stealth/ox-alpha:max"),
    "muse-spark": (HERMES_LAUNCHER, "openrouter/meta/muse-spark-1.2-contributor"),
}
GATE_BY_TASK = {
    "T0.0": "G0", "T0.1": "G0", "T0.2": "G0", "T0.3": "G0",
    **{f"T{i}.{j}": f"G{i}" for i, count in ((1, 2), (2, 3), (3, 2), (4, 3), (5, 5), (6, 3), (7, 3)) for j in range(1, count + 1)},
}


class WrapperError(RuntimeError):
    """A typed pre-launch or post-launch policy violation."""
_EVIDENCE_BRIEF_ITEM = (
    r"(?:end[_\s-]*ts|end\s+timestamp|end\s+time|"
    r"receipt\s+(?:digest|hash)|result[_\s-]*sha256)"
)
_EVIDENCE_BRIEF_DIRECTIVE = re.compile(
    r"\b(?:record|write|populate|set|include|report|provide|capture|"
    r"calculate|compute|supply|document|add)\b"
    rf"[^.!?;\n]{{0,100}}\b{_EVIDENCE_BRIEF_ITEM}\b",
    re.IGNORECASE,
)
_EVIDENCE_BRIEF_OWN_FIELD = (
    rf"(?:\b(?:your\s+own|its\s+own|(?:the\s+)?agent['’]s\s+own|"
    rf"this\s+run['’]s)\s+{_EVIDENCE_BRIEF_ITEM}\b)"
)
_EVIDENCE_BRIEF_REQUIREMENT = re.compile(
    rf"(?:{_EVIDENCE_BRIEF_OWN_FIELD}[^.!?;\n]{{0,100}}\b"
    rf"(?:is\s+required|is\s+mandatory|must\s+(?:contain|include)|"
    rf"needed\s+in\s+(?:the\s+)?result|expected\s+in\s+(?:the\s+)?result)\b|"
    rf"\b(?:is\s+required|is\s+mandatory|must\s+(?:contain|include)|"
    rf"needed\s+in\s+(?:the\s+)?result|expected\s+in\s+(?:the\s+)?result)\b"
    rf"[^.!?;\n]{{0,100}}{_EVIDENCE_BRIEF_OWN_FIELD})",
    re.IGNORECASE,
)
_EVIDENCE_BRIEF_NEGATION = re.compile(
    r"\b(?:do\s+not|don't|must\s+not|should\s+not|never|"
    r"not\s+(?:ask|instruct|tell|require|request))\b",
    re.IGNORECASE,
)
_EVIDENCE_BRIEF_WRAPPER_EXPLANATION = re.compile(
    r"\bwrapper\b[^.!?;\n]{0,120}\b(?:writes|records|populates|sets|"
    r"adds|computes|persists)\b[^.!?;\n]{0,80}\b(?:post[-\s]?exit|"
    r"after\s+(?:the\s+)?child|after\s+exit)\b",
    re.IGNORECASE,
)


def _evidence_brief_self_referential(brief_text: str) -> bool:
    """Return whether an evidence brief directs the agent to record a post-exit field."""
    for clause in re.split(r"[\n.!?;]+", brief_text):
        clause = clause.strip()
        if not clause or _EVIDENCE_BRIEF_NEGATION.search(clause):
            continue
        if _EVIDENCE_BRIEF_WRAPPER_EXPLANATION.search(clause):
            continue
        if (
            _EVIDENCE_BRIEF_DIRECTIVE.search(clause)
            or _EVIDENCE_BRIEF_REQUIREMENT.search(clause)
        ):
            return True
    return False


def _evidence_brief_guard(args: argparse.Namespace) -> None:
    """Reject self-referential evidence instructions before registry mutation."""
    if str(args.role).casefold() != "evidence":
        return
    try:
        brief_text = args.query_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise WrapperError(f"EVIDENCE_BRIEF_INVALID: cannot read query file: {args.query_file}") from exc
    if _evidence_brief_self_referential(brief_text):
        raise WrapperError(
            "EVIDENCE_BRIEF_SELF_REFERENTIAL: evidence briefs must not instruct "
            "the agent to record its own end_ts or receipt digest"
        )



def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WrapperError(f"ALLOWANCE_INVALID: missing {label}: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise WrapperError(f"ALLOWANCE_INVALID: invalid {label}: {path}") from exc


#: §29a REDACT-WRITEPATH: credential material must never reach committable
#: evidence. Patterns run in order so an sk-or-v1 token embedded in a VAR=...
#: pair collapses to a fully redacted value, and every replacement is chosen
#: so re-applying _redact_secrets is a fixed point ([REDACTED] output never
#: re-matches). Hex digests (sha256 ...) contain none of these anchors and
#: pass through untouched. Substitution runs on the STRUCTURED payload before
#: serialization: decoded strings carry no JSON escape sequences, so greedy
#: \S+ value classes cannot eat syntax that does not exist at that layer.
#:
#: T29A-REVISION-2: [REDACTED] is canonical ONLY when followed by whitespace
#: or end-of-string on decoded leaves (\[REDACTED\](?=\s|$)). Suffixed forms
#: such as [REDACTED]-suffix or [REDACTED]<suffix> are live material: the
#: negative lookahead lets them match so they re-wash to the canonical form
#: instead of staying exempt.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-or-v1-[A-Za-z0-9_-]{16,}"), "sk-or-v1-[REDACTED]"),
    (re.compile(r"(OPENROUTER_API_KEY|DEEPSEEK_API_KEY|OPENAI_API_KEY)=(?!\[REDACTED\](?=\s|$))\S+"), r"\g<1>=[REDACTED]"),
    (re.compile(r"Authorization:\s*Bearer\s+(?!\[REDACTED\](?=\s|$))\S+", re.IGNORECASE), "Authorization: Bearer [REDACTED]"),
)


def _redact_secrets(value: Any) -> Any:
    """Recursively redact every str leaf of ``value`` (dict keys and values).

    Non-str leaves pass through untouched. Idempotent fixed point. Runs on the
    structured payload BEFORE _json_write serializes it, so a secret value with
    an embedded quote can never desynchronize escape handling.

    T29A-REVISION-2: dicts are rebuilt imperatively; when two distinct source
    keys normalize to one redacted key, insertion fails closed with the typed
    CREDENTIAL_REDACTION_KEY_COLLISION WrapperError, which deliberately carries
    no original key, normalized key, value, or structural-path material.
    """
    if isinstance(value, str):
        return _redact_secret_text(value)
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            out_key = _redact_secret_text(key) if isinstance(key, str) else key
            if out_key in redacted:
                raise WrapperError("CREDENTIAL_REDACTION_KEY_COLLISION: distinct mapping keys normalize to one redacted key")
            redacted[out_key] = _redact_secrets(item)
        return redacted
    if isinstance(value, list):
        return [_redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_secrets(item) for item in value)
    return value


def _redact_secret_text(text: str) -> str:
    """Leaf substitution: replace live-format credentials with [REDACTED]."""
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _json_write(path: Path, value: Any) -> None:
    #: T29A-REVISION-2: the COMPLETE structural pass runs before any
    #: filesystem effect, so a collision leaves an existing target
    #: byte-identical, a nonexistent target absent, and no temp residue.
    payload = json.dumps(_redact_secrets(value), indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def _registry_paths(evidence_dir: Path) -> tuple[Path, Path]:
    return evidence_dir / "active-allowances.json", evidence_dir / ".active-allowances.lock"


def _path_key(value: str, worktree: Path) -> str:
    path = Path(value)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(worktree.resolve()).as_posix()
        except ValueError:
            return path.resolve().as_posix()
    return path.as_posix().lstrip("./")


def _allowance_paths(allowance: dict[str, Any], worktree: Path) -> tuple[list[str], list[str]]:
    allowed = allowance.get("allowed")
    forbidden = allowance.get("forbidden", [])
    if not isinstance(allowed, list) or not all(isinstance(item, str) and item for item in allowed):
        raise WrapperError("ALLOWANCE_INVALID: allowed must be a non-empty list of paths")
    if not isinstance(forbidden, list) or not all(isinstance(item, str) and item for item in forbidden):
        raise WrapperError("ALLOWANCE_INVALID: forbidden must be a list of paths")
    return [_path_key(item, worktree) for item in allowed], [_path_key(item, worktree) for item in forbidden]




def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _receipt_files(evidence_dir: Path) -> Iterable[Path]:
    if not evidence_dir.exists():
        return ()
    return sorted(evidence_dir.rglob("*-receipt.json"))


def _prior_task_receipt(evidence_dir: Path, task_id: str) -> Path | None:
    for path in _receipt_files(evidence_dir):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("task_id") == task_id or data.get("task") == task_id:
            return path
    return None


def _prior_singleton_success(evidence_dir: Path, label: str) -> Path | None:
    if "broad_suite_once_v1" not in label:
        return None
    for path in _receipt_files(evidence_dir):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("label") == label and data.get("exit") == 0:
            return path
    return None


def _workspace_root(project_dir: Path, evidence_dir: Path) -> Path:
    configured = os.environ.get("VCSPINE_EXECUTION_ROOT")
    if configured:
        return Path(configured).resolve()
    # A normal evidence directory lives inside the repository, while card
    # worktrees live beside it. Resolve the repository root first so an
    # in-repository evidence path does not make the worktree look external.
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=project_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve().parent
    return evidence_dir.resolve().parent


#: WRAPPER-OVERLAP-NARROW-R2 F-a/F-b support.
def _same_worktree(left: str, right: str) -> bool:
    """Whether two registry worktree strings denote one resolved directory."""
    try:
        return Path(left).resolve() == Path(right).resolve()
    except OSError:
        return left == right


def _star_fragment(pattern: str) -> tuple[str, str] | None:
    """Reduce a star-carrying glob to ``(prefix, suffix)`` around its single
    ``*`` (runs of ``*``/``**`` collapse to one star, matching fnmatch
    semantics where both translate to ``.*``); plain literals and undecidable
    fragments (``?``, ``[...]``, multiple independent stars) return None.

    A literal must NOT be modeled as ``(literal, "")``: that fragment denotes
    ``literal.*``, not the singleton ``{literal}`` (R2 re-review finding).
    """
    collapsed = re.sub(r"\*{2,}", "*", pattern)
    if "?" in collapsed or "[" in collapsed:
        return None
    if collapsed.count("*") != 1:
        return None
    prefix, _, suffix = collapsed.partition("*")
    return prefix, suffix


def _literal_matches_fragment(literal: str, prefix: str, suffix: str) -> bool:
    """Exact test of ``literal`` against the ``prefix.*suffix`` language."""
    return (
        literal.startswith(prefix)
        and literal.endswith(suffix)
        and len(literal) >= len(prefix) + len(suffix)
    )


def _patterns_may_intersect(pat_a: str, pat_b: str) -> bool:
    """Conservative FAIL-CLOSED decision on whether two allowance globs can
    both match some literal path (WRAPPER-OVERLAP-NARROW-R2 F-a).

    Exact where decidable. Two wildcard-free patterns intersect iff equal.
    Literal vs single-star glob uses the exact membership test above.
    Two single-star globs intersect iff one prefix is a prefix of the other
    AND one suffix is a suffix of the other (witness:
    ``longer_prefix + longer_suffix``; both sides carry a real star, so the
    middle absorbs any gap). This decides crossings like ``docs/*.md`` vs
    ``docs/x*`` that plain fnmatch cross-checks miss, while keeping pairs
    like ``.../intent_judge.py`` vs ``.../*.json`` correctly disjoint.
    ANY UNDECIDABLE CROSSING returns True: patterns carrying ``?``,
    ``[...]`` classes, or multiple independent stars are not analyzed, so
    admission serializes rather than risking unsound parallel approval.
    """
    if pat_a == pat_b:
        return True
    if not any(ch in pat_a + pat_b for ch in "*?["):
        return False
    lit_a = not any(ch in pat_a for ch in "*?[")
    lit_b = not any(ch in pat_b for ch in "*?[")
    if lit_a != lit_b:
        literal, glob = (pat_a, pat_b) if lit_a else (pat_b, pat_a)
        frag = _star_fragment(glob)
        if frag is None:
            return True
        return _literal_matches_fragment(literal, *frag)
    if lit_a:
        return False  # both literal here implies distinct (equal handled above)
    frag_a = _star_fragment(pat_a)
    frag_b = _star_fragment(pat_b)
    if frag_a is None or frag_b is None:
        return True
    prefixes_compatible = frag_a[0].startswith(frag_b[0]) or frag_b[0].startswith(frag_a[0])
    suffixes_compatible = frag_a[1].endswith(frag_b[1]) or frag_b[1].endswith(frag_a[1])
    return prefixes_compatible and suffixes_compatible


def _allowances_overlap(current: dict[str, Any], other: dict[str, Any], same_worktree: bool = False) -> bool:
    """Overlap policy (WRAPPER-OVERLAP-NARROW-R2 F-b): read-only sides (empty
    ``allowed``, the §21.4 orchestrator convention) never overlap; a
    same-worktree pair whose BOTH allowed lists are non-empty overlaps
    unconditionally -- whole-worktree snapshots cannot attribute writes
    between concurrent children, so mutually-mutating pairs serialize;
    cross-worktree pairs fall to conservative pattern intersection.
    """
    current_allowed = [str(a) for a in current.get("allowed", [])]
    other_allowed = [str(b) for b in other.get("allowed", [])]
    if not current_allowed or not other_allowed:
        return False
    if same_worktree:
        return True
    return any(_patterns_may_intersect(a, b) for a in current_allowed for b in other_allowed)


#: Descriptor holding this process's registry-guard critical-section lock, or
#: None. Single-threaded wrapper invariant: ``_registry_release`` reuses this
#: descriptor when an interrupt lands inside the critical section instead of
#: blocking on a second flock acquisition, which would deadlock the handler.
_ACTIVE_REGISTRY_LOCK: Any = None


def _registry_guard(evidence_dir: Path, task_id: str, allowance_file: Path, worktree: Path, allowed: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    global _ACTIVE_REGISTRY_LOCK
    evidence_dir.mkdir(parents=True, exist_ok=True)
    registry_path, lock_path = _registry_paths(evidence_dir)
    lock_path.touch(exist_ok=True)
    lock_handle = lock_path.open("r+")
    _ACTIVE_REGISTRY_LOCK = lock_handle
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
    try:
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {}
        except (OSError, json.JSONDecodeError) as exc:
            raise WrapperError("ALLOWANCE_REGISTRY_INVALID: active-allowances.json is not valid JSON") from exc
        if not isinstance(registry, dict):
            raise WrapperError("ALLOWANCE_REGISTRY_INVALID: active-allowances.json must be an object")
        now = time.time()
        stale: list[str] = []
        dead_pid_stale = False
        long_threshold_stale = False
        for active_id, entry in list(registry.items()):
            if not isinstance(entry, dict):
                continue
            started = entry.get("start_ts_epoch")
            pid = entry.get("pid")
            if not isinstance(started, (int, float)):
                continue
            age = now - started
            if isinstance(pid, int):
                pid_alive = _pid_exists(pid)
                if not pid_alive and age > DEAD_PID_GRACE_SECONDS:
                    stale.append(active_id)
                    dead_pid_stale = True
                    del registry[active_id]
                continue
            if age > STALE_SECONDS:
                stale.append(active_id)
                long_threshold_stale = True
                del registry[active_id]
        if stale:
            note = evidence_dir / "stale-allowance-cleared.json"
            classes = []
            if dead_pid_stale:
                classes.append("dead-PID grace")
            if long_threshold_stale:
                classes.append("six-hour missing/non-int PID")
            _json_write(note, {
                "cleared_task_ids": stale,
                "cleared_ts": utc_now(),
                "reason": f"{' and '.join(classes)} allowance entries cleared",
            })
        # WRAPPER-OVERLAP-NARROW-R2 F-c: an already-active task_id is refused
        # BEFORE overlap evaluation and before the candidate write, so a second
        # dispatch cannot clobber the live entry (either side's release would
        # then unregister the survivor). Entries just swept above do NOT count.
        if task_id in registry:
            active_entry = registry[task_id]
            detail = ""
            if isinstance(active_entry, dict):
                detail = f" (pid {active_entry.get('pid')}, started {active_entry.get('start_ts')})"
            raise WrapperError(
                f"TASK_ALREADY_ACTIVE: {task_id}{detail} is already registered as an active dispatch"
            )
        candidate = {"task_id": task_id, "allowance_file": str(allowance_file), "worktree": str(worktree), "start_ts": utc_now(), "start_ts_epoch": now, "pid": os.getpid(), "allowed": allowed}
        candidate_worktree = str(worktree)
        for active_id, entry in registry.items():
            if isinstance(entry, dict) and _allowances_overlap(
                candidate,
                entry,
                same_worktree=_same_worktree(str(entry.get("worktree", "")), candidate_worktree),
            ):
                raise WrapperError(f"ALLOWANCE_OVERLAP: {task_id} overlaps active task {active_id}")
        registry[task_id] = candidate
        _json_write(registry_path, registry)
        # H3 fix: the critical section ends once the candidate entry is durably
        # written. The lock is NOT held for the child runtime, so other wrappers
        # can register allowances and the dead-PID sweep can fire while this
        # dispatch runs.
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        lock_handle.close()
        _ACTIVE_REGISTRY_LOCK = None
        return registry, candidate
    except Exception:
        _ACTIVE_REGISTRY_LOCK = None
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        lock_handle.close()
        raise


def _registry_release(evidence_dir: Path, task_id: str) -> None:
    """Remove one task entry from the registry under an exclusive lock.

    With the guard's critical section shortened (H3 fix), the lock is normally
    free here, so this read-modify-write MUST take LOCK_EX itself; an unlocked
    RMW loses concurrent deletions and leaves zombie allowances behind.
    """
    registry_path, lock_path = _registry_paths(evidence_dir)
    held = _ACTIVE_REGISTRY_LOCK
    if held is not None and not getattr(held, "closed", True):
        handle = held
    else:
        lock_path.touch(exist_ok=True)
        handle = lock_path.open("r+")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    try:
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {}
        except (OSError, json.JSONDecodeError):
            registry = {}
        if isinstance(registry, dict):
            registry.pop(task_id, None)
            _json_write(registry_path, registry)
    finally:
        if handle is not held:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _git(project_dir: Path, args: list[str]) -> str:
    result = subprocess.run(["git", *args], cwd=project_dir, text=True, capture_output=True, check=False)
    return result.stdout.strip()



def _snapshot_path_is_evidence(project_dir: Path, evidence_dir: Path, relative: str) -> bool:
    path = Path(os.path.abspath(project_dir / relative))
    try:
        path.relative_to(Path(os.path.abspath(evidence_dir)))
        return True
    except ValueError:
        return False


def _path_state(path: Path) -> tuple[str, int, str] | None:
    try:
        stat = path.lstat()
    except FileNotFoundError:
        return None
    mode = stat.st_mode & 0o7777
    if path.is_symlink():
        return "symlink", mode, sha256_bytes(os.fsencode(os.readlink(path)))
    if path.is_file():
        digest = hashlib.sha256()
        try:
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        except FileNotFoundError:
            return None
        return "file", mode, digest.hexdigest()
    if path.is_dir():
        return "directory", mode, ""
    return "other", mode, ""


def _capture_ignore_baseline(project_dir: Path) -> tempfile.TemporaryDirectory[str]:
    """Copy repository ignore files so post-child checks use pre-child rules."""
    root = project_dir.resolve()
    probe = tempfile.TemporaryDirectory(prefix="vcspine-ignore-")
    probe_root = Path(probe.name)
    subprocess.run(["git", "init", "-q"], cwd=probe_root, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for directory, directories, files in os.walk(root, topdown=True, followlinks=False):
        directories[:] = sorted(name for name in directories if name != ".git")
        if ".gitignore" not in files:
            continue
        source = Path(directory) / ".gitignore"
        relative = source.relative_to(root)
        target = probe_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    source_exclude = root / ".git" / "info" / "exclude"
    target_exclude = probe_root / ".git" / "info" / "exclude"
    target_exclude.write_bytes(source_exclude.read_bytes() if source_exclude.is_file() else b"")
    return probe


def _baseline_ignored(probe_root: Path, paths: list[str]) -> set[str]:
    if not paths:
        return set()
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin", "-z"],
        cwd=probe_root,
        input=b"\0".join(os.fsencode(path) for path in paths),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return {os.fsdecode(path).rstrip("/") for path in result.stdout.split(b"\0") if path}


def _repo_snapshot(project_dir: Path, evidence_dir: Path, ignore_probe: Path | None = None) -> dict[str, tuple[str, int, str]]:
    """Capture worktree paths, applying ignore rules from before the child ran."""
    root = project_dir.resolve()
    snapshot: list[tuple[str, tuple[str, int, str]]] = []
    for directory, directories, files in os.walk(root, topdown=True, followlinks=False):
        directories[:] = sorted(directories)
        files = sorted(files)
        for name in directories + files:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if relative == ".git" or relative.startswith(".git/"):
                if name in directories:
                    directories.remove(name)
                continue
            if _snapshot_path_is_evidence(root, evidence_dir, relative):
                if name in directories:
                    directories.remove(name)
                continue
            state = _path_state(path)
            if state is not None:
                snapshot.append((relative, state))
    tracked = set(_git(root, ["ls-files"]).splitlines())
    ignored = _baseline_ignored(
        ignore_probe,
        [relative + "/" if state[0] == "directory" else relative for relative, state in snapshot],
    ) if ignore_probe else set()
    return {
        relative: state
        for relative, state in snapshot
        if relative in tracked or relative not in ignored
    }


def _changed_files(before: dict[str, tuple[str, int, str]], after: dict[str, tuple[str, int, str]]) -> list[str]:
    return sorted(name for name in set(before) | set(after) if before.get(name) != after.get(name))

def _git_commits(project_dir: Path, base_sha: str) -> list[str]:
    spec = f"{base_sha}..HEAD" if base_sha else "HEAD"
    return [line for line in _git(project_dir, ["log", "--format=%H", spec]).splitlines() if line]


def _resolve_base_sha(project_dir: Path, supplied: str | None) -> str:
    return supplied or _git(project_dir, ["rev-parse", "HEAD"])


def _allowed(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) or fnmatch.fnmatchcase(path, pattern.lstrip("./")) for pattern in patterns)


def _committed_files(project_dir: Path, base_sha: str) -> list[str]:
    """Files touched by commits in the dispatch window (merge-base safe).

    Enumerates the union of paths changed by any commit in
    ``merge_base(base_sha, HEAD)..HEAD`` using the same globs as pre-flight
    allowance checks. ``merge_base`` makes the range safe when ``base_sha``
    is not an ancestor of HEAD (e.g. after a rebase or unrelated history).
    """
    if not base_sha:
        return []
    merge_base = _git(project_dir, ["merge-base", base_sha, "HEAD"]).strip()
    if not merge_base:
        merge_base = base_sha.strip()
    head = _git(project_dir, ["rev-parse", "HEAD"]).strip()
    if not head or not merge_base or merge_base == head:
        # No new commits in window.
        # Still handle the case where base_sha == head but file was committed
        # via checking diff; if head==merge_base then window is empty.
        return []
    # Union of files across all commits in window (fail-closed vs net diff).
    log_output = _git(project_dir, ["log", "--name-only", "--pretty=format:", f"{merge_base}..HEAD", "--"])
    files: set[str] = {line.strip() for line in log_output.splitlines() if line.strip()}
    # Augment with diff --name-only to cover merge commits / renames where
    # log --name-only may be incomplete; union is strictly more conservative.
    diff_output = _git(project_dir, ["diff", "--name-only", f"{merge_base}..HEAD", "--"])
    for line in diff_output.splitlines():
        cleaned = line.strip()
        if cleaned:
            files.add(cleaned)
    return sorted(files)


def _stop_marker(result_text: str) -> str:
    for line in result_text.splitlines():
        if line.startswith("JUDGMENT_REQUIRED:") or line.startswith("STOP:"):
            return line.strip()
    return ""


def _receipt_is_interrupted(path: Path) -> bool:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(value, dict) and value.get("status") == "interrupted"


def _evidence_paths(evidence_dir: Path) -> list[str]:
    if not evidence_dir.exists():
        return []
    return sorted(path.relative_to(evidence_dir).as_posix() for path in evidence_dir.rglob("*") if path.is_file())

def _finalization_failure_payload(
    task_id: str,
    cleanup_attempted: bool,
    cleanup_error: BaseException | None,
    release_error: BaseException | None,
) -> dict[str, Any]:
    def describe(error: BaseException | None) -> dict[str, str] | None:
        if error is None:
            return None
        return {
            "type": type(error).__name__,
            "message": str(error) or repr(error),
        }

    return {
        "type": "WRAPPER_FINALIZATION_FAILURE",
        "task_id": task_id,
        "cleanup": {
            "attempted": cleanup_attempted,
            "succeeded": cleanup_attempted and cleanup_error is None,
            "error": describe(cleanup_error),
        },
        "registry_release": {
            "attempted": True,
            "succeeded": release_error is None,
            "error": describe(release_error),
        },
    }


def _record_finalization_failure(
    evidence_dir: Path,
    receipt_path: Path,
    receipt: dict[str, Any] | None,
    failure: dict[str, Any],
) -> BaseException | None:
    """Retain finalization failure evidence without hiding the typed failure."""
    try:
        failure_path = evidence_dir / f"{failure['task_id']}-finalization-failure.json"
        failure["evidence_path"] = str(failure_path)
        failure["receipt"] = str(receipt_path)
        _json_write(failure_path, failure)
        if receipt is not None and not _receipt_is_interrupted(receipt_path):
            receipt["finalization"] = failure
            receipt["evidence"] = _evidence_paths(evidence_dir)
            _json_write(receipt_path, receipt)
    except Exception as exc:
        return exc
    return None


def _finalization_error_message(
    failure: dict[str, Any],
    evidence_error: BaseException | None,
) -> str:
    parts = ["FINALIZATION_FAILED"]
    cleanup_error = failure["cleanup"]["error"]
    release_error = failure["registry_release"]["error"]
    in_flight_error = failure.get("in_flight_error")
    if cleanup_error is not None:
        parts.append(f"ignore probe cleanup failed: {cleanup_error['message']}")
    if release_error is not None:
        parts.append(f"registry release failed: {release_error['message']}")
    if in_flight_error is not None:
        parts.append(f"in-flight failure: {in_flight_error['message']}")
    if evidence_error is not None:
        parts.append(f"failure evidence recording failed: {evidence_error}")
    return "; ".join(parts)






def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--model-route", required=True)
    parser.add_argument("--query-file", required=True, type=Path)
    parser.add_argument("--project-dir", required=True, type=Path)
    parser.add_argument("--allowance-file", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=7200)
    parser.add_argument("--base-sha")
    parser.add_argument("--gate")
    return parser


def _preflight(args: argparse.Namespace, allowance: dict[str, Any]) -> tuple[Path, list[str], list[str], str]:
    project_dir = args.project_dir.resolve()
    evidence_dir = args.evidence_dir.resolve()
    if not project_dir.is_dir():
        raise WrapperError(f"WORKTREE_INVALID: project directory does not exist: {project_dir}")
    root = _workspace_root(project_dir, evidence_dir)
    if not _inside(project_dir, root):
        raise WrapperError(f"WORKSPACE_ESCAPE: project directory is outside execution workspace root: {root}")
    allowed, forbidden = _allowance_paths(allowance, project_dir)
    prior = _prior_task_receipt(evidence_dir, args.task_id)
    if prior is not None:
        raise WrapperError(f"TASK_ALREADY_COMPLETED: prior receipt exists: {prior}")
    singleton = _prior_singleton_success(evidence_dir, args.label)
    if singleton is not None:
        raise WrapperError(f"SINGLETON_ALREADY_COMPLETED: {args.label} already succeeded: {singleton}")
    base_sha = _resolve_base_sha(project_dir, args.base_sha)
    return project_dir, allowed, forbidden, base_sha


def run(args: argparse.Namespace) -> int:
    if args.model_route not in ROUTE_LAUNCHERS:
        raise WrapperError(f"MODEL_ROUTE_UNSUPPORTED: {args.model_route}")
    if args.timeout <= 0:
        raise WrapperError("TIMEOUT_INVALID: timeout must be positive")
    _evidence_brief_guard(args)
    allowance = load_json(args.allowance_file, "allowance file")
    if not isinstance(allowance, dict):
        raise WrapperError("ALLOWANCE_INVALID: allowance must be an object")
    project_dir, allowed, forbidden, base_sha = _preflight(args, allowance)
    evidence_dir = args.evidence_dir.resolve()
    _registry_guard(evidence_dir, args.task_id, args.allowance_file.resolve(), project_dir, allowed)
    start_ts = utc_now()
    child_pid: int | None = None
    stdout_bytes = b""
    stderr_bytes = b""
    exit_code = 125
    ignore_probe: tempfile.TemporaryDirectory[str] | None = None
    receipt_path = evidence_dir / f"{args.task_id}-receipt.json"
    receipt: dict[str, Any] | None = None
    interrupted = False

    def handle_interrupt(signum: int, _frame: Any) -> None:
        nonlocal interrupted
        if interrupted:
            os._exit(128 + signum)
        interrupted = True
        partial_receipt = {
            "task_id": args.task_id,
            "status": "interrupted",
            "role": args.role,
            "label": args.label,
            "model_route": args.model_route,
            "gate": args.gate or GATE_BY_TASK.get(args.task_id) or (re.search(r"G\d+", args.label) or [""])[0],
            "preserved_args": {
                "task_id": args.task_id,
                "role": args.role,
                "label": args.label,
                "model_route": args.model_route,
                "gate": args.gate,
                "query_file": str(args.query_file),
                "project_dir": str(args.project_dir),
                "allowance_file": str(args.allowance_file),
                "evidence_dir": str(args.evidence_dir),
                "timeout": args.timeout,
            },
            "wrapper_pid": os.getpid(),
            "child_pid": child_pid,
            "start_ts": start_ts,
            "interrupted_ts": utc_now(),
            "signal": signal.Signals(signum).name,
        }
        try:
            _json_write(receipt_path, partial_receipt)
        except BaseException:
            pass
        try:
            _registry_release(evidence_dir, args.task_id)
        except BaseException:
            pass
        os._exit(128 + signum)

    for interrupt_signal in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal.signal(interrupt_signal, handle_interrupt)
    try:
        launcher_path, resolved_requested = ROUTE_LAUNCHERS[args.model_route]
        executable = os.environ.get("VCSPINE_FAKE_LAUNCHER", launcher_path)
        command = [
            executable,
            f"--model={resolved_requested}",
            f"--query-file={args.query_file}",
            f"--project-dir={project_dir}",
            f"--timeout={args.timeout}",
        ]
        ignore_probe = _capture_ignore_baseline(project_dir)
        before_snapshot = _repo_snapshot(project_dir, evidence_dir, Path(ignore_probe.name))
        child = subprocess.Popen(command, cwd=project_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        child_pid = child.pid
        try:
            stdout_bytes, stderr_bytes = child.communicate(timeout=args.timeout + 5)
            exit_code = child.returncode
        except subprocess.TimeoutExpired as exc:
            stdout_bytes = exc.stdout or b""
            stderr_bytes = exc.stderr or b""
            os.killpg(child.pid, signal.SIGTERM)
            try:
                tail_out, tail_err = child.communicate(timeout=5)
                stdout_bytes += tail_out or b""
                stderr_bytes += tail_err or b""
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                tail_out, tail_err = child.communicate()
                stdout_bytes += tail_out or b""
                stderr_bytes += tail_err or b""
            exit_code = 124
        sys.stdout.write(stdout_bytes.decode("utf-8", errors="replace"))
        sys.stdout.flush()
        sys.stderr.write(stderr_bytes.decode("utf-8", errors="replace"))
        sys.stderr.flush()
        end_ts = utc_now()
        result_text = stdout_bytes.decode("utf-8", errors="replace")
        changed = _changed_files(
            before_snapshot,
            _repo_snapshot(project_dir, evidence_dir, Path(ignore_probe.name)),
        )
        violation_paths = [path for path in changed if not _allowed(path, allowed) or _allowed(path, forbidden)]
        committed_files = _committed_files(project_dir, base_sha)
        committed_violations = [path for path in committed_files if not _allowed(path, allowed) or _allowed(path, forbidden)]
        all_violations = sorted(set(violation_paths) | set(committed_violations))
        stderr_text = stderr_bytes.decode("utf-8", errors="replace")
        result_stripped = result_text.strip()
        is_empty_result = result_stripped == ""
        child_failed = (exit_code != 0) or is_empty_result
        # E1 takes precedence over E2: allowance violation is policy-level.
        if all_violations:
            receipt_status = "allowance_violation"
        elif child_failed:
            receipt_status = "child_failed"
        else:
            receipt_status = "success"
        resolved_match = re.search(r"(?:^|\s)resolved=([^\s]+)", stderr_text, re.MULTILINE)
        receipt = {
            "task_id": args.task_id,
            "gate": args.gate or GATE_BY_TASK.get(args.task_id) or (re.search(r"G\d+", args.label) or [""])[0],
            "role": args.role,
            "label": args.label,
            "model_route": args.model_route,
            "launcher_command": command,
            "resolved_model": resolved_match.group(1) if resolved_match else args.model_route,
            "pid": child_pid,
            "start_ts": start_ts,
            "end_ts": end_ts,
            "exit": exit_code,
            "brief_path": str(args.query_file.resolve()),
            "brief_sha256": sha256_file(args.query_file.resolve()),
            "result_sha256": sha256_bytes(stdout_bytes),
            "base_sha": base_sha,
            "commits": _git_commits(project_dir, base_sha),
            "changed_files": changed,
            "committed_files": committed_files,
            "allowance": {"file": str(args.allowance_file.resolve()), "allowed": allowed, "forbidden": forbidden},
            "evidence": [],
            "stop_or_judgment": _stop_marker(result_text),
            "status": receipt_status,
        }
        if receipt_status == "allowance_violation":
            receipt["violating_files"] = all_violations
            receipt["committed_violations"] = committed_violations
            receipt["worktree_violations"] = violation_paths
        elif receipt_status == "child_failed":
            receipt["child_exit"] = exit_code
            receipt["child_stderr_tail"] = stderr_text[-4000:]
            receipt["empty_result"] = is_empty_result
        if all_violations:
            violation_path = evidence_dir / f"{args.task_id}-violation.json"
            _json_write(violation_path, {
                "task_id": args.task_id,
                "type": "ALLOWANCE_VIOLATION",
                "changed_files": changed,
                "committed_files": committed_files,
                "violations": all_violations,
                "committed_violations": committed_violations,
                "worktree_violations": violation_paths,
                "allowed": allowed,
                "forbidden": forbidden,
                "receipt": str(receipt_path),
            })
        if not _receipt_is_interrupted(receipt_path):
            _json_write(receipt_path, receipt)
        if not _receipt_is_interrupted(receipt_path):
            receipt["evidence"] = _evidence_paths(evidence_dir)
            _json_write(receipt_path, receipt)
        if receipt_status == "allowance_violation":
            raise WrapperError(f"ALLOWANCE_VIOLATION: changed files outside allowance: {', '.join(all_violations)}")
        if receipt_status == "child_failed":
            # Keep interrupted/death-note paths intact - already handled via _receipt_is_interrupted guards.
            tail = stderr_text[-2000:].strip()
            detail = f"child exit {exit_code}"
            if tail:
                detail += f"; stderr tail: {tail[:2000]}"
            if is_empty_result:
                detail += "; empty result"
            raise WrapperError(f"CHILD_FAILED: {detail}")
        return exit_code
    finally:
        in_flight_error = sys.exc_info()[1]
        cleanup_attempted = False
        cleanup_error: BaseException | None = None
        release_error: BaseException | None = None
        try:
            try:
                if ignore_probe is not None:
                    cleanup_attempted = True
                    ignore_probe.cleanup()
            except Exception as exc:
                cleanup_error = exc
        finally:
            try:
                _registry_release(evidence_dir, args.task_id)
            except Exception as exc:
                release_error = exc
        if cleanup_error is not None or release_error is not None:
            failure = _finalization_failure_payload(
                args.task_id,
                cleanup_attempted,
                cleanup_error,
                release_error,
            )
            if in_flight_error is not None:
                failure["in_flight_error"] = {
                    "type": type(in_flight_error).__name__,
                    "message": str(in_flight_error) or repr(in_flight_error),
                }
            evidence_error = _record_finalization_failure(evidence_dir, receipt_path, receipt, failure)
            raise WrapperError(_finalization_error_message(failure, evidence_error))

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except WrapperError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("WRAPPER_INTERRUPTED", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
