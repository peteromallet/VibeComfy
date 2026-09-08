"""Model-independent temporal delivery contracts.

These value objects describe frame accounting at the boundary between a
workflow's working representation and delivered media. They deliberately do
not encode any model's latent grid, padding, or sampling rules: callers supply
those alignment positions after applying model-specific rules.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal


Indexing = Literal["zero_based", "one_based"]
ZERO_BASED: Indexing = "zero_based"
ONE_BASED: Indexing = "one_based"


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"`{name}` must be an integer.")
    return value


def _positive_integer(value: Any, name: str) -> int:
    result = _integer(value, name)
    if result <= 0:
        raise ValueError(f"`{name}` must be positive.")
    return result


def _finite_positive(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"`{name}` must be a positive number.")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"`{name}` must be a finite positive number.")
    return result


def _non_negative_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"`{name}` must be a non-negative number.")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"`{name}` must be a finite non-negative number.")
    return result


def _indexing(value: Any, name: str = "indexing") -> Indexing:
    if value not in (ZERO_BASED, ONE_BASED):
        raise ValueError(f"`{name}` must be 'zero_based' or 'one_based'.")
    return value


def _json_safe(value: Any, name: str) -> Any:
    """Return a detached JSON-safe copy of evidence metadata."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"`{name}` must not contain NaN or infinity.")
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"`{name}` object keys must be strings.")
            result[key] = _json_safe(item, f"{name}.{key}")
        return result
    if isinstance(value, (list, tuple)):
        return [_json_safe(item, f"{name}[]") for item in value]
    raise ValueError(f"`{name}` must contain only JSON-serializable values.")


