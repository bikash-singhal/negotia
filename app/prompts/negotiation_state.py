from app.domains.negotiation_turn.models import NegotiationTurn


class NegotiationStatePromptBuilder:
    def build_system_prompt(self) -> str:
        return """You extract structured negotiation state from negotiation history.

You are analyzing the conversation, not responding as the negotiation opponent.
Rules:
- Replace the example values with concise, factual descriptions from the history.
- Use a JSON string or null for each latest position.
- Use arrays of JSON strings for agreements, open topics, and unresolved items.
- Distinguish the user's position from the opponent's position.
- Do not invent agreements, offers, open topics, or unresolved issues.
- Use empty arrays when the history provides no items for a category.
- Include every required key exactly once and do not include additional keys.

Output requirements:
- You MUST return exactly one valid JSON object and nothing else.
- DO NOT wrap the JSON in Markdown or code fences.
- DO NOT include a preamble, label, explanation, or commentary before or after it.
- Values MUST use the exact types shown below.

Return exactly this JSON structure, replacing only its values:
{
  "latest_user_position": null,
  "latest_opponent_position": null,
  "agreements": [],
  "open_topics": [],
  "unresolved_items": [],
  "negotiation_stage": "opening"
}
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
            "Extract the current negotiation state and return only the required "
            "JSON object."
        )
