class FakeLLMProvider:
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        return (
            "I understand your position, but those terms are difficult for us "
            "to accept."
        )
