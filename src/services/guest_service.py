from src.repos.bot_guests import BotGuestsRepo


class GuestService:
    """Business logic for bot guest management."""

    def __init__(self, guests_repo: BotGuestsRepo) -> None:
        self._guests_repo = guests_repo

    def get_guests(self) -> list[str]:
        return self._guests_repo.get_usernames()

    def add_guest(self, username: str) -> None:
        self._guests_repo.add_guest(username)

    def remove_guest(self, username: str) -> bool:
        return self._guests_repo.remove_guest(username)

    def is_guest(self, username: str) -> bool:
        return username in self.get_guests()
