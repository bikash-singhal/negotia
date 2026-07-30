from dataclasses import dataclass


@dataclass(frozen=True)
class CoachObservation:
    strengths: list[str]
    weaknesses: list[str]
    missed_opportunities: list[str]
    risk_signals: list[str]
    confidence: str
