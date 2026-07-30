class FakeLLMProvider:
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
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
