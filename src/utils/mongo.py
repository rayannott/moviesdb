import os

import dotenv

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.collection import Collection

from src.obj.entry import Entry

dotenv.load_dotenv()


MONGODB_PASSWORD = os.environ.get("MONGODB_PASSWORD")
assert MONGODB_PASSWORD is not None


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
    def update_entry(_):
        ...

    @staticmethod
    def add_entry(entry: Entry):
        new_id = entries().insert_one(entry.as_dict()).inserted_id
        entry._id = new_id

    @staticmethod
    def delete_entry(_):
        ...

    @staticmethod
    def add_watchlist_entry(_):
        ...

    @staticmethod
    def delete_watchlist_entry(_):
        ...

    @staticmethod
    def add_aimemory_item(_):
        ...

    @staticmethod
    def delete_aimemory_item(_):
        ...
