from datetime import datetime

import telebot
from src.obj.entry import Entry, MalformedEntryException, Type
from src.mongo import Mongo
from botsrc.utils import format_entry, process_watch_list_on_add_entry


def text(message: telebot.types.Message) -> str:
    return message.text if message.text is not None else ""


def get_movie_type_kb() -> telebot.types.ReplyKeyboardMarkup:
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        telebot.types.KeyboardButton("Movie"), telebot.types.KeyboardButton("Series")
    )
    return kb


def get_confirmation_kb() -> telebot.types.ReplyKeyboardMarkup:
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        telebot.types.KeyboardButton("Confirm"), telebot.types.KeyboardButton("Cancel")
    )
    return kb


def get_skip_kb(extra_buttons: list[str] = []) -> telebot.types.ReplyKeyboardMarkup:
    kb = telebot.types.ReplyKeyboardMarkup(
        resize_keyboard=True, row_width=1 + len(extra_buttons)
    )
    kb.add(*(telebot.types.KeyboardButton(btn) for btn in ["Skip"] + extra_buttons))
    return kb


def add(message: telebot.types.Message, bot: telebot.TeleBot):
    # Start the process by asking for the movie title
    sent = bot.send_message(message.chat.id, "Please enter the title:")
    bot.register_next_step_handler(sent, _get_title, bot=bot)


def _get_title(message: telebot.types.Message, bot: telebot.TeleBot):
    title = text(message)
    if not title:
        bot.reply_to(
            message,
            "You must specify a title.",
            reply_markup=telebot.types.ReplyKeyboardRemove(),
        )
        return
    extra_note = (
        "Note that it will be removed from watch list if you proceed to add it. "
        if title in Mongo.load_watch_list()
        else ""
    )
    bot.send_message(message.chat.id, f"{extra_note}Now, please rate it:")
    bot.register_next_step_handler_by_chat_id(
        message.chat.id, _get_rating, bot=bot, title=title
    )


def _get_rating(message: telebot.types.Message, bot: telebot.TeleBot, title: str):
    try:
        rating = Entry.parse_rating(text(message))
    except MalformedEntryException as e:
        bot.reply_to(
            message,
            f"{e}",
            reply_markup=telebot.types.ReplyKeyboardRemove(),
        )
        return

    bot.send_message(
        message.chat.id,
        "What type of entry is it? (Movie or Series)",
        reply_markup=get_movie_type_kb(),
    )
    bot.register_next_step_handler_by_chat_id(
        message.chat.id, _get_type, bot=bot, title=title, rating=rating
    )


def _get_type(
    message: telebot.types.Message, bot: telebot.TeleBot, title: str, rating: int
):
    try:
        type_ = Entry.parse_type(text(message))
    except MalformedEntryException as e:
        bot.send_message(
            message.chat.id,
            f"{e}",
            reply_markup=telebot.types.ReplyKeyboardRemove(),
        )
        return
    bot.send_message(
        message.chat.id,
        "Please enter the date (dd.mm.yyyy or 'today' or nothing):",
        reply_markup=get_skip_kb(extra_buttons=["Today"]),
    )
    bot.register_next_step_handler_by_chat_id(
        message.chat.id, _get_date, bot=bot, title=title, rating=rating, type_=type_
    )


def _get_date(
    message: telebot.types.Message,
    bot: telebot.TeleBot,
    title: str,
    rating: int,
    type_: Type,
):
    try:
        date = Entry.parse_date(
            text(message).lower() if text(message) != "Skip" else ""
        )
    except MalformedEntryException as e:
        bot.reply_to(
            message,
            f"Invalid date: {e}. Please use the format dd.mm.yyyy or 'today'.",
            reply_markup=telebot.types.ReplyKeyboardRemove(),
        )
        return

    bot.send_message(
        message.chat.id,
        "Do you want to add any notes? (Optional):",
        reply_markup=get_skip_kb(),
    )
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
    message: telebot.types.Message,
    bot: telebot.TeleBot,
    title: str,
    rating: int,
    type_: Type,
    date: datetime | None,
):
    notes = text(message) if text(message) != "Skip" else ""

    entry = Entry(None, title, rating, date, type_, notes)
    bot.send_message(
        message.chat.id,
        f"Thank you! Let's confirm the details:\n{format_entry(entry, True)}",
        reply_markup=get_confirmation_kb(),
    )
    bot.register_next_step_handler_by_chat_id(
        message.chat.id,
        _confirm_add,
        bot=bot,
        entry=entry,
    )


def _confirm_add(message: telebot.types.Message, bot: telebot.TeleBot, entry: Entry):
    if text(message).lower() == "confirm":
        Mongo.add_entry(entry)
        bot.send_message(
            message.chat.id,
            f"Entry added:\n{format_entry(entry, True, True)}",
            reply_markup=telebot.types.ReplyKeyboardRemove(),
        )
        if process_watch_list_on_add_entry(entry):
            bot.send_message(message.chat.id, f"Removed {entry.title} from watch list.")
    else:
        bot.send_message(
            message.chat.id,
            "Entry creation canceled.",
            reply_markup=telebot.types.ReplyKeyboardRemove(),
        )
