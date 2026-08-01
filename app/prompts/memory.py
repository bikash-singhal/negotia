from app.domains.debrief.models import NegotiationDebriefRecord
from app.domains.strategy.models import NegotiationStrategyRecord


class MemoryPromptBuilder:
    def build_system_prompt(self) -> str:
        return """You are an expert negotiation memory analyst.

Identify cross-session patterns using only the supplied persisted negotiation
debriefs and strategies.
Rules:
- Treat each labelled session as distinct evidence.
- Do not treat one isolated observation as a recurring pattern.
- Do not invent evidence, behavior, progress, risks, or recommendations.
- Base every conclusion only on the supplied debrief and strategy artifacts.
- Make focus areas and drills concise and actionable.
- Set sessions_analyzed to the exact number of supplied sessions.
- Use empty arrays when the artifacts do not support a category.

Output requirements:
- You MUST return exactly one valid JSON object and nothing else.
- Return JSON only.
- DO NOT wrap the JSON in Markdown or code fences.
- DO NOT include commentary, labels, or explanations before or after it.
- Include every required key exactly once and do not include additional keys.
- recurring_strengths, recurring_weaknesses, improving_skills, persistent_risks, priority_focus_areas, and recommended_drills MUST be arrays of JSON strings.
- sessions_analyzed MUST be a positive JSON integer and confidence MUST be a JSON string.

Return exactly this JSON structure, replacing only its values:
{
  "recurring_strengths": [],
  "recurring_weaknesses": [],
  "improving_skills": [],
  "persistent_risks": [],
  "priority_focus_areas": [],
  "recommended_drills": [],
  "sessions_analyzed": 2,
  "confidence": "low"
}
"""

    def build_user_prompt(
        self,
        debrief_records: list[NegotiationDebriefRecord],
        strategy_records: list[NegotiationStrategyRecord],
    ) -> str:
        strategies_by_session = {
            record.session_id: record for record in strategy_records
        }
        rendered_sessions = "\n\n".join(
            self._render_session(
                position,
                debrief_record,
                strategies_by_session[debrief_record.session_id],
            )
            for position, debrief_record in enumerate(debrief_records, start=1)
        )
        return (
            f"Persisted artifacts from {len(debrief_records)} negotiation sessions\n\n"
            f"{rendered_sessions}\n\n"
            "Identify supported cross-session patterns and return only the required "
            "JSON object."
        )

    @classmethod
    def _render_session(
        cls,
        position: int,
        debrief_record: NegotiationDebriefRecord,
        strategy_record: NegotiationStrategyRecord,
    ) -> str:
        debrief = debrief_record.debrief
        strategy = strategy_record.strategy
        return "\n".join(
            (
                f"Session {position}",
                f"Session ID: {debrief_record.session_id}",
                "",
                "Persisted debrief",
                "Repeated strengths:",
                cls._render_items(debrief.repeated_strengths),
                "Repeated weaknesses:",
                cls._render_items(debrief.repeated_weaknesses),
                "Key missed opportunities:",
                cls._render_items(debrief.key_missed_opportunities),
                "Recurring risks:",
                cls._render_items(debrief.recurring_risks),
                f"Overall assessment: {debrief.overall_assessment}",
                f"Debrief confidence: {debrief.confidence}",
                "",
                "Persisted strategy",
                f"Primary objective: {strategy.primary_objective}",
                f"Expected outcome: {strategy.expected_outcome}",
                "Prioritized tactics:",
                cls._render_tactics(strategy_record),
                "Long-term skills:",
                cls._render_items(strategy.long_term_skills),
                "Preparation checklist:",
                cls._render_items(strategy.preparation_checklist),
                "Avoid next time:",
                cls._render_items(strategy.avoid_next_time),
                f"Strategy confidence: {strategy.confidence}",
            )
        )

    @classmethod
    def _render_tactics(cls, record: NegotiationStrategyRecord) -> str:
        tactics = record.strategy.prioritized_tactics
        if not tactics:
            return "- None recorded."
        return "\n".join(
            (
                f"- Priority {tactic.priority}: {tactic.title}\n"
                f"  Rationale: {tactic.rationale}\n"
                f"  Actions: {cls._render_inline_items(tactic.actions)}\n"
                "  Example language: "
                f"{cls._render_inline_items(tactic.example_language)}\n"
                f"  Success indicator: {tactic.success_indicator}"
            )
            for tactic in tactics
        )

    @staticmethod
    def _render_items(items: list[str]) -> str:
        if not items:
            return "- None recorded."
        return "\n".join(f"- {item}" for item in items)

    @staticmethod
    def _render_inline_items(items: list[str]) -> str:
        if not items:
            return "None recorded."
        return "; ".join(items)
