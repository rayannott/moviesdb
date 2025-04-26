import telebot
import logging

from src.parser import Flags, KeywordArgs, PositionalArgs
from src.obj.entry import Entry, MalformedEntryException
from src.mongo import Mongo

from botsrc.utils import format_entry, select_entry_by_oid_part
from botsrc.commands import add


logger = logging.getLogger(__name__)


def cmd_list(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: telebot.types.Message,
):
    entries = sorted(Mongo.load_entries())
    tail_str = "\n".join(
        format_entry(
            entry,
            verbose=bool({"v", "verbose"} & flags),
            with_oid="oid" in flags,
        )
        for entry in entries[-5:]
    )
    bot.send_message(message.chat.id, tail_str)


def cmd_add(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: telebot.types.Message,
):
    if not kwargs:
        add(message, bot)
        return
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
    bot.send_message(
        message.chat.id, f"Entry added:\n{format_entry(entry, True, True)}"
    )


def cmd_find(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: telebot.types.Message,
):
    if not pos:
        bot.reply_to(message, "You must specify a title.")
        return
    entries = sorted(Mongo.load_entries())
    filtered = [ent for ent in entries if pos[0].lower() in ent.title.lower()]
    if not filtered:
        bot.reply_to(message, f"No entries found with {pos[0]}.")
        return
    res = f"{len(filtered)} found:\n" + "\n".join(
        format_entry(
            ent,
            verbose=bool({"v", "verbose"} & flags),
            with_oid="oid" in flags,
        )
        for ent in filtered
    )
    bot.send_message(message.chat.id, res)


def cmd_watch(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: telebot.types.Message,
):
    watch_list = Mongo.load_watch_list()
    if not pos:
        movies = [title for title, is_series in watch_list.items() if not is_series]
        series = [title for title, is_series in watch_list.items() if is_series]
        bot.send_message(
            message.chat.id,
            f"Movies: {', '.join(movies)}\n\nSeires: {', '.join(series)}",
        )
        return
    watch_title = "".join(pos)
    is_series = watch_title.endswith("+")
    title = watch_title.rstrip("+ ")
    watch_list = Mongo.load_watch_list()
    if "delete" in flags:
        if title not in watch_list:
            bot.reply_to(message, f"{title} is not in the watch list.")
            return
        if not Mongo.delete_watchlist_entry(title, is_series):
            bot.reply_to(message, f"There is no such watch list entry: {title}.")
            return
        bot.send_message(message.chat.id, f"Deleted {title} from watch list.")
        return
    if title in watch_list:
        bot.reply_to(message, f"{title} is already in the watch list.")
        return
    Mongo.add_watchlist_entry(title, is_series)
    bot.send_message(message.chat.id, f"Added {title} to watch list.")


def cmd_pop(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: telebot.types.Message,
):
    if not pos:
        bot.reply_to(message, "You must specify an oid.")
        return
    entries = sorted(Mongo.load_entries())
    selected_entry = select_entry_by_oid_part(pos[0], entries)
    if selected_entry is None:
        bot.reply_to(message, "Could not find a unique entry.")
        return
    assert selected_entry._id
    if Mongo.delete_entry(selected_entry._id):
        bot.send_message(
            message.chat.id, f"Deleted successfully:\n{format_entry(selected_entry)}"
        )
    else:
        bot.reply_to(message, "Something went wrong.")
