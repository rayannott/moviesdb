"""Bot command handlers using shared services."""

from datetime import datetime

import telebot
from loguru import logger
from telebot import types

from src.applications.bot.formatting import (
    format_entry,
    format_title,
    list_many_entries,
    list_many_groups,
)
from src.exceptions import (
    DuplicateEntryException,
    EntryNotFoundException,
    MalformedEntryException,
)
from src.models.entry import Entry, EntryType
from src.parser import Flags, KeywordArgs, PositionalArgs
from src.services.entry_service import EntryService
from src.services.guest_service import GuestService
from src.services.image_service import ImageService
from src.services.watchlist_service import WatchlistService
from src.utils.utils import replace_tag_alias


def _text(message: types.Message) -> str:
    return message.text if message.text is not None else ""


def _movie_type_kb() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(types.KeyboardButton("Movie"), types.KeyboardButton("Series"))
    return kb


def _confirmation_kb() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(types.KeyboardButton("Confirm"), types.KeyboardButton("Cancel"))
    return kb


def _skip_kb(extra_buttons: list[str] | None = None) -> types.ReplyKeyboardMarkup:
    extra_buttons = extra_buttons or []
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True, row_width=1 + len(extra_buttons)
    )
    kb.add(*(types.KeyboardButton(btn) for btn in ["Skip"] + extra_buttons))
    return kb


