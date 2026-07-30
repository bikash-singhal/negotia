from app.domains.adaptive_context.models import AdaptiveContext
from app.domains.negotiation_turn.models import NegotiationTurn


class CoachPromptBuilder:
    def build_system_prompt(
        self,
        adaptive_context: AdaptiveContext | None = None,
    ) -> str:
        base_prompt = """You are an expert negotiation coach.

You are analyzing the conversation.
You are NOT participating in the negotiation.
Evaluate only the user's negotiation behavior.
Return exactly one valid JSON object with this structure:
{
  "strengths": [],
  "weaknesses": [],
  "missed_opportunities": [],
  "risk_signals": [],
  "confidence": "low"
}

Rules
- Base every observation on evidence from the conversation.
- Do not invent strengths, weaknesses, missed opportunities, or risk signals.
- Use concise, factual descriptions.
- Use empty arrays when the conversation provides no supported observations.
- Return only JSON, with no Markdown fences, labels, explanations, or commentary.
"""
        if adaptive_context is None:
            return base_prompt

        focus_areas = "\n".join(f"- {item}" for item in adaptive_context.focus_areas)
        coaching_focus = "\n".join(
            f"- {item}" for item in adaptive_context.coaching_focus
        )
        strengths = "\n".join(f"- {item}" for item in adaptive_context.strengths)

        return f"""{base_prompt}
--- Historical coaching context ---

Use this historical context only to guide your observational attention.
- Evaluate the current negotiation using current-session evidence.
- Do not assume a historical weakness occurred again.
- Do not claim improvement or regression without supporting current-session evidence.
- Use recurring strengths as observation context, not guaranteed current behavior.

Focus areas
{focus_areas}

Coaching focus
{coaching_focus}

Recurring strengths
{strengths}

--- End historical coaching context ---
"""

    def build_user_prompt(self, turns: list[NegotiationTurn]) -> str:
        if not turns:
            history = "No negotiation turns are available."
        else:
            history = "\n\n".join(
                (
                    f"Turn {turn.turn_number} - "
                    f"{turn.speaker.value.capitalize()}:\n{turn.content}"
                )
                for turn in sorted(turns, key=lambda turn: turn.turn_number)
            )

        return (
            f"Complete ordered negotiation history\n\n{history}\n\n"
            "Analyze only the user's negotiation behavior and return the required "
            "JSON object."
        )
