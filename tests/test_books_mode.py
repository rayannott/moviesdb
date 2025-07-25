import pytest
from supabase import create_client, Client

from src.utils.env import SUPABASE_API_KEY, SUPABASE_PROJECT_ID
from src.obj.books_mode import BooksMode, Book


@pytest.fixture(scope="session")
def supabase_client() -> Client:
    """Fixture to create a Supabase client."""
    return create_client(
        f"https://{SUPABASE_PROJECT_ID}.supabase.co",
        SUPABASE_API_KEY,
    )


@pytest.fixture
def books(supabase_client: Client) -> list[Book]:
    """Fixture to get books from the Supabase client."""
    return BooksMode.get_books(supabase_client)


def test_get_books(books: list[Book]):
    assert isinstance(books, list), "Books should be a list."
    assert all(isinstance(book, Book) for book in books), (
        "All items should be Book instances."
    )
    assert len(books) > 0, "There should be at least one book in the list."
