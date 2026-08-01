from collections.abc import Iterator


class FakeLLMProvider:
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float | None = None,
    ) -> str:
        if system_prompt.startswith(
            "You generate structured negotiation scenario details"
        ):
            return (
                '{"industry": "Technology", '
                '"opponent_role": "Recruiter", '
                '"objective": "Improve the total compensation package while '
                'preserving the offer.", '
                '"personality": "Professional, pragmatic, and attentive to '
                'internal compensation bands.", '
                '"negotiation_style": "Collaborative and evidence-driven", '
                '"constraints": ["Compensation must remain within the approved '
                'level range."], '
                '"hidden_context": ["There is limited flexibility in base salary '
                'but more flexibility in equity."], '
                '"walk_away_conditions": ["The candidate makes an ultimatum or '
                'rejects all package components."]}'
            )

        if system_prompt.startswith("You are an expert negotiation memory analyst"):
            session_count = 2
            history_prefix = "Persisted artifacts from "
            if user_prompt.startswith(history_prefix):
                rendered_count = user_prompt.removeprefix(history_prefix).partition(
                    " "
                )[0]
                if rendered_count.isdigit():
                    session_count = int(rendered_count)
            return (
                '{"stable_strengths": ["Uses conditional concessions."], '
                '"stable_weaknesses": ["Anchors before gathering information."], '
                '"improving_skills": ["Concession planning"], '
                '"persistent_risks": ["Makes unilateral concessions."], '
                '"highest_priority_skill": "Diagnostic questioning", '
                '"next_session_drill": "Practice five discovery questions.", '
                '"progress_summary": "Concession planning is improving, but discovery must become more consistent.", '
                f'"sessions_analyzed": {session_count}, '
                '"confidence": "medium"}'
            )

        if system_prompt.startswith("You are an expert negotiation strategy advisor"):
            return (
                '{"primary_objective": '
                '"Make concessions conditional on reciprocal value.", '
                '"expected_outcome": '
                '"Each concession advances the user toward a balanced agreement.", '
                '"prioritized_tactics": ['
                '{"priority": 1, '
                '"title": "Trade rather than concede", '
                '"rationale": "Conditional trades protect value.", '
                '"actions": ["Request reciprocal value for every concession."], '
                '"example_language": ["I can agree to that if you can improve the '
                'payment terms."], '
                '"success_indicator": "Every concession receives reciprocal value."}, '
                '{"priority": 2, '
                '"title": "Prepare concession boundaries", '
                '"rationale": "Defined boundaries prevent reactive concessions.", '
                '"actions": ["Set concession limits before negotiating."], '
                '"example_language": ["That is the furthest I can move on price."], '
                '"success_indicator": "No unplanned concessions are made."}], '
                '"long_term_skills": ["Concession planning"], '
                '"preparation_checklist": ["Define reciprocal asks."], '
                '"avoid_next_time": ["Do not concede without receiving value."], '
                '"confidence": "low"}'
            )

        if system_prompt.startswith("You are an expert negotiation debrief analyst"):
            return (
                '{"repeated_strengths": [], '
                '"repeated_weaknesses": [], '
                '"key_missed_opportunities": [], '
                '"recurring_risks": [], '
                '"overall_assessment": '
                '"There is not enough evidence for a detailed assessment.", '
                '"confidence": "low"}'
            )

        if system_prompt.startswith("You are an expert negotiation coach"):
            return (
                '{"strengths": [], '
                '"weaknesses": [], '
                '"missed_opportunities": [], '
                '"risk_signals": [], '
                '"confidence": "low"}'
            )

        if system_prompt.startswith("You extract structured negotiation state"):
            return (
                '{"latest_user_position": null, '
                '"latest_opponent_position": null, '
                '"agreements": [], '
                '"open_topics": [], '
                '"unresolved_items": [], '
                '"negotiation_stage": "opening"}'
            )

        return (
            "I understand your position, but those terms are difficult for us "
            "to accept."
        )

    def stream(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float | None = None,
    ) -> Iterator[str]:
        response = self.generate(
            system_prompt,
            user_prompt,
            temperature=temperature,
        )
        chunk_size = 16
        for start in range(0, len(response), chunk_size):
            yield response[start : start + chunk_size]
