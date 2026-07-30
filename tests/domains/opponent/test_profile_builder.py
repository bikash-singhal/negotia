from typing import cast

import pytest

from app.domains.opponent.exceptions import UnsupportedScenarioDifficultyError
from app.domains.opponent.models import OpponentProfile
from app.domains.opponent.profile_builder import OpponentProfileBuilder
from app.domains.scenario.models import ScenarioDifficulty


@pytest.mark.parametrize(
    ("difficulty", "expected_profile"),
    [
        (
            ScenarioDifficulty.BEGINNER,
            OpponentProfile(
                resistance_level=(
                    "Low - engage openly and challenge only clearly unfavorable "
                    "proposals."
                ),
                concession_pace=(
                    "Responsive - make modest concessions after reasonable user "
                    "arguments."
                ),
                information_disclosure=(
                    "Open - volunteer useful non-confidential information that "
                    "helps the negotiation progress."
                ),
                tactic_complexity=(
                    "Simple - use direct trade-offs and address one issue at a time."
                ),
                pressure_level=(
                    "Low - keep urgency mild and give the user room to recover."
                ),
                mistake_tolerance=(
                    "High - overlook minor negotiation mistakes and clarify "
                    "misunderstandings."
                ),
                boundary_discipline=(
                    "Flexible - explore alternatives while still respecting "
                    "walk-away conditions."
                ),
            ),
        ),
        (
            ScenarioDifficulty.INTERMEDIATE,
            OpponentProfile(
                resistance_level=(
                    "Moderate - question weak assumptions while engaging "
                    "constructively with credible proposals."
                ),
                concession_pace=(
                    "Measured - require clear value in return for meaningful "
                    "concessions."
                ),
                information_disclosure=(
                    "Selective - share useful non-confidential information when it "
                    "advances your objective."
                ),
                tactic_complexity=(
                    "Moderate - combine issues and use conditional trade-offs when "
                    "appropriate."
                ),
                pressure_level=(
                    "Balanced - use reasonable urgency without becoming aggressive."
                ),
                mistake_tolerance=(
                    "Moderate - notice mistakes but allow well-reasoned recovery."
                ),
                boundary_discipline=(
                    "Firm - protect key constraints while exploring viable "
                    "alternatives."
                ),
            ),
        ),
        (
            ScenarioDifficulty.ADVANCED,
            OpponentProfile(
                resistance_level=(
                    "High - test proposals rigorously and resist terms that do not "
                    "advance your objective."
                ),
                concession_pace=(
                    "Slow - concede only after receiving substantial reciprocal value."
                ),
                information_disclosure=(
                    "Guarded - reveal only non-confidential information that "
                    "strategically supports your position."
                ),
                tactic_complexity=(
                    "Sophisticated - use multi-issue trades, conditional offers, "
                    "and careful anchoring."
                ),
                pressure_level=(
                    "High but professional - create disciplined urgency without "
                    "hostility or disrespect."
                ),
                mistake_tolerance=(
                    "Low - recognize weak anchors and unsupported claims while "
                    "remaining constructive."
                ),
                boundary_discipline=(
                    "Strict - protect constraints and walk-away conditions while "
                    "considering credible trades."
                ),
            ),
        ),
    ],
)
def test_difficulty_maps_to_expected_profile(
    difficulty: ScenarioDifficulty,
    expected_profile: OpponentProfile,
) -> None:
    assert OpponentProfileBuilder().build(difficulty) == expected_profile


def test_unsupported_difficulty_raises_domain_error() -> None:
    difficulty = cast(ScenarioDifficulty, "unsupported")

    with pytest.raises(UnsupportedScenarioDifficultyError) as exc_info:
        OpponentProfileBuilder().build(difficulty)

    assert exc_info.value.difficulty == difficulty
    assert str(exc_info.value) == "Unsupported scenario difficulty: 'unsupported'."
