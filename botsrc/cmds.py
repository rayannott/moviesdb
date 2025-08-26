import logging

import telebot
from telebot import types

from botsrc.commands import (
    add,
    find,
    group,
    guest,
    list_,
    pop,
    suggest,
    tag,
    watch,
    logs,
    books,
    image,
)
from src.parser import Flags, KeywordArgs, PositionalArgs

logger = logging.getLogger(__name__)


def cmd_list(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: types.Message,
):
    """list [--verbose] [--oid]
    List the last 5 entries in the database.
        verbose(flag): show the notes
        oid(flag): show the mongoDB OIDs
    """
    list_(message, bot, flags)


def cmd_add(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: types.Message,
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
    message: types.Message,
):
    """find <title> [--verbose] [--oid]
    Find an entry by title.
        verbose(flag): show the notes
        oid(flag): show the mongoDB OIDs
    """
    find(message, bot, pos, flags)


def cmd_watch(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: types.Message,
):
    """watch [<title>] [--delete]
    Show the watch list or add/delete an entry.
    If no arguments are specified, show the watch list.
        title: the title of the entry; if ends with a '+', it is a series
        delete(flag): if specified, delete the entry from the watch list instead of adding it
    """
    watch(message, bot, pos, flags, kwargs)


def cmd_pop(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: types.Message,
):
    """pop <oid>
    Delete an entry by OID.
        oid: the OID of the entry
    """
    pop(message, bot, pos)


def cmd_suggest(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: types.Message,
):
    suggest(message, bot)


def cmd_guest(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: types.Message,
):
    """guest [--add <name>] [--remove <name>]
    Show the guest list or add/remove a name.
    If no arguments are specified, show the guest list.
        add: add the name to the guest list
        remove: remove the name from the guest list
    """
    guest(message, bot, kwargs)


def cmd_tag(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: types.Message,
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


def cmd_logs(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: types.Message,
):
    """logs [--full]
    Take a peak into the logs.
    If the --full flag is specified, send the logs as a zip file. Otherwise, just show the last 10 lines of the log file.
        full(flag): if specified, send all logs as a single zip file
    """
    logs(message, bot, flags)


def cmd_group(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: types.Message,
):
    """group [<title>]
    List entries grouped by title."""
    group(message, bot, pos)


def cmd_books(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: types.Message,
):
    """books [<title>] [--verbose]
    List the last books read.
    If no arguments are specified, show the last 5 books.
    If a title is specified, filter the books by the title substring.
        verbose(flag): show the body of the book
    """
    books(message, bot, pos, flags)


def cmd_image(
    pos: PositionalArgs,
    kwargs: KeywordArgs,
    flags: Flags,
    bot: telebot.TeleBot,
    message: types.Message,
):
    """image ...
    Manage images; 'image --help' for more.
    Commands:
        list <filter> [--show]: List images by filter; show if --show is specified
        entry <entry_oid>: Show images for a specific entry
    """
    image(message, bot, pos, flags, kwargs)
