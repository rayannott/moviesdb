from src.models.bot_guest_entry import BotGuestEntry
from src.repos.mongo_base import MongoRepo


class BotGuestsRepo(MongoRepo[BotGuestEntry]):
    collection_name = "botguests"

    def add_guest(self, username: str) -> BotGuestEntry:
        entry = BotGuestEntry(username=username)
        return self.add(entry)

    def remove_guest(self, username: str) -> bool:
        return self.delete_by(username=username)

    def get_usernames(self) -> list[str]:
        return [e.username for e in self.get_all()]
