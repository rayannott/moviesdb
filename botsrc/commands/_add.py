from datetime import datetime

import telebot
from telebot import types
from loguru import logger

from botsrc.utils import (
    format_entry,
    format_title,
    process_watch_again_tag_on_add_entry,
    process_watch_list_on_add_entry,
)
from src.mongo import Mongo
from src.obj.entry import Entry, MalformedEntryException, Type
from src.parser import Flags, KeywordArgs, PositionalArgs


def text(message: types.Message) -> str:
    return message.text if message.text is not None else ""


def get_movie_type_kb() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("Movie"), types.KeyboardButton("Series")
    )
    return kb


def get_confirmation_kb() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("Confirm"), types.KeyboardButton("Cancel")
    )
    return kb


def get_skip_kb(extra_buttons: list[str] = []) -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True, row_width=1 + len(extra_buttons)
    )
    kb.add(*(types.KeyboardButton(btn) for btn in ["Skip"] + extra_buttons))
    return kb


def add(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: types.Message,
):
    # Start the process by asking for the movie title
    if not (pos or flags or kwargs):
        sent = bot.send_message(message.chat.id, "Please enter the title:")
        logger.debug("multistep add entry initiated")
        bot.register_next_step_handler(sent, _get_title, bot=bot)
        return
    try:
        title = kwargs["title"]
        rating = Entry.parse_rating(kwargs["rating"])
        type_ = Entry.parse_type(kwargs.get("type", "movie"))
        date = Entry.parse_date(kwargs.get("date", ""))
        notes = kwargs.get("notes", "")
    except MalformedEntryException as e:
        bot.reply_to(message, str(e))
        logger.debug(f"malformed entry while adding entry {title}", exc_info=e)
        return
    except KeyError:
        bot.reply_to(message, "Need to specify title and rating")
        logger.debug("missing title or rating while adding entry", exc_info=True)
        return
    entry = Entry(None, title, rating, date, type_, notes)
    Mongo.add_entry(entry)
    bot.send_message(
        message.chat.id, f"Entry added:\n{format_entry(entry, True, True)}"
    )
    logger.debug(f"added entry {entry}")
    if msg := process_watch_list_on_add_entry(entry):
        bot.send_message(message.chat.id, msg)


def _get_title(message: types.Message, bot: telebot.TeleBot):
    title = text(message)
    if not title:
        bot.reply_to(
            message,
            "You must specify a title.",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        logger.debug("no title specified")
        return
    watch_list = Mongo.load_watch_list()
    is_series = watch_list.get(title)
    extra_note = (
        f"Note that {format_title(title, is_series)} will be removed from watch list if you proceed to add it. "
        if is_series is not None
        else ""
    )
    bot.send_message(message.chat.id, f"{extra_note}Now, please rate it:")
    logger.debug("asking for rating")
    bot.register_next_step_handler_by_chat_id(
        message.chat.id, _get_rating, bot=bot, title=title
    )


def _get_rating(message: types.Message, bot: telebot.TeleBot, title: str):
    try:
        rating = Entry.parse_rating(text(message))
    except MalformedEntryException as e:
        bot.reply_to(
            message,
            f"{e}",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        logger.debug("malformed rating", exc_info=e)
        return

    bot.send_message(
        message.chat.id,
        "What type of entry is it? (Movie or Series)",
        reply_markup=get_movie_type_kb(),
    )
    logger.debug("asking for type")
    bot.register_next_step_handler_by_chat_id(
        message.chat.id, _get_type, bot=bot, title=title, rating=rating
    )


def _get_type(
    message: types.Message, bot: telebot.TeleBot, title: str, rating: int
):
    try:
        type_ = Entry.parse_type(text(message))
    except MalformedEntryException as e:
        bot.send_message(
            message.chat.id,
            f"{e}",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        logger.debug("malformed type", exc_info=e)
        return
    bot.send_message(
        message.chat.id,
        "Please enter the date (dd.mm.yyyy or 'today' or nothing):",
        reply_markup=get_skip_kb(extra_buttons=["Today"]),
    )
    logger.debug("asking for date")
    bot.register_next_step_handler_by_chat_id(
        message.chat.id, _get_date, bot=bot, title=title, rating=rating, type_=type_
    )


def _get_date(
    message: types.Message,
    bot: telebot.TeleBot,
    title: str,
    rating: int,
    type_: Type,
):
    try:
        date = Entry.parse_date(
            text(message).lower() if text(message).lower() != "skip" else ""
        )
    except MalformedEntryException as e:
        bot.reply_to(
            message,
            f"Invalid date: {e}. Please use the format dd.mm.yyyy or 'today'.",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        logger.debug("malformed date", exc_info=e)
        return

    bot.send_message(
        message.chat.id,
        "Do you want to add any notes? (Optional):",
        reply_markup=get_skip_kb(),
    )
    logger.debug("asking for notes")
    bot.register_next_step_handler_by_chat_id(
        message.chat.id,
        _get_notes,
        bot=bot,
        title=title,
        rating=rating,
        type_=type_,
        date=date,
    )


def _get_notes(
    message: types.Message,
    bot: telebot.TeleBot,
    title: str,
    rating: int,
    type_: Type,
    date: datetime | None,
):
    notes = text(message) if text(message).lower() != "skip" else ""

    entry = Entry(None, title, rating, date, type_, notes)
    bot.send_message(
        message.chat.id,
        f"Thank you! Let's confirm the details:\n{format_entry(entry, True)}",
        reply_markup=get_confirmation_kb(),
    )
    logger.debug("asking for confirmation")
    bot.register_next_step_handler_by_chat_id(
        message.chat.id,
        _confirm_add,
        bot=bot,
        entry=entry,
    )


def _confirm_add(message: types.Message, bot: telebot.TeleBot, entry: Entry):
    if text(message).lower() != "confirm":
        bot.send_message(
            message.chat.id,
            "Entry creation canceled.",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        logger.debug("entry creation canceled")
        return
    Mongo.add_entry(entry)
    bot.send_message(
        message.chat.id,
        f"Entry added:\n{format_entry(entry, True, True)}",
        reply_markup=types.ReplyKeyboardRemove(),
    )
    logger.debug(f"added entry {entry}")
    if msg := process_watch_list_on_add_entry(entry):
        bot.send_message(message.chat.id, msg)
    if msg := process_watch_again_tag_on_add_entry(entry):
        bot.send_message(message.chat.id, msg)
