# from bson import ObjectId
# from pymongo.collection import Collection
# from pymongo.mongo_client import MongoClient

from src.models.entry import Entry
from src.repos.mongo_base import MongoRepo


class EntriesRepo(MongoRepo[Entry]):
    pass
