class UnsupportedScenarioDifficultyError(Exception):
    def __init__(self, difficulty: object) -> None:
        self.difficulty = difficulty
        super().__init__(f"Unsupported scenario difficulty: '{difficulty}'.")
