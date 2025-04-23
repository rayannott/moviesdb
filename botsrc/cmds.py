import telebot

from src.parser import Flags, KeywordArgs, PositionalArgs
from src.obj.entry import Entry, MalformedEntryException
from src.utils.mongo import Mongo
from src.app import App


def cmd_add(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: telebot.types.Message,
):
    try:
        title = kwargs["title"]
        rating = Entry.parse_rating(kwargs["rating"])
        type_ = Entry.parse_type(kwargs.get("type", "movie"))
        date = Entry.parse_date(kwargs.get("date", ""))
        notes = kwargs.get("notes", "")
    except MalformedEntryException as e:
        bot.reply_to(message, str(e))
        return
    except KeyError:
        bot.reply_to(message, "Need to specify title and rating")
        return
    entry = Entry(None, title, rating, date, type_, notes)
    # TODO: other entry-adding-related processing here
    Mongo.add_entry(entry)
    bot.send_message(message.chat.id, f"Entry added:\n{entry}")


def cmd_find(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: telebot.types.Message,
):
    entries = App.load_entries_mongo()
