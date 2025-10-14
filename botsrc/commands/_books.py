import telebot
from telebot import types
from loguru import logger

from botsrc.utils import format_book
from src.apps import BooksApp
from src.parser import Flags, PositionalArgs


def books(
    message: types.Message,
    bot: telebot.TeleBot,
    pos: PositionalArgs,
    flags: Flags,
):
    # TODO: implement other logic (n books, find, ...)
    client = BooksApp.get_client()
    books = BooksApp.get_books(client)
    logger.debug(f"Fetched {len(books)} books from the database")
    if not books:
        bot.reply_to(message, "No books found.")
        logger.warning("No books found")
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
    logger.debug(f"Displayed {len(last_5)} books")
