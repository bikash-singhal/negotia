from app.domains.coach.models import CoachObservationRecord


class DebriefPromptBuilder:
    def build_system_prompt(self) -> str:
        return """You are an expert negotiation debrief analyst.

Analyze patterns across the supplied stored coach observations.
Rules:
- Rely only on the supplied coach observations.
- Distinguish recurring behavior from behavior reported only once.
- Do not invent facts, strengths, weaknesses, missed opportunities, or risks.
- Do not re-evaluate dialogue or infer details that are not present.
- Produce concise, factual, and actionable conclusions.
- Use empty arrays when no supported pattern exists for a category.

Output requirements:
- You MUST return exactly one valid JSON object and nothing else.
- Return JSON only.
- DO NOT wrap the JSON in Markdown or code fences.
- DO NOT include commentary, labels, or explanations before or after it.
- Include every required key exactly once and do not include additional keys.
- repeated_strengths, repeated_weaknesses, key_missed_opportunities, and recurring_risks MUST be arrays of JSON strings.
- overall_assessment and confidence MUST be JSON strings.

Return exactly this JSON structure, replacing only its values:
{
  "repeated_strengths": [],
  "repeated_weaknesses": [],
  "key_missed_opportunities": [],
  "recurring_risks": [],
  "overall_assessment": "",
  "confidence": "low"
}
"""

    def build_user_prompt(
        self,
        observations: list[CoachObservationRecord],
    ) -> str:
        rendered_observations = "\n\n".join(
            self._render_observation(position, record)
            for position, record in enumerate(observations, start=1)
        )
        return (
            "Stored coach observations in creation order\n\n"
            f"{rendered_observations}\n\n"
            "Synthesize recurring patterns and return only the required JSON object."
        )

    @classmethod
    def _render_observation(
        cls,
        position: int,
        record: CoachObservationRecord,
    ) -> str:
        observation = record.observation
        return "\n".join(
            (
                f"Observation {position}",
                f"User turn ID: {record.user_turn_id}",
                f"Opponent turn ID: {record.opponent_turn_id}",
                "Strengths:",
                cls._render_items(observation.strengths),
                "Weaknesses:",
                cls._render_items(observation.weaknesses),
                "Missed opportunities:",
                cls._render_items(observation.missed_opportunities),
                "Risk signals:",
                cls._render_items(observation.risk_signals),
                f"Confidence: {observation.confidence}",
            )
        )

    @staticmethod
    def _render_items(items: list[str]) -> str:
        if not items:
            return "- None recorded."
        return "\n".join(f"- {item}" for item in items)
