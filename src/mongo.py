from bson import ObjectId
from pymongo.collection import Collection
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from src.obj.entry import Entry
from src.obj.watch_list import WatchList
from src.utils.env import MONGODB_PASSWORD

uri = f"mongodb+srv://rayannott:{MONGODB_PASSWORD}@moviesseries.7g8z1if.mongodb.net/?retryWrites=true&w=majority&appName=MoviesSeries"
CLIENT = MongoClient(uri, server_api=ServerApi("1"))
CLIENT.admin.command("ping")


# TODO: add types
def entries() -> Collection:
    return CLIENT.db.entries


def watchlist() -> Collection:
    return CLIENT.db.watchlist


def aimemory() -> Collection:
    return CLIENT.db.aimemory


class Mongo:
    # TODO: implement
    @staticmethod
    def update_entry(entry: Entry):
        entries().replace_one({"_id": entry._id}, entry.as_dict())

    @staticmethod
    def add_entry(entry: Entry):
        new_id = entries().insert_one(entry.as_dict()).inserted_id
        entry._id = new_id

    @staticmethod
    def delete_entry(oid: ObjectId) -> bool:
        return entries().delete_one({"_id": oid}).deleted_count == 1

    @staticmethod
    def add_watchlist_entry(title: str, is_series: bool):
        watchlist().insert_one({"title": title, "is_series": is_series})

    @staticmethod
    def delete_watchlist_entry(title: str, is_series: bool) -> bool:
        return (
            watchlist()
            .delete_one({"title": title, "is_series": is_series})
            .deleted_count
            == 1
        )

    @staticmethod
    def load_entries() -> list[Entry]:
        data = entries().find()
        return [Entry.from_dict(entry) for entry in data]

    @staticmethod
    def load_watch_list() -> WatchList:
        data = watchlist().find()
        return WatchList([(item["title"], item["is_series"]) for item in data])

    @staticmethod
    def load_aimemory_items() -> list[tuple[str, str]]:
        return [(str(mem["_id"]), mem["item"]) for mem in aimemory().find()]

    @staticmethod
    def add_aimemory_item(mem: str) -> ObjectId:
        return aimemory().insert_one({"item": mem}).inserted_id

    @staticmethod
    def delete_aimemory_item(oid: ObjectId) -> bool:
        return aimemory().delete_one({"_id": oid}).deleted_count == 1
