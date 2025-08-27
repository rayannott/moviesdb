from datetime import datetime
from typing import NamedTuple

from supabase import Client


class Book(NamedTuple):
    """A class for comparing."""

    dt_read: datetime  # this is the id, primary key
    title: str  # this is the id, primary key
    author: str | None
    rating: float | None
    n_pages: int | None
    body: str

    def __repr__(self) -> str:
        return f"{self.title} from {self.dt_read:%d.%m.%Y}"

    @classmethod
    def from_sql_row(cls, row: dict) -> "Book":
        return cls(
            dt_read=datetime.fromisoformat(row["dt_read"]),
            title=row["title"],
            author=row.get("author"),
            rating=row.get("rating"),
            n_pages=row.get("n_pages"),
            body=row["body"],
        )

    def to_row(self) -> dict:
        return {
            "dt_read": self.dt_read.isoformat(),
            "title": self.title,
            "author": self.author,
            "rating": self.rating,
            "n_pages": self.n_pages,
            "body": self.body,
        }

    def to_row_values_only(self) -> list:
        return [
            self.title,
            self.dt_read,
            self.rating,
            self.author,
            self.n_pages,
            self.body,
        ]

    def insert(self, client: Client):
        client.table("books").insert(self.to_row()).execute()

    def update(self, client: Client):
        _ = (
            client.table("books")
            .update(self.to_row())
            .match({"title": self.title, "dt_read": self.dt_read.isoformat()})
            .execute()
        )
