class FakeLLMProvider:
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
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
