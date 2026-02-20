from typing import cast

import dotenv
from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Configuration, Singleton, Callable
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from src.models.entry import Entry
from src.repos.chatbot_memory import ChatbotMemoryEntriesRepo
from src.repos.entries import EntriesRepo
from src.repos.watchlist_entries import WatchlistEntriesRepo
from src.settings import Settings

dotenv.load_dotenv()


def build_mongo_uri(prefix: str, password: str, suffix: str) -> str:
    return f"{prefix}:{password}@{suffix}"


class Container(DeclarativeContainer):
    config = Configuration()
    config.from_pydantic(Settings())  # type: ignore
    config = cast(Settings, config)  # type: ignore[assignment]
    mongo_uri = Callable(
        build_mongo_uri,
        prefix=config.mongodb_prefix,
        password=config.mongodb_password,
        suffix=config.mongodb_suffix,
    )
    mongo_client = Singleton(
        MongoClient,
        mongo_uri(),
        server_api=ServerApi("1"),
    )

    entries_repo = Singleton(
        EntriesRepo,
        client=mongo_client,
        model_cls=Entry,
    )
    # watchlist_entries_repo = Singleton(WatchlistEntriesRepo, mongo_client)
    # chatbot_memory_entries_repo = Singleton(ChatbotMemoryEntriesRepo, mongo_client)
