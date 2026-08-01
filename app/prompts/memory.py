from app.domains.debrief.models import NegotiationDebriefRecord
from app.domains.strategy.models import NegotiationStrategyRecord


class MemoryPromptBuilder:
    def build_system_prompt(self) -> str:
        return """You are an expert negotiation memory analyst.

Build a compact coaching profile of cross-session patterns by comparing the
supplied persisted negotiation debriefs and strategies in chronological order
from oldest to newest.

Trend definitions:
- A stable strength is useful behavior demonstrated repeatedly across sessions.
- A stable weakness is a weakness demonstrated repeatedly across sessions.
- An improving skill was previously weak or prioritized and is meaningfully better
  in newer sessions.
- A persistent risk is harmful behavior that continues despite prior strategy
  recommendations.
- A regression is behavior that was previously stronger and later became worse.

Rules:
- Treat each chronologically labelled session as distinct evidence.
- Do not treat one isolated observation as a recurring pattern.
- Do not claim improvement or regression without chronological evidence.
- With only two sessions, use cautious language for any trend claim.
- Do not invent evidence, behavior, progress, risks, or recommendations.
- Base every conclusion only on the supplied debrief and strategy artifacts.
- Semantically synthesize equivalent observations instead of copying or
  concatenating per-session wording.
- Merge overlapping concepts into one concise, actionable coaching statement.
- Do not repeat the same concept across stable weaknesses, persistent risks, and
  highest-priority skill unless the evidence makes that overlap necessary.
- Select exactly one highest-leverage skill to practice next.
- Provide exactly one concrete next-session drill.
- Summarize both supported progress and remaining work concisely.
- stable_strengths and stable_weaknesses contain at most 3 strings each.
- improving_skills and persistent_risks contain at most 2 strings each.
- Set sessions_analyzed to the exact number of supplied sessions.
- Use empty arrays when the artifacts do not support a category.

Output requirements:
- You MUST return exactly one valid JSON object and nothing else.
- Return JSON only.
- DO NOT wrap the JSON in Markdown or code fences.
- DO NOT include commentary, labels, or explanations before or after it.
- Include every required key exactly once and do not include additional keys.
- stable_strengths, stable_weaknesses, improving_skills, and persistent_risks MUST be arrays of concise JSON strings.
- highest_priority_skill, next_session_drill, progress_summary, and confidence MUST be JSON strings.
- sessions_analyzed MUST be a positive JSON integer and confidence MUST be a JSON string.

Return exactly this JSON structure, replacing only its values:
{
  "stable_strengths": [],
  "stable_weaknesses": [],
  "improving_skills": [],
  "persistent_risks": [],
  "highest_priority_skill": "",
  "next_session_drill": "",
  "progress_summary": "",
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
                len(debrief_records),
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
        session_count: int,
        debrief_record: NegotiationDebriefRecord,
        strategy_record: NegotiationStrategyRecord,
    ) -> str:
        debrief = debrief_record.debrief
        strategy = strategy_record.strategy
        if session_count == 1:
            session_label = "Session 1 — oldest and newest"
        elif position == 1:
            session_label = "Session 1 — oldest"
        elif position == session_count:
            session_label = f"Session {position} — newest"
        else:
            session_label = f"Session {position}"

        return "\n".join(
            (
                session_label,
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
