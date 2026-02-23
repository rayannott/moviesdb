from src.models.watchlist_entry import WatchlistEntry
from src.repos.mongo_base import MongoRepo


class WatchlistEntriesRepo(MongoRepo[WatchlistEntry]):
    collection_name = "watchlist"

    def add_by_title(self, title: str, is_series: bool) -> WatchlistEntry:
        entry = WatchlistEntry(title=title, is_series=is_series)
        return self.add(entry)

    def delete_by_title(self, title: str, is_series: bool) -> bool:
        return self.delete_by(title=title, is_series=is_series)
