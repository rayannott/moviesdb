import re

import pytest
from supabase import Client

from src.apps import BooksApp
from src.obj.book import Book


@pytest.fixture(scope="session")
def supabase_client() -> Client:
    """Fixture to create a Supabase client."""
    return BooksApp.get_client()


@pytest.fixture
def books(supabase_client: Client) -> list[Book]:
    """Fixture to get books from the Supabase client."""
    return BooksApp.get_books(supabase_client)


def test_get_books(books: list[Book]):
    assert isinstance(books, list), "Books should be a list."
    assert all(isinstance(book, Book) for book in books), (
        "All items should be Book instances."
    )
    assert len(books) > 0, "There should be at least one book in the list."


def test_db_rows(supabase_client: Client):
    DT_READ_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

    book_rows = supabase_client.table("books").select("*").execute().data
    for book_dict in book_rows:
        assert book_dict["title"], f"Title should not be empty in {book_dict!r}"
        dt_read = book_dict["dt_read"]
        assert DT_READ_RE.match(dt_read), (
            f"Invalid dt_read format: {dt_read} in {book_dict!r}"
        )
        assert book_dict["author"], f"Author should not be empty in {book_dict!r}"
