class FakeLLMProvider:
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
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
