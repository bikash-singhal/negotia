from app.domains.opponent.exceptions import UnsupportedScenarioDifficultyError
from app.domains.opponent.models import OpponentProfile
from app.domains.scenario.models import ScenarioDifficulty


class OpponentProfileBuilder:
    def build(self, difficulty: ScenarioDifficulty) -> OpponentProfile:
        if difficulty is ScenarioDifficulty.BEGINNER:
            return OpponentProfile(
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
            )

        if difficulty is ScenarioDifficulty.INTERMEDIATE:
            return OpponentProfile(
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
            )

        if difficulty is ScenarioDifficulty.ADVANCED:
            return OpponentProfile(
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
            )

        raise UnsupportedScenarioDifficultyError(difficulty)
