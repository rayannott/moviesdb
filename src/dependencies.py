from typing import cast

import boto3
from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Callable, Configuration, Singleton
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from src.models.bot_guest_entry import BotGuestEntry
from src.models.chatbot_memory_entry import ChatbotMemoryEntry
from src.models.entry import Entry
from src.models.watchlist_entry import WatchlistEntry
from src.repos.bot_guests import BotGuestsRepo
from src.repos.chatbot_memory import ChatbotMemoryEntriesRepo
from src.repos.entries import EntriesRepo
from src.repos.watchlist_entries import WatchlistEntriesRepo
from src.services.chatbot_service import ChatbotService
from src.services.entry_service import EntryService
from src.services.export_service import ExportService
from src.services.guest_service import GuestService
from src.services.image_service import ImageService
from src.services.watchlist_service import WatchlistService
from src.settings import Settings


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
    watchlist_entries_repo = Singleton(
        WatchlistEntriesRepo,
        client=mongo_client,
        model_cls=WatchlistEntry,
    )
    chatbot_memory_repo = Singleton(
        ChatbotMemoryEntriesRepo,
        client=mongo_client,
        model_cls=ChatbotMemoryEntry,
    )
    bot_guests_repo = Singleton(
        BotGuestsRepo,
        client=mongo_client,
        model_cls=BotGuestEntry,
    )

    # Services
    entry_service = Singleton(
        EntryService,
        entries_repo=entries_repo,
        watchlist_repo=watchlist_entries_repo,
    )
    watchlist_service = Singleton(
        WatchlistService,
        watchlist_repo=watchlist_entries_repo,
        entries_repo=entries_repo,
    )
    chatbot_service = Singleton(
        ChatbotService,
        memory_repo=chatbot_memory_repo,
    )
    guest_service = Singleton(
        GuestService,
        guests_repo=bot_guests_repo,
    )
    export_service = Singleton(
        ExportService,
        entries_repo=entries_repo,
        watchlist_repo=watchlist_entries_repo,
    )

    # AWS
    s3_client = Singleton(
        boto3.client,
        "s3",
        region_name="eu-north-1",
        aws_access_key_id=config.aws_access_key_id,
        aws_secret_access_key=config.aws_secret_access_key,
    )
    image_service = Singleton(
        ImageService,
        s3_client=s3_client,
        bucket_name=config.aws_images_series_bucket_name,
        entry_service=entry_service,
    )
