import logging

import telebot

from botsrc.utils import format_book
from src.obj.books_mode import BooksMode
from src.parser import PositionalArgs, KeywordArgs, Flags

logger = logging.getLogger(__name__)


def books(
    message: telebot.types.Message,
    bot: telebot.TeleBot,
    flags: Flags,
):
    # TODO: implement other logic (n books, find, ...)
    client = BooksMode.get_client()
    books = BooksMode.get_books(client)
    if not books:
        bot.reply_to(message, "No books found.")
        return
    books.sort(key=lambda b: b.dt_read)
    formatted_books = "Last 5 books:\n" + "\n".join(
        format_book(
            book,
            "verbose" in flags,
        )
        for book in books[-5:]
    )
    bot.send_message(message.chat.id, formatted_books)
