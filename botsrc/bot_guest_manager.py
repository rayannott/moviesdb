from src.mongo import Mongo


class GuestManager:
    def add(self, username: str):
        Mongo.add_bot_guest(username)

    def remove(self, username: str) -> bool:
        return Mongo.remove_bot_guest(username)

    @property
    def guests(self) -> list[str]:
        return Mongo.load_bot_guests()

    def __contains__(self, username: str) -> bool:
        return username in self.guests
