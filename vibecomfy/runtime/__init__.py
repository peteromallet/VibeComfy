from .run import run, run_embedded, run_embedded_sync, run_sync, smoke_runtime, smoke_runtime_sync
from .session import EmbeddedSession, RunResult, ServerSession, SessionConfig, apply_memory_profile_override

__all__ = [
    "EmbeddedSession",
    "EnsureEnvResult",
    "EnsureFailure",
    "EnsurePackOutcome",
    "RunResult",
    "ServerSession",
    "SessionConfig",
    "apply_memory_profile_override",
    "ensure_env",
    "run",
    "run_sync",
    "run_embedded",
    "run_embedded_sync",
    "smoke_runtime",
    "smoke_runtime_sync",
]

_LAZY_ENSURE_ENV = None


def __getattr__(name: str):
    global _LAZY_ENSURE_ENV
    if name in {"ensure_env", "EnsureEnvResult", "EnsurePackOutcome", "EnsureFailure"}:
        if _LAZY_ENSURE_ENV is None:
            from .ensure_env import EnsureEnvResult as _EER, EnsureFailure as _EF, EnsurePackOutcome as _EPO, ensure_env as _ee  # noqa: E501
            _LAZY_ENSURE_ENV = {
                "ensure_env": _ee,
                "EnsureEnvResult": _EER,
                "EnsurePackOutcome": _EPO,
                "EnsureFailure": _EF,
            }
        return _LAZY_ENSURE_ENV[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