def _evidence(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("`evidence` must be an object.")
    return _json_safe(value, "evidence")


def _payload(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object.")
    return value


@dataclass(frozen=True, slots=True)
class FrameSlice:
    """A non-empty half-open frame range.

    ``[start, stop)`` is half-open in either indexing convention. A one-based
    range therefore uses ``[1, frame_count + 1)`` for a complete sequence.
    """

    start: int
    stop: int
    indexing: Indexing = ZERO_BASED

    def __post_init__(self) -> None:
        start = _integer(self.start, "start")
        stop = _integer(self.stop, "stop")
        indexing = _indexing(self.indexing)
        minimum = 0 if indexing == ZERO_BASED else 1
        if start < minimum:
            raise ValueError(f"`start` must be >= {minimum} for {indexing} indexing.")
        if stop <= start:
            raise ValueError("`stop` must be greater than `start`.")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "stop", stop)
        object.__setattr__(self, "indexing", indexing)

    @classmethod
    def from_count(cls, start: int, count: int, indexing: Indexing = ZERO_BASED) -> "FrameSlice":
        return cls(start=start, stop=start + _positive_integer(count, "count"), indexing=indexing)

    @property
    def count(self) -> int:
        return self.stop - self.start

    def contains(self, position: int) -> bool:
        position = _integer(position, "position")
        return self.start <= position < self.stop

    def zero_based_bounds(self) -> tuple[int, int]:
        offset = 1 if self.indexing == ONE_BASED else 0
        return self.start - offset, self.stop - offset

    def convert_indexing(self, indexing: Indexing) -> "FrameSlice":
        indexing = _indexing(indexing)
        start, stop = self.zero_based_bounds()
        offset = 1 if indexing == ONE_BASED else 0
        return FrameSlice(start=start + offset, stop=stop + offset, indexing=indexing)

    def intersection(self, other: "FrameSlice") -> "FrameSlice | None":
        if not isinstance(other, FrameSlice):
            raise TypeError("other must be a FrameSlice")
        if self.indexing != other.indexing:
            raise ValueError("frame slices must use the same indexing for arithmetic")
        start, stop = max(self.start, other.start), min(self.stop, other.stop)
        return FrameSlice(start, stop, self.indexing) if start < stop else None

    def to_dict(self) -> dict[str, Any]:
        return {"start": self.start, "stop": self.stop, "indexing": self.indexing}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FrameSlice":
        payload = _payload(value, "FrameSlice")
        return cls(payload["start"], payload["stop"], payload.get("indexing", ZERO_BASED))


@dataclass(frozen=True, slots=True)
class TemporalPlan:
    """Frame accounting for one temporal delivery.

    ``generated_frames`` counts generated frames included in ``delivery``; it
    does not count hidden context or discarded working-grid padding.
    ``alignment_positions`` are positions in ``working`` and may use a
    separately declared indexing convention.
    """

    fps: float
    delivery: FrameSlice
    indexing: Indexing = ZERO_BASED
    source: FrameSlice | None = None
    context: FrameSlice | None = None
    working: FrameSlice | None = None
    generated_frames: int | None = None
    alignment_positions: tuple[int, ...] = ()
    alignment_indexing: Indexing | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        fps = _finite_positive(self.fps, "fps")
        indexing = _indexing(self.indexing)
        if not isinstance(self.delivery, FrameSlice):
            raise ValueError("`delivery` must be a FrameSlice.")
        object.__setattr__(self, "fps", fps)
        object.__setattr__(self, "indexing", indexing)
        slices = {
            name: value
            for name, value in (
                ("source", self.source),
                ("context", self.context),
                ("working", self.working),
                ("delivery", self.delivery),
            )
            if value is not None
        }
        mismatched = sorted(name for name, value in slices.items() if value.indexing != indexing)
        if mismatched:
            raise ValueError(f"temporal slices {mismatched!r} must use plan indexing {indexing!r}.")

        if self.context is not None and self.source is not None:
            source_start, source_stop = self.source.zero_based_bounds()
            context_start, context_stop = self.context.zero_based_bounds()
            if not (source_start <= context_start and context_stop <= source_stop):
                raise ValueError("`context` must be contained within `source`.")
        if self.working is not None:
            working_start, working_stop = self.working.zero_based_bounds()
            delivery_start, delivery_stop = self.delivery.zero_based_bounds()
            if not (working_start <= delivery_start and delivery_stop <= working_stop):
                raise ValueError("`delivery` must be contained within `working`.")

        if self.generated_frames is not None:
            generated = _integer(self.generated_frames, "generated_frames")
            if generated < 0 or generated > self.delivery.count:
                raise ValueError("`generated_frames` must be between 0 and delivery.count.")
            object.__setattr__(self, "generated_frames", generated)

        positions = tuple(_integer(position, "alignment_positions[]") for position in self.alignment_positions)
        if len(set(positions)) != len(positions):
            raise ValueError("`alignment_positions` must not contain duplicates.")
        alignment_indexing = _indexing(self.alignment_indexing or indexing, "alignment_indexing")
        if positions and self.working is None:
            raise ValueError("`working` is required when alignment_positions are supplied.")
        if self.working is not None:
            working_start, working_stop = self.working.zero_based_bounds()
            position_offset = 1 if alignment_indexing == ONE_BASED else 0
            for position in positions:
                normalized = position - position_offset
                if not working_start <= normalized < working_stop:
                    raise ValueError("each alignment position must fall within working.")
        object.__setattr__(self, "alignment_positions", positions)
        object.__setattr__(self, "alignment_indexing", alignment_indexing)
        object.__setattr__(self, "evidence", _evidence(self.evidence))

    @property
    def delivery_frames(self) -> int:
        return self.delivery.count

    @property
    def context_frames(self) -> int:
        return self.context.count if self.context is not None else 0

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "fps": self.fps,
            "indexing": self.indexing,
            "delivery": self.delivery.to_dict(),
            "alignment_positions": list(self.alignment_positions),
            "alignment_indexing": self.alignment_indexing,
            "evidence": _json_safe(self.evidence, "evidence"),
        }
        for name in ("source", "context", "working"):
            value = getattr(self, name)
            if value is not None:
                payload[name] = value.to_dict()
        if self.generated_frames is not None:
            payload["generated_frames"] = self.generated_frames
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TemporalPlan":
        payload = _payload(value, "TemporalPlan")
        return cls(
            fps=payload["fps"],
            delivery=FrameSlice.from_dict(_payload(payload["delivery"], "delivery")),
            indexing=payload.get("indexing", ZERO_BASED),
            source=(FrameSlice.from_dict(_payload(payload["source"], "source")) if payload.get("source") is not None else None),
            context=(FrameSlice.from_dict(_payload(payload["context"], "context")) if payload.get("context") is not None else None),
            working=(FrameSlice.from_dict(_payload(payload["working"], "working")) if payload.get("working") is not None else None),
            generated_frames=payload.get("generated_frames"),
            alignment_positions=tuple(payload.get("alignment_positions", ())),
            alignment_indexing=payload.get("alignment_indexing"),
            evidence=payload.get("evidence", {}),
        )


