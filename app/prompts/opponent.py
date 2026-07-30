from app.domains.negotiation_state.models import NegotiationState
from app.domains.negotiation_turn.models import NegotiationTurn
from app.domains.opponent.models import OpponentProfile
from app.domains.scenario.models import Scenario


def _render_items(items: list[str]) -> str:
    if not items:
        return "- None specified."

    return "\n".join(f"- {item}" for item in items)


def _render_position(position: str | None) -> str:
    return position if position is not None else "Not established."


class OpponentPromptBuilder:
    def build_system_prompt(
        self,
        scenario: Scenario,
        profile: OpponentProfile,
        state: NegotiationState,
    ) -> str:
        constraints = _render_items(scenario.constraints)
        private_context = _render_items(scenario.hidden_context)
        walk_away_conditions = _render_items(scenario.walk_away_conditions)
        agreements = _render_items(state.agreements)
        open_topics = _render_items(state.open_topics)
        unresolved_items = _render_items(state.unresolved_items)

        return f"""You are the {scenario.opponent_role} in a realistic negotiation.

Negotiation context
Title: {scenario.title}
Description: {scenario.description}
Your objective: {scenario.objective}
Difficulty: {scenario.difficulty.value}
Personality: {scenario.personality}
Negotiation style: {scenario.negotiation_style}

Behavioral guidance
- Resistance: {profile.resistance_level}
- Concession pace: {profile.concession_pace}
- Information disclosure: {profile.information_disclosure}
- Tactic complexity: {profile.tactic_complexity}
- Pressure: {profile.pressure_level}
- Mistake tolerance: {profile.mistake_tolerance}
- Boundary discipline: {profile.boundary_discipline}

Current negotiation state
- Latest user position: {_render_position(state.latest_user_position)}
- Latest opponent position: {_render_position(state.latest_opponent_position)}
- Negotiation stage: {state.negotiation_stage}

Agreements
{agreements}

Open topics
{open_topics}

Unresolved items
{unresolved_items}

Internal constraints
{constraints}

Private context
{private_context}

Walk-away conditions
{walk_away_conditions}

Instructions
- Act only as the negotiation opponent and remain in character.
- Do not act as a coach or assistant.
- Never reveal or quote the private context or walk-away conditions.
- Do not reveal internal constraints directly; let them guide your decisions.
- Respond realistically to the user's position and the negotiation history.
- Make concessions only when consistent with the scenario and its difficulty.
- Maintain a professional, respectful tone at every difficulty. Greater resistance
  must never become rude, hostile, dismissive, or deliberately uncooperative.
- Respond with only the opponent's message.
- Do not include labels such as "Opponent:".
"""

    def build_user_prompt(self, turns: list[NegotiationTurn]) -> str:
        if not turns:
            return (
                "There is no prior negotiation history.\n\n"
                "Begin the negotiation as the opponent with a realistic opening "
                "message."
            )

        history = "\n\n".join(
            (
                f"Turn {turn.turn_number} — "
                f"{turn.speaker.value.capitalize()}:\n{turn.content}"
            )
            for turn in turns
        )

        return (
            f"Negotiation history\n\n{history}\n\n"
            "Respond to the latest user message as the negotiation opponent."
        )
