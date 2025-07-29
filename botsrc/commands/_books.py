import logging

import telebot

from botsrc.utils import format_book
from src.obj.books_mode import BooksMode
from src.parser import PositionalArgs, Flags

logger = logging.getLogger(__name__)


def books(
    message: telebot.types.Message,
    bot: telebot.TeleBot,
    pos: PositionalArgs,
    flags: Flags,
):
    # TODO: implement other logic (n books, find, ...)
    client = BooksMode.get_client()
    books = BooksMode.get_books(client)
    if not books:
        bot.reply_to(message, "No books found.")
        return
    if pos:
        books = [book for book in books if pos[0].lower() in book.title.lower()]
    books.sort(key=lambda b: b.dt_read)
    last_5 = books[-5:]
    formatted_books = f"Last {len(last_5)} books:\n" + "\n".join(
        format_book(
            book,
            "verbose" in flags,
        )
        for book in last_5
    )
    formatted_books = "No books found." if len(last_5) == 0 else formatted_books
    bot.send_message(message.chat.id, formatted_books)
