from dataclasses import dataclass


@dataclass(frozen=True)
class OpponentProfile:
    resistance_level: str
    concession_pace: str
    information_disclosure: str
    tactic_complexity: str
    pressure_level: str
    mistake_tolerance: str
    boundary_discipline: str