class BotCommands:
    """Bot command implementations backed by services."""

    def __init__(
        self,
        entry_service: EntryService,
        watchlist_service: WatchlistService,
        guest_service: GuestService,
        image_service: ImageService,
    ) -> None:
        self._entry_svc = entry_service
        self._watchlist_svc = watchlist_service
        self._guest_svc = guest_service
        self._image_svc = image_service

    def cmd_list(
        self,
        pos: PositionalArgs,
        kwargs: KeywordArgs,
        flags: Flags,
        bot: telebot.TeleBot,
        message: types.Message,
    ) -> None:
        """list [--verbose] [--oid]
        List the last 5 entries in the database.
            verbose(flag): show the notes
            oid(flag): show the mongoDB OIDs
        """
        if "guest" in flags:
            flags = set()
            logger.debug("guest message; set flags to set()")
        entries = self._entry_svc.get_entries()
        msg = list_many_entries(
            entries[-5:],
            "verbose" in flags,
            "oid" in flags,
            override_title="Last 5 entries:",
        )
        bot.send_message(message.chat.id, msg)
        logger.debug(msg)

    def cmd_find(
        self,
        pos: PositionalArgs,
        kwargs: KeywordArgs,
        flags: Flags,
        bot: telebot.TeleBot,
        message: types.Message,
    ) -> None:
        """find <title> [--verbose] [--oid]
        Find an entry by title.
            verbose(flag): show the notes
            oid(flag): show the mongoDB OIDs
        """
        if not pos:
            bot.reply_to(message, "You must specify a title.")
            logger.debug("title not specified")
            return
        if "guest" in flags:
            logger.debug(f"guest user tried to use flags {flags}; prevented")
            flags = set()
        title = " ".join(pos)
        entries = self._entry_svc.get_entries()
        filtered = [ent for ent in entries if title.lower() in ent.title.lower()]
        if not filtered:
            bot.reply_to(message, f"No entries found with {title!r}.")
            logger.debug(f"no entries found with {title!r}")
            return
        res = list_many_entries(filtered, "verbose" in flags, "oid" in flags)
        bot.send_message(message.chat.id, res)
        logger.debug(f"found {len(filtered)} entries with {title!r}")

    def cmd_watch(
        self,
        pos: PositionalArgs,
        kwargs: KeywordArgs,
        flags: Flags,
        bot: telebot.TeleBot,
        message: types.Message,
    ) -> None:
        """watch [<title>] [--delete]
        Show the watch list or add/delete an entry.
        If no arguments are specified, show the watch list.
            title: the title of the entry; if ends with a '+', it is a series
            delete(flag): delete instead of adding
        """
        if not (pos or kwargs or (flags - {"guest"})):
            movies = self._watchlist_svc.movies
            series = self._watchlist_svc.series
            bot.send_message(
                message.chat.id,
                f"Movies: {', '.join(movies)}\n\nSeries: {', '.join(series)}",
            )
            logger.debug("watch list requested")
            return
        if "guest" in flags:
            bot.reply_to(message, "Sorry, you can't modify anything.")
            logger.debug("guest user tried to modify watch list; prevented")
            return
        watch_title = " ".join(pos)
        is_series = watch_title.endswith("+")
        title = watch_title.rstrip("+ ")
        title_fmt = format_title(title, is_series)
        if "delete" in flags:
            try:
                self._watchlist_svc.remove(title, is_series)
            except EntryNotFoundException:
                bot.reply_to(message, f"{title_fmt} is not in the watch list.")
                logger.debug(f"{title_fmt} not found for deletion")
                return
            bot.send_message(message.chat.id, f"Deleted {title_fmt} from watch list.")
            logger.debug(f"deleted {title_fmt} from watch list")
            return
        try:
            self._watchlist_svc.add(title, is_series)
        except DuplicateEntryException:
            bot.reply_to(message, f"{title_fmt} is already in the watch list.")
            logger.debug(f"{title_fmt} already exists in watch list")
            return
        bot.send_message(message.chat.id, f"Added {title_fmt} to watch list.")
        logger.debug(f"added {title_fmt} to watch list")

    def cmd_pop(
        self,
        pos: PositionalArgs,
        kwargs: KeywordArgs,
        flags: Flags,
        bot: telebot.TeleBot,
        message: types.Message,
    ) -> None:
        """pop <oid>
        Delete an entry by OID.
            oid: the OID of the entry
        """
        if not pos:
            bot.reply_to(message, "You must specify an oid.")
            logger.debug("oid not specified")
            return
        entries = self._entry_svc.get_entries()
        selected = [e for e in entries if pos[0] in e.id]
        if len(selected) != 1:
            bot.reply_to(message, "Could not find a unique entry.")
            return
        selected_entry = selected[0]
        logger.debug(f"selected entry: {selected_entry}")
        assert selected_entry.id
        try:
            self._entry_svc.delete_entry(selected_entry.id)
        except EntryNotFoundException:
            bot.reply_to(message, "Something went wrong.")
            logger.error(f"failed to delete entry: {selected_entry}")
            return
        bot.send_message(
            message.chat.id,
            f"Deleted successfully:\n{format_entry(selected_entry)}",
        )
        logger.debug(f"deleted entry with id={selected_entry.id}")

    def cmd_tag(
        self,
        pos: PositionalArgs,
        kwargs: KeywordArgs,
        flags: Flags,
        bot: telebot.TeleBot,
        message: types.Message,
    ) -> None:
        """tag [<tagname>] [<oid>] [--delete] [--verbose] [--oid]
        Show the tags or add/delete a tag.
        If no arguments are specified, show the tag counts.
            tagname: if only argument, show the entries with the given tag
            oid: add/delete the tag to/from the entry with the given OID
            delete(flag): ...
            verbose(flag): show the notes
            oid(flag): show the mongoDB OIDs
        """
        tags = self._entry_svc.get_tags()
        if not pos:
            msg = "Tags:\n" + "\n".join(
                f"{len(entries):>3}   {tag:<18}"
                for tag, entries in sorted(
                    tags.items(), key=lambda x: len(x[1]), reverse=True
                )
            )
            bot.send_message(message.chat.id, msg)
            logger.debug("no positional arguments; listing all tags")
            return
        if len(pos) == 1:
            tag = replace_tag_alias(pos[0])
            if (tag_entries := tags.get(tag)) is None:
                bot.send_message(message.chat.id, f"Tag {tag} not found.")
                logger.debug(f"tag {tag!r} not found")
                return
            res = list_many_entries(
                tag_entries,
                "verbose" in flags,
                "oid" in flags,
                override_title=f"{len(tag_entries)} entries with tag {tag!r}",
            )
            bot.send_message(message.chat.id, res)
            logger.debug(
                f"found and listed {len(tag_entries)} entries with tag {tag!r}"
            )
            return
        if len(pos) == 2 and "guest" not in flags:
            tag_name, oid = pos
            tag_name = replace_tag_alias(tag_name)
            entries = self._entry_svc.get_entries()
            entry = next((ent for ent in entries if oid in ent.id), None)
            if entry is None:
                bot.reply_to(message, "Could not find an entry.")
                logger.debug(f"could not find entry with oid {oid}")
                return
            if {"d", "delete"} & flags:
                if not self._entry_svc.remove_tag(entry, tag_name):
                    bot.reply_to(
                        message, f"The entry does not have the tag {tag_name}:"
                    )
                    logger.debug(f"tag {tag_name!r} not found in entry {entry.id}")
                    return
                bot.send_message(
                    message.chat.id, f"Tag removed:\n{format_entry(entry)}"
                )
                logger.debug(f"removed tag {tag_name!r} from entry {entry.id}")
                return
            if not self._entry_svc.add_tag(entry, tag_name):
                bot.reply_to(message, f"The entry already has the tag {tag_name}:")
                return
            bot.send_message(message.chat.id, f"Tag added:\n{format_entry(entry)}")
            logger.debug(f"added tag {tag_name!r} to entry {entry.id}")
            return
        bot.reply_to(message, "Too many arguments.")
        logger.debug("too many positional arguments")

    def cmd_group(
        self,
        pos: PositionalArgs,
        kwargs: KeywordArgs,
        flags: Flags,
        bot: telebot.TeleBot,
        message: types.Message,
    ) -> None:
        """group [<title>]
        List entries grouped by title."""
        groups = self._entry_svc.get_groups()
        if pos:
            title = " ".join(pos)
            groups = [g for g in groups if title.lower() in g.title.lower()]
        if not groups:
            bot.send_message(message.chat.id, "No groups found.")
            logger.info("no groups found")
            return
        msg = list_many_groups(groups)
        bot.send_message(message.chat.id, msg)
        logger.info(f"found {len(groups)} groups")

    def cmd_guest(
        self,
        pos: PositionalArgs,
        kwargs: KeywordArgs,
        flags: Flags,
        bot: telebot.TeleBot,
        message: types.Message,
    ) -> None:
        """guest [--add <name>] [--remove <name>]
        Show the guest list or add/remove a name.
        If no arguments are specified, show the guest list.
            add: add the name to the guest list
            remove: remove the name from the guest list
        """
        if (name := kwargs.get("add")) is not None:
            self._guest_svc.add_guest(name)
            msg = f"{name} added to the guests list"
        elif (name := kwargs.get("remove")) is not None:
            is_ok = self._guest_svc.remove_guest(name)
            msg = (
                f"{name} removed from the guests list"
                if is_ok
                else f"{name} was not in the guest list"
            )
        else:
            msg = "Guests: " + ", ".join(self._guest_svc.get_guests())
        bot.send_message(message.chat.id, msg)
        logger.debug(f"{msg}; (current guests: {self._guest_svc.get_guests()})")

    def cmd_add(
        self,
        pos: PositionalArgs,
        kwargs: KeywordArgs,
        flags: Flags,
        bot: telebot.TeleBot,
        message: types.Message,
    ) -> None:
        """add [--title <t> --rating <r> [--type <type>] [--date <d>] [--notes <n>]]
        Add a new entry to the database.
        If no arguments are specified, start the multi-step process.
            title: the title of the entry
            rating: the rating of the entry (0-10)
            type: the type of the entry (movie or series; default: movie)
            date: the date of the entry (dd.mm.yyyy or today or ""; default: "")
            notes: the notes of the entry (default: "")
        Examples:
            add --title "The Matrix" --rating 9.0 --date 30.10.2022
            add
        """
        if not (pos or flags or kwargs):
            sent = bot.send_message(message.chat.id, "Please enter the title:")
            logger.debug("multistep add entry initiated")
            bot.register_next_step_handler(sent, self._add_get_title, bot=bot)
            return
        try:
            title = kwargs["title"]
            rating = Entry.parse_rating(kwargs["rating"])
            type_ = Entry.parse_type(kwargs.get("type", "movie"))
            date = Entry.parse_date(kwargs.get("date", ""))
            notes = kwargs.get("notes", "")
        except MalformedEntryException as e:
            bot.reply_to(message, str(e))
            logger.debug(f"malformed entry while adding: {e}")
            return
        except KeyError:
            bot.reply_to(message, "Need to specify title and rating")
            logger.debug("missing title or rating while adding entry")
            return
        entry = Entry(title=title, rating=rating, date=date, type=type_, notes=notes)
        self._entry_svc.add_entry(entry)
        bot.send_message(
            message.chat.id,
            f"Entry added:\n{format_entry(entry, True, True)}",
        )
        logger.debug(f"added entry {entry}")
        self._process_watchlist_on_add(entry, bot, message)

    def _add_get_title(self, message: types.Message, bot: telebot.TeleBot) -> None:
        title = _text(message)
        if not title:
            bot.reply_to(
                message,
                "You must specify a title.",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return
        is_series = self._watchlist_svc.get_is_series(title)
        extra_note = (
            f"Note that {format_title(title, bool(is_series))} will be removed "
            f"from watch list if you proceed to add it. "
            if is_series is not None
            else ""
        )
        bot.send_message(message.chat.id, f"{extra_note}Now, please rate it:")
        bot.register_next_step_handler_by_chat_id(
            message.chat.id,
            self._add_get_rating,
            bot=bot,
            title=title,
        )

    def _add_get_rating(
        self, message: types.Message, bot: telebot.TeleBot, title: str
    ) -> None:
        try:
            rating = Entry.parse_rating(_text(message))
        except MalformedEntryException as e:
            bot.reply_to(
                message,
                str(e),
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return
        bot.send_message(
            message.chat.id,
            "What type of entry is it? (Movie or Series)",
            reply_markup=_movie_type_kb(),
        )
        bot.register_next_step_handler_by_chat_id(
            message.chat.id,
            self._add_get_type,
            bot=bot,
            title=title,
            rating=rating,
        )

    def _add_get_type(
        self,
        message: types.Message,
        bot: telebot.TeleBot,
        title: str,
        rating: float,
    ) -> None:
        try:
            type_ = Entry.parse_type(_text(message))
        except MalformedEntryException as e:
            bot.send_message(
                message.chat.id,
                str(e),
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return
        bot.send_message(
            message.chat.id,
            "Please enter the date (dd.mm.yyyy or 'today' or nothing):",
            reply_markup=_skip_kb(extra_buttons=["Today"]),
        )
        bot.register_next_step_handler_by_chat_id(
            message.chat.id,
            self._add_get_date,
            bot=bot,
            title=title,
            rating=rating,
            type_=type_,
        )

    def _add_get_date(
        self,
        message: types.Message,
        bot: telebot.TeleBot,
        title: str,
        rating: float,
        type_: EntryType,
    ) -> None:
        try:
            raw = _text(message).lower()
            date = Entry.parse_date(raw if raw != "skip" else "")
        except MalformedEntryException as e:
            bot.reply_to(
                message,
                f"Invalid date: {e}. Please use the format dd.mm.yyyy or 'today'.",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            return
        bot.send_message(
            message.chat.id,
            "Do you want to add any notes? (Optional):",
            reply_markup=_skip_kb(),
        )
        bot.register_next_step_handler_by_chat_id(
            message.chat.id,
            self._add_get_notes,
            bot=bot,
            title=title,
            rating=rating,
            type_=type_,
            date=date,
        )

    def _add_get_notes(
        self,
        message: types.Message,
        bot: telebot.TeleBot,
        title: str,
        rating: float,
        type_: EntryType,
        date: datetime | None,
    ) -> None:
        notes = _text(message) if _text(message).lower() != "skip" else ""
        entry = Entry(title=title, rating=rating, date=date, type=type_, notes=notes)
        bot.send_message(
            message.chat.id,
            f"Thank you! Let's confirm the details:\n{format_entry(entry, True)}",
            reply_markup=_confirmation_kb(),
        )
        bot.register_next_step_handler_by_chat_id(
            message.chat.id,
            self._add_confirm,
            bot=bot,
            entry=entry,
        )

    def _add_confirm(
        self, message: types.Message, bot: telebot.TeleBot, entry: Entry
    ) -> None:
        if _text(message).lower() != "confirm":
            bot.send_message(
                message.chat.id,
                "Entry creation canceled.",
                reply_markup=types.ReplyKeyboardRemove(),
            )
            logger.debug("entry creation canceled")
            return
        self._entry_svc.add_entry(entry)
        bot.send_message(
            message.chat.id,
            f"Entry added:\n{format_entry(entry, True, True)}",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        logger.debug(f"added entry {entry}")
        self._process_watchlist_on_add(entry, bot, message)
        self._process_watch_again_on_add(entry, bot, message)

    def _process_watchlist_on_add(
        self,
        entry: Entry,
        bot: telebot.TeleBot,
        message: types.Message,
    ) -> None:
        title_fmt = format_title(entry.title, entry.is_series)
        if self._entry_svc.remove_from_watchlist_on_add(entry):
            bot.send_message(
                message.chat.id,
                f"Removed {title_fmt} from watch list.",
            )

    def _process_watch_again_on_add(
        self,
        entry: Entry,
        bot: telebot.TeleBot,
        message: types.Message,
    ) -> None:
        modified = self._entry_svc.process_watch_again_on_add(entry)
        if not modified:
            return
        msg = "Removed the watch again tag from:"
        for ent in modified:
            msg += f"\n{format_entry(ent)}"
        bot.send_message(message.chat.id, msg)

    def cmd_suggest(
        self,
        pos: PositionalArgs,
        kwargs: KeywordArgs,
        flags: Flags,
        bot: telebot.TeleBot,
        message: types.Message,
    ) -> None:
        """suggest <message>
        Suggest a movie to the owner."""
        from botsrc.utils import ME_CHAT_ID

        if message.text is None or not message.text.strip():
            bot.reply_to(message, "Please provide a text message.")
            logger.debug("empty message text")
            return
        username = message.from_user.username if message.from_user else ""
        name = message.from_user.first_name if message.from_user else ""
        sugg_text = f"Suggestion from {name}(@{username}):\n{message.text}"
        bot.send_message(ME_CHAT_ID, sugg_text)
        bot.send_message(message.chat.id, "Thank you for your suggestion!")
        logger.debug(sugg_text)

    def cmd_books(
        self,
        pos: PositionalArgs,
        kwargs: KeywordArgs,
        flags: Flags,
        bot: telebot.TeleBot,
        message: types.Message,
    ) -> None:
        """books [<title>] [--verbose]
        List the last books read.
        If no arguments are specified, show the last 5 books.
        If a title is specified, filter the books by the title substring.
            verbose(flag): show the body of the book
        """
        from botsrc.utils import format_book
        from src.apps import BooksApp

        client = BooksApp.get_client()
        books = BooksApp.get_books(client)
        logger.debug(f"Fetched {len(books)} books from the database")
        if not books:
            bot.reply_to(message, "No books found.")
            return
        if pos:
            books = [book for book in books if pos[0].lower() in book.title.lower()]
        books.sort(key=lambda b: b.dt_read)
        last_5 = books[-5:]
        formatted = f"Last {len(last_5)} books:\n" + "\n".join(
            format_book(book, "verbose" in flags) for book in last_5
        )
        formatted = "No books found." if len(last_5) == 0 else formatted
        bot.send_message(message.chat.id, formatted)
        logger.debug(f"Displayed {len(last_5)} books")

    def cmd_image(
        self,
        pos: PositionalArgs,
        kwargs: KeywordArgs,
        flags: Flags,
        bot: telebot.TeleBot,
        message: types.Message,
    ) -> None:
        """image ...
        Manage images; 'image --help' for more.
        Commands:
            list <filter> [--show]: List images by filter; show if --show is specified
            entry <entry_oid>: Show images for a specific entry
        """
        from botsrc.commands._image import image

        image(message, bot, pos, flags, kwargs, image_service=self._image_svc)
