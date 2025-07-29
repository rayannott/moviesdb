import pytest
from supabase import Client
from pymongo import MongoClient

from src.obj.books_mode import BooksMode, Book
from src.mongo import Mongo


@pytest.fixture(scope="session")
def supabase_client() -> Client:
    """Fixture to create a Supabase client."""
    return BooksMode.get_client()


@pytest.fixture
def books(supabase_client: Client) -> list[Book]:
    """Fixture to get books from the Supabase client."""
    return BooksMode.get_books(supabase_client)


@pytest.fixture(scope="session")
def mongo_client() -> MongoClient:
    """Fixture to create a MongoDB client."""
    return Mongo.client()
