from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher


class PasswordHasher:
    def __init__(self, rounds: int = 12) -> None:
        self._password_hash = PasswordHash((BcryptHasher(rounds=rounds),))

    def hash(self, password: str) -> str:
        return self._password_hash.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        return self._password_hash.verify(password, password_hash)
