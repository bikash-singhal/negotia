class MissingLLMProviderTextError(Exception):
    def __init__(self) -> None:
        super().__init__("The LLM provider response did not contain non-blank text.")
