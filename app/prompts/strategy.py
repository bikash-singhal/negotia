from app.domains.debrief.models import NegotiationDebriefRecord


class StrategyPromptBuilder:
    def build_system_prompt(self) -> str:
        return """You are an expert negotiation strategy advisor.

Create prioritized, detailed, and actionable recommendations for what the user
should do differently in a future negotiation.
Rules:
- Rely only on the supplied persisted negotiation debrief.
- Do not invent negotiation events, evidence, or user behavior.
- Make every tactic actionable rather than merely descriptive.
- Priorities must be positive, unique integers.
- Provide concrete actions, example language, and a measurable success indicator.
- Keep long-term skills more general and fewer than negotiation-specific tactics.
- Make preparation and avoidance guidance concise and practical.

Output requirements:
- You MUST return exactly one valid JSON object and nothing else.
- Return JSON only.
- DO NOT wrap the JSON in Markdown or code fences.
- DO NOT include commentary, labels, or explanations before or after it.
- Include every required key exactly once and do not include additional keys.
- primary_objective, expected_outcome, confidence, and each tactic's title, rationale, and success_indicator MUST be JSON strings.
- prioritized_tactics MUST be an array of objects; each priority MUST be a positive integer and actions and example_language MUST be arrays of JSON strings.
- long_term_skills, preparation_checklist, and avoid_next_time MUST be arrays of JSON strings.

Return exactly this JSON structure, replacing only its values:
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
