import telebot
import logging

from src.parser import Flags, KeywordArgs, PositionalArgs
from src.mongo import Mongo
from src.utils.utils import AccessRightsManager

from botsrc.utils import (
    format_entry,
    format_title,
    select_entry_by_oid_part,
    list_many_entries,
)
from botsrc.commands import add, suggest, tag, group


logger = logging.getLogger(__name__)


def cmd_list(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: telebot.types.Message,
):
    """list [--verbose] [--oid]
    List the last 5 entries in the database.
        verbose(flag): show the notes
        oid(flag): show the mongoDB OIDs
    """
    if "guest" in flags:
        flags = set()
    entries = sorted(Mongo.load_entries())
    msg = list_many_entries(
        entries[-5:],
        "verbose" in flags,
        "oid" in flags,
        override_title="Last 5 entries:",
    )
    bot.send_message(message.chat.id, msg)


def cmd_add(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: telebot.types.Message,
):
    """add [--title <title> --rating <rating> [--type <type>] [--date <date>] [--notes <notes>]]
    Add a new entry to the database.
    If no arguments are specified, start the multi-step process.
        title: the title of the entry
        rating: the rating of the entry (0-10)
        type: the type of the entry (movie or series; default: movie)
        date: the date of the entry (dd.mm.yyyy or today or ""; default: "")
        notes: the notes of the entry (default: "")
    Examples:
        add --title "The Matrix" --rating 9.0 --date 30.10.2022 --notes "Great movie! #watch-again"
        add
    """
    add(pos, kwargs, flags, bot, message)


def cmd_find(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: telebot.types.Message,
):
    """find <title> [--verbose] [--oid]
    Find an entry by title.
        verbose(flag): show the notes
        oid(flag): show the mongoDB OIDs
    """
    # TODO: refactor; move to own module
    if not pos:
        bot.reply_to(message, "You must specify a title.")
        return
    if "guest" in flags:
        flags = set()
    title = " ".join(pos)
    entries = sorted(Mongo.load_entries())
    filtered = [ent for ent in entries if title.lower() in ent.title.lower()]
    if not filtered:
        bot.reply_to(message, f"No entries found with {title!r}.")
        return
    res = list_many_entries(filtered, "verbose" in flags, "oid" in flags)
    bot.send_message(message.chat.id, res)


def cmd_watch(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: telebot.types.Message,
):
    """watch [<title>] [--delete]
    Show the watch list or add/delete an entry.
    If no arguments are specified, show the watch list.
        title: the title of the entry; if ends with "+", it is a series
        delete(flag): if specified, delete the entry from the watch list instead of adding it
    """
    # TODO: refactor; move to own module
    watch_list = Mongo.load_watch_list()
    if not (pos or kwargs or flags):
        bot.send_message(
            message.chat.id,
            f"Movies: {', '.join(watch_list.movies)}\n\nSeries: {', '.join(watch_list.series)}",
        )
        return
    if "guest" in flags:
        bot.reply_to(message, "Sorry, you can't modify anything.")
        return
    watch_title = " ".join(pos)
    is_series = watch_title.endswith("+")
    title = watch_title.rstrip("+ ")
    title_fmt = format_title(title, is_series)
    if "delete" in flags:
        if not watch_list.remove(title, is_series):
            bot.reply_to(message, f"{title_fmt} is not in the watch list.")
            return
        if not Mongo.delete_watchlist_entry(title, is_series):
            bot.reply_to(message, f"There is no such watch list entry: {title_fmt}.")
            return
        bot.send_message(message.chat.id, f"Deleted {title_fmt} from watch list.")
        return
    if not watch_list.add(title, is_series):
        bot.reply_to(message, f"{title_fmt} is already in the watch list.")
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
    """pop <oid>
    Delete an entry by OID.
        oid: the OID of the entry
    """
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
    """guest [--add <name>] [--remove <name>]
    Show the guest list or add/remove a name.
    If no arguments are specified, show the guest list.
        add: add the name to the guest list
        remove: remove the name from the guest list
    """
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


def cmd_tag(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: telebot.types.Message,
):
    """tag [<tagname>] [<oid>] [--delete] [--verbose] [--oid]
    Show the tags or add/delete a tag.
    If no arguments are specified, show the tag counts.
        tagname: if only argument, show the entries with the given tag
        oid: add/delete the tag to/from the entry with the given OID
        delete(flag): ...
        verbose(flag): show the notes
        oid(flag): show the mongoDB OIDs
    """
    tag(message, bot, pos, flags)


def cmd_group(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: telebot.types.Message,
):
    """group [<title>]
    List entries grouped by title."""
    group(message, bot, pos)
