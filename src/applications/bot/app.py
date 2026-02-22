"""Telegram bot application using shared services."""

from collections.abc import Callable
from functools import wraps

from loguru import logger
from telebot import TeleBot, types

from src.applications.bot.commands import BotCommands
from src.parser import Flags, KeywordArgs, ParsingError, PositionalArgs, parse
from src.services.entry_service import EntryService
from src.services.guest_service import GuestService
from src.services.watchlist_service import WatchlistService
from src.utils.help_utils import parse_docstring

ME_CHAT_ID = 409474295

ALLOW_GUEST_COMMANDS = {"list", "watch", "suggest", "find", "tag", "group", "books"}

HELP_GUEST_MESSAGE = """You can use the bot, but some commands may be restricted.
You can use the following commands (read-only):
    - list - to view the entries
    - find <title> - to find a title by name
    - watch - to view the watch list
    - suggest <message> - to suggest me a movie!
    - group [<title>] - group entries by title
    - tag [<tagname>] - to view tags stats or entries with the given tag
    - books - to view the books I've recently read"""


def _get_help(
    commands: dict[str, Callable[..., None]],
    command: str | None = None,
) -> str:
    if command is None:
        return "\n".join(
            f"/{cmd} - {parsed_doc[1]}\n  {parsed_doc[0]}"
            if (parsed_doc := parse_docstring(func.__doc__)) is not None
            else f"/{cmd}"
            for cmd, func in commands.items()
        )
    func = commands.get(command)
    if func is None:
        return f"Command {command!r} not found."
    docstring = parse_docstring(func.__doc__)
    if docstring is None:
        return f"Command /{command} has no documentation."
    return f"/{command}\n" + "\n".join(docstring)


class BotApp:
    """Telegram bot wired with the DI container services."""

    def __init__(
        self,
        token: str,
        entry_service: EntryService,
        watchlist_service: WatchlistService,
        guest_service: GuestService,
    ) -> None:
        self.bot = TeleBot(token)
        self._guest_svc = guest_service

        self._commands = BotCommands(
            entry_service=entry_service,
            watchlist_service=watchlist_service,
            guest_service=guest_service,
        )

        BotCmdHandler = Callable[
            [PositionalArgs, KeywordArgs, Flags, TeleBot, types.Message],
            None,
        ]
        self._command_map: dict[str, BotCmdHandler] = {
            method_name[4:]: getattr(self._commands, method_name)
            for method_name in dir(self._commands)
            if method_name.startswith("cmd_")
        }

        self._register_handlers()

    def _pre_process(self, func: Callable[..., None]) -> Callable[..., None]:
        @wraps(func)
        def wrapper(message: types.Message) -> None:
            if message.from_user is None or message.from_user.username is None:
                logger.error(
                    f"Message without username: {message.chat.id=}; {message.text}"
                )
                return
            username = message.from_user.username
            name = message.from_user.first_name
            logger.info(f"{name}(@{username};id={message.chat.id}):{message.text}")
            if message.chat.id == ME_CHAT_ID:
                extra_flags: set[str] = set()
            elif self._guest_svc.is_guest(username):
                extra_flags = {"guest"}
            else:
                self.bot.reply_to(message, "You are not allowed to use this bot.")
                logger.info(f"User {username} is not allowed to use the bot")
                return
            func(message, extra_flags)

        return wrapper

    def _managed_help(
        self,
        root: str,
        pos: list[str],
        flags: set[str],
        message: types.Message,
    ) -> bool:
        if root == "help":
            if "guest" in flags:
                msg = HELP_GUEST_MESSAGE
            elif not pos:
                msg = _get_help(self._command_map)
            elif len(pos) == 1:
                msg = _get_help(self._command_map, pos[0])
            else:
                msg = "Too many arguments."
            self.bot.send_message(message.chat.id, msg)
            return True
        if "help" in flags:
            msg = _get_help(self._command_map, root)
            self.bot.send_message(message.chat.id, msg)
            return True
        return False

    def _register_handlers(self) -> None:
        @self.bot.message_handler(commands=["start"])
        @self._pre_process
        def cmd_start(message: types.Message, extra_flags: set[str]) -> None:
            if "guest" in extra_flags:
                self.bot.send_message(
                    message.chat.id,
                    "Hello, dear guest! Type /help to see available commands.",
                )
                logger.info("guest message shown")
            else:
                self.bot.send_message(message.chat.id, "Hello, me!")

        @self.bot.message_handler(commands=["stop"])
        @self._pre_process
        def cmd_stop(message: types.Message, extra_flags: set[str]) -> None:
            self.bot.send_message(message.chat.id, "Shutting down.")
            logger.info("Stopping bot via /stop")
            self.bot.stop_bot()

        @self.bot.message_handler(content_types=["photo"])
        @self._pre_process
        def handle_photo(message: types.Message, extra_flags: set[str]) -> None:
            from botsrc.commands._upload import upload_photo

            upload_photo(message, self.bot)

        @self.bot.message_handler(func=lambda msg: True)
        @self._pre_process
        def handle_text(message: types.Message, extra_flags: set[str]) -> None:
            if message.text is None:
                self.bot.reply_to(message, "Only text is supported.")
                return
            try:
                root, pos, kwargs, flags = parse(message.text.lstrip("/"))
            except ParsingError as e:
                self.bot.reply_to(message, f"{e}: {message.text!r}")
                logger.info("parsing error", exc_info=True)
                return
            root = root.lower()
            flags.update(extra_flags)
            if self._managed_help(root, pos, flags, message):
                return
            command_method = self._command_map.get(root)
            if command_method is None:
                msg = f"Unknown command: {message.text}"
                self.bot.reply_to(message, msg)
                logger.info(msg)
                return
            if "guest" in flags and root not in ALLOW_GUEST_COMMANDS:
                self.bot.reply_to(
                    message,
                    f"Sorry, you are not allowed to use {root}. "
                    "Type /help to see available commands.",
                )
                logger.info(f"guest: command {root} not allowed")
                return
            logger.info(f"Called {root} with {pos=}, {kwargs=}, {flags=}")
            command_method(pos, kwargs, flags, self.bot, message)

    def run(self) -> None:
        from src.obj.git_repo import RepoManager

        repo_info = RepoManager().get_repo_info()
        startup_msg = f"Bot started on branch: {repo_info.branch_name}."
        logger.info("Bot started")
        self.bot.send_message(ME_CHAT_ID, startup_msg)
        self.bot.infinity_polling()