@dataclass(frozen=True, slots=True)
class TerminalConstraint:
    """A declared terminal frame target for a later decoder/verifier."""

    target_ref: str
    frame_index: int
    indexing: Indexing = ZERO_BASED
    metric: str = "decoded_rgb_sha256"
    tolerance: float = 0.0
    convergence_frames: int = 1
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.target_ref, str) or not self.target_ref.strip():
            raise ValueError("`target_ref` must be a non-empty string.")
        object.__setattr__(self, "target_ref", self.target_ref.strip())
        frame_index = _integer(self.frame_index, "frame_index")
        indexing = _indexing(self.indexing)
        minimum = 0 if indexing == ZERO_BASED else 1
        if frame_index < minimum:
            raise ValueError(f"`frame_index` must be >= {minimum} for {indexing} indexing.")
        if not isinstance(self.metric, str) or not self.metric.strip():
            raise ValueError("`metric` must be a non-empty string.")
        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(self, "indexing", indexing)
        object.__setattr__(self, "metric", self.metric.strip())
        object.__setattr__(self, "tolerance", _non_negative_number(self.tolerance, "tolerance"))
        object.__setattr__(self, "convergence_frames", _positive_integer(self.convergence_frames, "convergence_frames"))
        object.__setattr__(self, "evidence", _evidence(self.evidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_ref": self.target_ref,
            "frame_index": self.frame_index,
            "indexing": self.indexing,
            "metric": self.metric,
            "tolerance": self.tolerance,
            "convergence_frames": self.convergence_frames,
            "evidence": _json_safe(self.evidence, "evidence"),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TerminalConstraint":
        payload = _payload(value, "TerminalConstraint")
        return cls(
            target_ref=payload["target_ref"],
            frame_index=payload["frame_index"],
            indexing=payload.get("indexing", ZERO_BASED),
            metric=payload.get("metric", "decoded_rgb_sha256"),
            tolerance=payload.get("tolerance", 0.0),
            convergence_frames=payload.get("convergence_frames", 1),
            evidence=payload.get("evidence", {}),
        )


@dataclass(frozen=True, slots=True)
class DecodedMediaExpectation:
    """Decoded media properties a runtime verifier may check."""

    frames: int | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    require_audio: bool = False
    audio_sample_rate: int | None = None
    audio_channels: int | None = None
    pixel_format: str | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("frames", "width", "height"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _positive_integer(value, name))
        if self.fps is not None:
            object.__setattr__(self, "fps", _finite_positive(self.fps, "fps"))
        if not isinstance(self.require_audio, bool):
            raise ValueError("`require_audio` must be a boolean.")
        for name in ("audio_sample_rate", "audio_channels"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _positive_integer(value, name))
                if not self.require_audio:
                    raise ValueError(f"`{name}` requires require_audio=True.")
        if self.pixel_format is not None:
            if not isinstance(self.pixel_format, str) or not self.pixel_format.strip():
                raise ValueError("`pixel_format` must be a non-empty string when provided.")
            object.__setattr__(self, "pixel_format", self.pixel_format.strip())
        if all(value is None for value in (self.frames, self.width, self.height, self.fps, self.pixel_format)) and not self.require_audio:
            raise ValueError("DecodedMediaExpectation must declare at least one expectation.")
        object.__setattr__(self, "evidence", _evidence(self.evidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "frames": self.frames,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "require_audio": self.require_audio,
            "audio_sample_rate": self.audio_sample_rate,
            "audio_channels": self.audio_channels,
            "pixel_format": self.pixel_format,
            "evidence": _json_safe(self.evidence, "evidence"),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DecodedMediaExpectation":
        payload = _payload(value, "DecodedMediaExpectation")
        return cls(
            frames=payload.get("frames"),
            width=payload.get("width"),
            height=payload.get("height"),
            fps=payload.get("fps"),
            require_audio=payload.get("require_audio", False),
            audio_sample_rate=payload.get("audio_sample_rate"),
            audio_channels=payload.get("audio_channels"),
            pixel_format=payload.get("pixel_format"),
            evidence=payload.get("evidence", {}),
        )


__all__ = [
    "DecodedMediaExpectation",
    "FrameSlice",
    "Indexing",
    "ONE_BASED",
    "TemporalPlan",
    "TerminalConstraint",
    "ZERO_BASED",
]
