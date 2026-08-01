class UsernameAlreadyExistsError(Exception):
    def __init__(self, username: str) -> None:
        self.username = username
        super().__init__(f"Username '{username}' is already registered.")


class InvalidCredentialsError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid username or password.")


class InvalidAccessTokenError(Exception):
    def __init__(self) -> None:
        super().__init__("Could not validate authentication credentials.")


class ExpiredAccessTokenError(InvalidAccessTokenError):
    pass
