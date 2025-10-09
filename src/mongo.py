from functools import lru_cache

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from src.obj.entry import Entry
from src.obj.watch_list import WatchList
from src.utils.env import MONGODB_PASSWORD


class Mongo:
    @staticmethod
    @lru_cache(maxsize=1)
    def client() -> MongoClient:
        uri = f"mongodb+srv://rayannott:{MONGODB_PASSWORD}@moviesseries.7g8z1if.mongodb.net/?retryWrites=true&w=majority&appName=MoviesSeries"
        return MongoClient(uri, server_api=ServerApi("1"))

    @classmethod
    def entries(cls) -> Collection:
        return cls.client().db.entries

    @classmethod
    def watchlist(cls) -> Collection:
        return cls.client().db.watchlist

    @classmethod
    def aimemory(cls) -> Collection:
        return cls.client().db.aimemory

    @classmethod
    def botguests(cls) -> Collection:
        return cls.client().db.botguests

    @classmethod
    def update_entry(cls, entry: Entry):
        cls.entries().replace_one({"_id": entry._id}, entry.as_dict())

    @classmethod
    def add_entry(cls, entry: Entry):
        new_id = cls.entries().insert_one(entry.as_dict()).inserted_id
        entry._id = new_id

    @classmethod
    def delete_entry(cls, oid: ObjectId) -> bool:
        return cls.entries().delete_one({"_id": oid}).deleted_count == 1

    @classmethod
    def add_watchlist_entry(cls, title: str, is_series: bool):
        cls.watchlist().insert_one({"title": title, "is_series": is_series})

    @classmethod
    def delete_watchlist_entry(cls, title: str, is_series: bool) -> bool:
        return (
            cls.watchlist()
            .delete_one({"title": title, "is_series": is_series})
            .deleted_count
            == 1
        )

    @classmethod
    def load_entries(cls) -> list[Entry]:
        data = cls.entries().find()
        return [Entry.from_dict(entry) for entry in data]

    @classmethod
    def load_watch_list(cls) -> WatchList:
        data = cls.watchlist().find()
        return WatchList([(item["title"], item["is_series"]) for item in data])

    @classmethod
    def load_aimemory_items(cls) -> list[tuple[str, str]]:
        return [(str(mem["_id"]), mem["item"]) for mem in cls.aimemory().find()]

    @classmethod
    def add_aimemory_item(cls, mem: str) -> ObjectId:
        return cls.aimemory().insert_one({"item": mem}).inserted_id

    @classmethod
    def delete_aimemory_item(cls, oid: ObjectId) -> bool:
        return cls.aimemory().delete_one({"_id": oid}).deleted_count == 1

    @classmethod
    def load_bot_guests(cls) -> list[str]:
        return [guest["username"] for guest in cls.botguests().find()]

    @classmethod
    def add_bot_guest(cls, username: str) -> ObjectId:
        return cls.botguests().insert_one({"username": username}).inserted_id

    @classmethod
    def remove_bot_guest(cls, username: str) -> bool:
        return cls.botguests().delete_one({"username": username}).deleted_count == 1
