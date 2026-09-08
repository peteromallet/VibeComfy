import json

import pytest

from vibecomfy.contracts import (
    DecodedMediaExpectation,
    FrameSlice,
    ONE_BASED,
    TemporalPlan,
    TerminalConstraint,
    ZERO_BASED,
)


def test_frame_slice_supports_half_open_arithmetic_and_index_conversion() -> None:
    one_based = FrameSlice(1, 91, ONE_BASED)
    assert one_based.count == 90
    assert one_based.contains(90)
    assert not one_based.contains(91)
    assert one_based.zero_based_bounds() == (0, 90)
    assert one_based.convert_indexing(ZERO_BASED) == FrameSlice(0, 90)
    assert FrameSlice(3, 8).intersection(FrameSlice(6, 10)) == FrameSlice(6, 8)


def test_temporal_plan_validates_delivery_context_alignment_and_json_evidence() -> None:
    plan = TemporalPlan(
        fps=24,
        source=FrameSlice(85, 124),
        context=FrameSlice(95, 124),
        working=FrameSlice(0, 90),
        delivery=FrameSlice(9, 69),
        generated_frames=40,
        alignment_positions=(69,),
        alignment_indexing=ONE_BASED,
        evidence={"source": {"sha256": "abc", "frames": 39}},
    )
    assert plan.delivery_frames == 60
    assert plan.context_frames == 29
    payload = plan.to_dict()
    assert json.loads(json.dumps(payload))["alignment_positions"] == [69]
    assert TemporalPlan.from_dict(payload) == plan


@pytest.mark.parametrize(
    "kwargs",
    [
        {"context": FrameSlice(90, 125), "source": FrameSlice(85, 124)},
        {"working": FrameSlice(0, 60), "delivery": FrameSlice(9, 69)},
        {"working": FrameSlice(0, 10), "alignment_positions": (11,)},
        {"working": FrameSlice(0, 10), "alignment_positions": (0, 0)},
    ],
)
def test_temporal_plan_rejects_inconsistent_frame_arithmetic(kwargs) -> None:
    defaults = {"fps": 24, "delivery": FrameSlice(0, 5)}
    defaults.update(kwargs)
    with pytest.raises(ValueError):
        TemporalPlan(**defaults)


def test_terminal_and_decoded_expectation_round_trip_and_validate() -> None:
    terminal = TerminalConstraint(
        target_ref="inputs/destination.png",
        frame_index=59,
        metric="decoded_rgb_sha256",
        convergence_frames=8,
        evidence={"asset_sha256": "abc"},
    )
    expected = DecodedMediaExpectation(
        frames=60,
        width=960,
        height=544,
        fps=24,
        require_audio=True,
        audio_sample_rate=32000,
        audio_channels=2,
        pixel_format="rgb24",
    )
    assert TerminalConstraint.from_dict(terminal.to_dict()) == terminal
    assert DecodedMediaExpectation.from_dict(expected.to_dict()) == expected
    json.dumps(terminal.to_dict())
    json.dumps(expected.to_dict())


def test_contracts_reject_unsafe_evidence_and_invalid_expectations() -> None:
    with pytest.raises(ValueError):
        TemporalPlan(fps=24, delivery=FrameSlice(0, 1), evidence={"bad": float("nan")})
    with pytest.raises(ValueError):
        DecodedMediaExpectation(require_audio=False, audio_channels=2)
    with pytest.raises(ValueError):
        TerminalConstraint(target_ref="x", frame_index=-1)
