from app.domains.debrief.models import NegotiationDebriefRecord


class StrategyPromptBuilder:
    def build_system_prompt(self) -> str:
        return """You are an expert negotiation strategy advisor.

Create prioritized, detailed, and actionable recommendations for what the user
should do differently in a future negotiation.
Return exactly one valid JSON object with this structure:
{
  "primary_objective": "",
  "expected_outcome": "",
  "prioritized_tactics": [
    {
      "priority": 1,
      "title": "",
      "rationale": "",
      "actions": [],
      "example_language": [],
      "success_indicator": ""
    }
  ],
  "long_term_skills": [],
  "preparation_checklist": [],
  "avoid_next_time": [],
  "confidence": "low"
}

Rules
- Rely only on the supplied persisted negotiation debrief.
- Do not invent negotiation events, evidence, or user behavior.
- Make every tactic actionable rather than merely descriptive.
- Priorities must be positive, unique integers.
- Provide concrete actions, example language, and a measurable success indicator.
- Keep long-term skills more general and fewer than negotiation-specific tactics.
- Make preparation and avoidance guidance concise and practical.
- Return only JSON, with no Markdown fences, labels, explanations, or commentary.
"""

    def build_user_prompt(
        self,
        record: NegotiationDebriefRecord,
    ) -> str:
        debrief = record.debrief
        return "\n".join(
            (
                "Persisted negotiation debrief",
                "",
                f"Debrief ID: {record.id}",
                f"Session ID: {record.session_id}",
                f"Observation count: {record.observation_count}",
                "Repeated strengths:",
                self._render_items(debrief.repeated_strengths),
                "Repeated weaknesses:",
                self._render_items(debrief.repeated_weaknesses),
                "Key missed opportunities:",
                self._render_items(debrief.key_missed_opportunities),
                "Recurring risks:",
                self._render_items(debrief.recurring_risks),
                f"Overall assessment: {debrief.overall_assessment}",
                f"Debrief confidence: {debrief.confidence}",
                "",
                (
                    "Create the required forward-looking negotiation strategy and "
                    "return only the JSON object."
                ),
            )
        )

    @staticmethod
    def _render_items(items: list[str]) -> str:
        if not items:
            return "- None recorded."
        return "\n".join(f"- {item}" for item in items)
