from dataclasses import FrozenInstanceError

import pytest

from app.domains.adaptive_context.models import AdaptiveContext


def test_adaptive_context_is_frozen_runtime_projection() -> None:
    context = AdaptiveContext(
        focus_areas=["Diagnostic questioning"],
        coaching_focus=["Active listening"],
        opponent_adjustments=["Test unilateral concessions"],
        strengths=["Uses conditional trades"],
    )

    assert context.focus_areas == ["Diagnostic questioning"]
    field_name = "focus_areas"
    with pytest.raises(FrozenInstanceError):
        setattr(context, field_name, [])
