"""Execution watchdog for ComfyUI runs.

The watchdog observes a single ComfyUI run by:

1. Subscribing to Comfy's WebSocket event stream at ``ws://<server>/ws?clientId=<uuid>``
   and tracking which node is currently executing, what its progress is, and which
   nodes have already completed or were cached.
2. Polling ``/system_stats`` on a fixed interval to record VRAM samples.
3. On stop or timeout, emitting a structured ``WatchdogReport`` with a single
   one-line ``diagnosis`` chosen from a small set of heuristic branches.

The watchdog is observation-only: it never cancels, retries, or otherwise mutates
the run. If the watchdog itself raises, the failure is logged and the run is left
untouched. The whole subsystem can be disabled by setting
``VIBECOMFY_WATCHDOG=0`` in the environment.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


# --- Tunable thresholds (heuristics) -----------------------------------------
#
# These thresholds drive the diagnosis branches. They're heuristics, not
# contracts; document them alongside the branch that uses them.

# Maximum number of recent progress events kept in the report (memory cap).
MAX_PROGRESS_EVENTS: int = 256
# Maximum number of recent VRAM samples kept (5s * 120 = 10 minutes).
MAX_VRAM_SAMPLES: int = 120

# slow_node: events arriving in last N seconds, current node active > M seconds.
SLOW_RECENT_EVENT_WINDOW_S: float = 30.0
SLOW_NODE_ACTIVE_S: float = 120.0

# stalled_runtime: no events in last N seconds.
STALL_NO_EVENT_S: float = 60.0

# oom_ish: VRAM free < N bytes for >= M consecutive samples and current node
# has been active > K seconds.
OOM_FREE_BYTES: int = 500 * 1024 * 1024  # 500 MB
OOM_CONSECUTIVE_SAMPLES: int = 3
OOM_NODE_ACTIVE_S: float = 60.0

# Default poll interval for /system_stats VRAM sampling.
DEFAULT_VRAM_POLL_INTERVAL_S: float = 5.0

# How long to wait before declaring the WS attempt "never_connected" failed.
WS_INITIAL_CONNECT_TIMEOUT_S: float = 10.0


# --- Dataclasses --------------------------------------------------------------


@dataclass(slots=True)
class VramSample:
    timestamp: float
    vram_free_bytes: int | None
    vram_total_bytes: int | None


@dataclass(slots=True)
class ProgressEvent:
    timestamp: float
    node_id: str
    value: int
    max: int


@dataclass(slots=True)
class WatchdogState:
    prompt_id: str | None
    client_id: str
    server_url: str
    started_at: float
    last_event_at: float | None
    current_node_id: str | None
    current_node_class_type: str | None
    current_node_started_at: float | None
    current_node_progress: dict[str, int] | None  # {value, max} or None
    executed_node_ids: list[str]
    cached_node_ids: list[str]
    last_error: dict[str, Any] | None
    connection_state: str  # connected | reconnecting | disconnected | never_connected
    prompt_completed: bool
    stop_reason: str | None  # how stop() was reached: completed|errored|timeout|exception|manual


@dataclass(slots=True)
class WatchdogReport:
    diagnosis: str
    diagnosis_reason: str
    state: dict[str, Any]
    vram_samples: list[dict[str, Any]]
    recent_progress_events: list[dict[str, Any]]
    timestamps: dict[str, float | None]
    elapsed_seconds: float
    elapsed_in_current_node_seconds: float | None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    def header_line(self) -> str:
        """One-line greppable summary, designed to be scanned via ``tail``."""
        st = self.state
        node_id = st.get("current_node_id") or "-"
        class_type = st.get("current_node_class_type") or "-"
        prompt_id = st.get("prompt_id") or "-"
        elapsed_in_node = (
            f"{int(self.elapsed_in_current_node_seconds)}s"
            if self.elapsed_in_current_node_seconds is not None
            else "-"
        )
        vram = "-"
        if self.vram_samples:
            free = self.vram_samples[-1].get("vram_free_bytes")
            if isinstance(free, int):
                vram = f"{free / (1024**3):.1f}GB"
        return (
            f"WATCHDOG diagnosis={self.diagnosis} prompt_id={prompt_id} "
            f"last_node={node_id} ({class_type}) "
            f"elapsed_in_node={elapsed_in_node} vram_free={vram}"
        )


# --- Helpers ------------------------------------------------------------------


def _is_disabled() -> bool:
    return os.environ.get("VIBECOMFY_WATCHDOG", "1").strip() in {"0", "false", "False", "no", "off"}


def _ws_url(server_url: str, client_id: str) -> str:
    parsed = urlparse(server_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    netloc = parsed.netloc or parsed.path
    return f"{scheme}://{netloc}/ws?clientId={client_id}"


def _node_class_index(api_dict: Mapping[str, Any] | None) -> dict[str, str]:
    """Map ``node_id -> class_type`` from the submitted API graph."""
    out: dict[str, str] = {}
    if not isinstance(api_dict, Mapping):
        return out
    for node_id, payload in api_dict.items():
        if not isinstance(payload, Mapping):
            continue
        class_type = payload.get("class_type")
        if isinstance(class_type, str):
            out[str(node_id)] = class_type
    return out


def _now() -> float:
    return time.monotonic()


def _wall() -> float:
    return time.time()


# --- Watchdog -----------------------------------------------------------------


class Watchdog:
    """Observe a single Comfy run.

    Usage:
        wd = Watchdog(server_url, client_id, api_dict=api_dict)
        await wd.start()
        try:
            ...run the prompt...
        finally:
            await wd.stop(reason="completed" | "timeout" | "exception")
            report = wd.dump()
    """

    def __init__(
        self,
        *,
        server_url: str,
        client_id: str,
        api_dict: Mapping[str, Any] | None = None,
        prompt_id: str | None = None,
        vram_poll_interval_s: float = DEFAULT_VRAM_POLL_INTERVAL_S,
        timeout_s: float | None = None,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.client_id = client_id
        self.vram_poll_interval_s = max(0.5, float(vram_poll_interval_s))
        self.timeout_s = timeout_s
        self._node_class_by_id = _node_class_index(api_dict)

        self._state = WatchdogState(
            prompt_id=prompt_id,
            client_id=client_id,
            server_url=self.server_url,
            started_at=_wall(),
            last_event_at=None,
            current_node_id=None,
            current_node_class_type=None,
            current_node_started_at=None,
            current_node_progress=None,
            executed_node_ids=[],
            cached_node_ids=[],
            last_error=None,
            connection_state="never_connected",
            prompt_completed=False,
            stop_reason=None,
        )
        self._monotonic_started = _now()
        self._vram_samples: deque[VramSample] = deque(maxlen=MAX_VRAM_SAMPLES)
        self._recent_progress: deque[ProgressEvent] = deque(maxlen=MAX_PROGRESS_EVENTS)
        self._stats_responsive: bool | None = None  # last /system_stats success
        self._ws_task: asyncio.Task[None] | None = None
        self._poll_task: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()
        self._first_connect_deadline: float | None = None

    # -- lifecycle ------------------------------------------------------------

    async def start(self) -> None:
        if _is_disabled():
            logger.debug("watchdog disabled via VIBECOMFY_WATCHDOG=0; not starting")
            return
        self._first_connect_deadline = _now() + WS_INITIAL_CONNECT_TIMEOUT_S
        self._ws_task = asyncio.create_task(self._ws_loop(), name="vibecomfy-watchdog-ws")
        self._poll_task = asyncio.create_task(self._poll_loop(), name="vibecomfy-watchdog-poll")

    async def stop(self, *, reason: str | None = None) -> None:
        if self._state.stop_reason is None:
            self._state.stop_reason = reason
        self._stopped.set()
        for task in (self._ws_task, self._poll_task):
            if task is None:
                continue
            task.cancel()
        for task in (self._ws_task, self._poll_task):
            if task is None:
                continue
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:  # pragma: no cover - watchdog never crashes a run
                logger.exception("watchdog background task raised on stop")

    # -- public report --------------------------------------------------------

    def dump(self) -> WatchdogReport:
        diagnosis, reason = self._diagnose()
        elapsed = max(0.0, _now() - self._monotonic_started)
        elapsed_in_node: float | None = None
        if self._state.current_node_started_at is not None:
            elapsed_in_node = max(0.0, _now() - self._state.current_node_started_at)
        return WatchdogReport(
            diagnosis=diagnosis,
            diagnosis_reason=reason,
            state=asdict(self._state),
            vram_samples=[asdict(s) for s in self._vram_samples],
            recent_progress_events=[asdict(p) for p in self._recent_progress],
            timestamps={
                "started_wall": self._state.started_at,
                "now_wall": _wall(),
                "last_event_at_monotonic": self._state.last_event_at,
                "now_monotonic": _now(),
            },
            elapsed_seconds=elapsed,
            elapsed_in_current_node_seconds=elapsed_in_node,
        )

    # -- accessors used by tests ---------------------------------------------

    @property
    def state(self) -> WatchdogState:
        return self._state

    @property
    def vram_samples(self) -> list[VramSample]:
        return list(self._vram_samples)

    @property
    def recent_progress_events(self) -> list[ProgressEvent]:
        return list(self._recent_progress)

    # -- WebSocket loop -------------------------------------------------------

    async def _ws_loop(self) -> None:
        """Subscribe to Comfy's event stream and feed messages into the state.

        The loop never propagates exceptions out: connection errors update
        ``connection_state`` and the loop exits without crashing the run.
        """
        try:
            import websockets  # type: ignore[import-not-found]
        except ImportError:  # pragma: no cover - dep is declared in pyproject
            logger.warning("watchdog: websockets module not available; ws loop disabled")
            self._state.connection_state = "never_connected"
            return

        url = _ws_url(self.server_url, self.client_id)
        try:
            async with websockets.connect(url, max_size=2**24) as ws:
                self._state.connection_state = "connected"
                async for raw in ws:
                    if self._stopped.is_set():
                        break
                    try:
                        await self._handle_ws_message(raw)
                    except Exception:  # pragma: no cover
                        logger.exception("watchdog: error handling ws message")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # connection refused, embedded backend, etc.
            logger.debug("watchdog: ws connect/recv failed: %s", exc)
            if self._state.connection_state == "connected":
                self._state.connection_state = "disconnected"
            else:
                self._state.connection_state = "never_connected"
            return
        # Clean exit (server closed the socket) -> mark disconnected.
        if self._state.connection_state == "connected":
            self._state.connection_state = "disconnected"

    async def _handle_ws_message(self, raw: Any) -> None:
        """Parse a single WS frame and update state.

        Comfy emits JSON text frames documented in the project README.
        We accept both ``str`` and ``bytes`` payloads. Binary frames (preview
        images) are ignored; we only care about JSON status updates.
        """
        if isinstance(raw, (bytes, bytearray)):
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                return  # binary preview frame; ignore
        else:
            text = str(raw)
        try:
            msg = json.loads(text)
        except (ValueError, TypeError):
            return
        self.feed(msg)

    # -- feed (also used by tests) -------------------------------------------

    def feed(self, msg: Mapping[str, Any]) -> None:
        """Feed a parsed Comfy WS message into the state.

        Public so unit tests can drive the watchdog without a real socket.
        """
        if not isinstance(msg, Mapping):
            return
        msg_type = msg.get("type")
        data = msg.get("data") or {}
        if not isinstance(data, Mapping):
            data = {}
        self._state.last_event_at = _now()
        if self._state.connection_state == "never_connected":
            # Direct feeds (tests, or in-process bridges) imply we're connected.
            self._state.connection_state = "connected"

        if msg_type == "execution_start":
            prompt_id = data.get("prompt_id")
            if isinstance(prompt_id, str) and self._state.prompt_id is None:
                self._state.prompt_id = prompt_id
        elif msg_type == "execution_cached":
            nodes = data.get("nodes") or []
            if isinstance(nodes, Iterable):
                for node in nodes:
                    if node is None:
                        continue
                    nid = str(node)
                    if nid not in self._state.cached_node_ids:
                        self._state.cached_node_ids.append(nid)
        elif msg_type == "executing":
            node = data.get("node")
            if node is None:
                # Comfy signals end-of-prompt via {"node": null}.
                if self._state.current_node_id is not None:
                    nid = self._state.current_node_id
                    if nid not in self._state.executed_node_ids:
                        self._state.executed_node_ids.append(nid)
                self._state.current_node_id = None
                self._state.current_node_class_type = None
                self._state.current_node_started_at = None
                self._state.current_node_progress = None
                self._state.prompt_completed = True
            else:
                nid = str(node)
                # Transitioning to a new node: record the previous one as executed.
                prev = self._state.current_node_id
                if prev is not None and prev != nid and prev not in self._state.executed_node_ids:
                    self._state.executed_node_ids.append(prev)
                self._state.current_node_id = nid
                self._state.current_node_class_type = self._node_class_by_id.get(nid)
                self._state.current_node_started_at = _now()
                self._state.current_node_progress = None
        elif msg_type == "progress":
            node = data.get("node")
            value = data.get("value")
            maximum = data.get("max")
            if node is not None and isinstance(value, (int, float)) and isinstance(maximum, (int, float)):
                nid = str(node)
                self._state.current_node_progress = {"value": int(value), "max": int(maximum)}
                self._recent_progress.append(
                    ProgressEvent(timestamp=_now(), node_id=nid, value=int(value), max=int(maximum))
                )
        elif msg_type == "executed":
            node = data.get("node")
            if node is not None:
                nid = str(node)
                if nid not in self._state.executed_node_ids:
                    self._state.executed_node_ids.append(nid)
        elif msg_type == "execution_error":
            self._state.last_error = dict(data)
            self._state.prompt_completed = False
        # status / other types: just bump last_event_at and move on.

    # -- VRAM sampling --------------------------------------------------------

    async def _poll_loop(self) -> None:
        """Poll ``/system_stats`` every ``vram_poll_interval_s`` seconds."""
        # Stagger first sample slightly so a fast clean run doesn't block on
        # an HTTP roundtrip just to make a 0-sample report.
        try:
            await asyncio.wait_for(self._stopped.wait(), timeout=0.05)
            return
        except asyncio.TimeoutError:
            pass
        while not self._stopped.is_set():
            try:
                await self._sample_system_stats()
            except Exception:  # pragma: no cover
                logger.exception("watchdog: system_stats sample failed")
                self._stats_responsive = False
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=self.vram_poll_interval_s)
            except asyncio.TimeoutError:
                continue

    async def _sample_system_stats(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.server_url}/system_stats")
        except httpx.HTTPError:
            self._stats_responsive = False
            self._vram_samples.append(VramSample(timestamp=_now(), vram_free_bytes=None, vram_total_bytes=None))
            return
        if resp.status_code != 200:
            self._stats_responsive = False
            self._vram_samples.append(VramSample(timestamp=_now(), vram_free_bytes=None, vram_total_bytes=None))
            return
        try:
            payload = resp.json()
        except ValueError:
            self._stats_responsive = False
            return
        self._stats_responsive = True
        free, total = _extract_vram(payload)
        self._vram_samples.append(VramSample(timestamp=_now(), vram_free_bytes=free, vram_total_bytes=total))

    # -- diagnosis ------------------------------------------------------------

    def _diagnose(self) -> tuple[str, str]:
        """Choose a single diagnosis label and a one-line reason string.

        Order matters. Earlier branches take precedence over later ones.
        """
        st = self._state
        now = _now()

        # errored: an execution_error message arrived.
        if st.last_error is not None:
            err_msg = st.last_error.get("exception_message") or st.last_error.get("exception_type") or "unknown"
            return "errored", f"execution_error captured: {err_msg}"

        # completed: server signalled end-of-prompt with executing:null.
        if st.prompt_completed and st.current_node_id is None:
            return (
                "completed",
                f"prompt finished cleanly; {len(st.executed_node_ids)} nodes executed, "
                f"{len(st.cached_node_ids)} cached",
            )

        # completed: the caller stopped the watchdog after a successful run
        # even though the event stream never delivered executing:null. This is
        # common for embedded runs whose local server shuts down immediately
        # after returning outputs; do not let a final /system_stats miss turn
        # a successful run into a false crash report.
        if st.stop_reason == "completed":
            return "completed", "stop reason was 'completed' but no execution termination event was seen"

        # crashed: poll loop ran but /system_stats stopped responding.
        # Only declare crashed if we did at least one sample. If the server was
        # never reachable, fall through to missing_event_stream below.
        if self._stats_responsive is False and self._vram_samples:
            return "crashed", "/system_stats stopped responding"

        # missing_event_stream: we never connected to /ws or got disconnected
        # before any execution_start arrived.
        if st.connection_state in {"never_connected", "disconnected"} and st.prompt_id is None and not st.executed_node_ids:
            return (
                "missing_event_stream",
                f"ws connection_state={st.connection_state} and no execution_start received",
            )

        # oom_ish: VRAM free has been below threshold for several samples and
        # the current node has been active long enough to have OOM'd.
        consecutive_low = self._consecutive_low_vram_samples()
        node_active_s = self._current_node_active_seconds(now)
        if (
            consecutive_low >= OOM_CONSECUTIVE_SAMPLES
            and node_active_s is not None
            and node_active_s > OOM_NODE_ACTIVE_S
        ):
            return (
                "oom_ish",
                f"vram_free<{OOM_FREE_BYTES} bytes for {consecutive_low} consecutive samples; "
                f"current node active {int(node_active_s)}s",
            )

        # stalled_runtime: no events in the last STALL_NO_EVENT_S seconds, but
        # the HTTP control plane is still responsive.
        seconds_since_event = self._seconds_since_last_event(now)
        if (
            seconds_since_event is not None
            and seconds_since_event > STALL_NO_EVENT_S
            and self._stats_responsive is not False
        ):
            return (
                "stalled_runtime",
                f"no ws events in {int(seconds_since_event)}s but /system_stats still responds",
            )

        # slow_node: events still arriving recently AND current node has been
        # active above SLOW_NODE_ACTIVE_S.
        if (
            seconds_since_event is not None
            and seconds_since_event <= SLOW_RECENT_EVENT_WINDOW_S
            and node_active_s is not None
            and node_active_s > SLOW_NODE_ACTIVE_S
        ):
            return (
                "slow_node",
                f"current node active {int(node_active_s)}s; last event {int(seconds_since_event)}s ago",
            )

        # Fallback: "in_progress" — nothing alarming yet.
        return "in_progress", "no diagnosis condition matched at dump time"

    # -- diagnosis helpers ----------------------------------------------------

    def _consecutive_low_vram_samples(self) -> int:
        count = 0
        for sample in reversed(self._vram_samples):
            if sample.vram_free_bytes is None:
                break
            if sample.vram_free_bytes < OOM_FREE_BYTES:
                count += 1
            else:
                break
        return count

    def _seconds_since_last_event(self, now: float) -> float | None:
        if self._state.last_event_at is None:
            return None
        return max(0.0, now - self._state.last_event_at)

    def _current_node_active_seconds(self, now: float) -> float | None:
        started = self._state.current_node_started_at
        if started is None:
            return None
        return max(0.0, now - started)


# --- /system_stats parsing ---------------------------------------------------


def _extract_vram(payload: Any) -> tuple[int | None, int | None]:
    """Pull (free, total) VRAM bytes from a /system_stats response.

    The Comfy payload shape is roughly:
        {
          "system": {...},
          "devices": [
            {"name": "...", "type": "cuda", "vram_total": int, "vram_free": int, ...}
          ]
        }
    We pick the first device with vram_total > 0. CPU-only systems will
    return (None, None) and the watchdog will surface that as missing data.
    """
    if not isinstance(payload, Mapping):
        return None, None
    devices = payload.get("devices")
    if not isinstance(devices, list):
        return None, None
    for dev in devices:
        if not isinstance(dev, Mapping):
            continue
        total = dev.get("vram_total")
        free = dev.get("vram_free")
        if isinstance(total, (int, float)) and total > 0:
            return (
                int(free) if isinstance(free, (int, float)) else None,
                int(total),
            )
    return None, None


# --- Convenience: write a report to disk -------------------------------------


def write_report(run_dir: Any, report: WatchdogReport) -> str:
    """Write the watchdog report as ``<run_dir>/watchdog.json``.

    The first line of the file is the human-readable header line; the rest is
    a pretty-printed JSON body. Returns the absolute path written.
    """
    from pathlib import Path

    run_path = Path(run_dir)
    run_path.mkdir(parents=True, exist_ok=True)
    target = run_path / "watchdog.json"
    body = json.dumps(report.to_json(), indent=2, default=str)
    text = f"{report.header_line()}\n{body}\n"
    target.write_text(text, encoding="utf-8")
    return str(target)
