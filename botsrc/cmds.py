import telebot
import logging

from src.parser import Flags, KeywordArgs, PositionalArgs
from src.obj.entry import Entry, MalformedEntryException
from src.mongo import Mongo
from src.utils.utils import AccessRightsManager

from botsrc.utils import (
    format_entry,
    select_entry_by_oid_part,
    process_watch_list_on_add_entry,
)
from botsrc.commands import add, suggest


logger = logging.getLogger(__name__)


def cmd_list(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: telebot.types.Message,
):
    if "guest" in flags:
        flags = set()
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
    # TODO: refactor; move to own module
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
    Mongo.add_entry(entry)
    bot.send_message(
        message.chat.id, f"Entry added:\n{format_entry(entry, True, True)}"
    )
    if process_watch_list_on_add_entry(entry):
        bot.send_message(message.chat.id, f"Removed {entry.title} from watch list.")


def cmd_find(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: telebot.types.Message,
):
    # TODO: refactor; move to own module
    if not pos:
        bot.reply_to(message, "You must specify a title.")
        return
    if "guest" in flags:
        flags = set()
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
    # TODO: refactor; move to own module
    watch_list = Mongo.load_watch_list()
    if not pos:
        movies = [title for title, is_series in watch_list.items() if not is_series]
        series = [title for title, is_series in watch_list.items() if is_series]
        bot.send_message(
            message.chat.id,
            f"Movies: {', '.join(movies)}\n\nSeries: {', '.join(series)}",
        )
        return
    if "guest" in flags:
        bot.reply_to(message, "Sorry, you can't modify anything.")
        return
    watch_title = "".join(pos)
    is_series = watch_title.endswith("+")
    title = watch_title.rstrip("+ ")
    title_fmt = f"{title} ({'series' if is_series else ''})"
    watch_list = Mongo.load_watch_list()
    if "delete" in flags:
        if title not in watch_list:
            bot.reply_to(message, f"{title_fmt} is not in the watch list.")
            return
        if not Mongo.delete_watchlist_entry(title, is_series):
            bot.reply_to(message, f"There is no such watch list entry: {title_fmt}.")
            return
        bot.send_message(message.chat.id, f"Deleted {title} from watch list.")
        return
    if title in watch_list:
        bot.reply_to(message, f"{title} is already in the watch list.")
        return
    Mongo.add_watchlist_entry(title, is_series)
    bot.send_message(message.chat.id, f"Added {title_fmt} to watch list.")


def cmd_pop(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: telebot.types.Message,
):
    # TODO: refactor; move to own module
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


def cmd_suggest(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: telebot.types.Message,
):
    suggest(message, bot)


def cmd_guest(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: telebot.types.Message,
):
    # TODO: refactor; move to own module
    am = AccessRightsManager()
    if (name := kwargs.get("add")) is not None:
        am.add(name)
        msg = f"{name} added to the guests list"
    elif (name := kwargs.get("remove")) is not None:
        is_ok = am.remove(name)
        msg = (
            f"{name} removed from the guests list"
            if is_ok
            else f"{name} was not in the guest list"
        )
    else:
        msg = "Guests: " + ", ".join(am.guests)
    bot.send_message(message.chat.id, msg)
