from dataclasses import dataclass


@dataclass(frozen=True)
class AdaptiveContext:
    focus_areas: list[str]
    coaching_focus: list[str]
    opponent_adjustments: list[str]
    strengths: list[str]
