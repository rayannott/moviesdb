from .mongo_base import EntryBaseModel


class WatchlistEntry(EntryBaseModel):
    title: str
    is_series: bool
