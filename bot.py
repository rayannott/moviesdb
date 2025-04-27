import os
import logging
import dotenv
import inspect
from functools import wraps
from collections.abc import Callable

from telebot import TeleBot, types

from src.parser import Flags, KeywordArgs, ParsingError, PositionalArgs, parse
from src.paths import LOG_FILE
from src.utils.utils import AccessRightsManager
import botsrc.cmds as botcmd
from botsrc.utils import ALLOW_GUEST_COMMANDS, ME_CHAT_ID, Report

dotenv.load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
assert TOKEN is not None


# TODO: set up file logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s]:%(asctime)s:%(module)s:%(message)s",
)
logger = logging.getLogger(__name__)

bot = TeleBot(TOKEN)
access_rights_manager = AccessRightsManager()
GUEST_MESSAGE = """Hello, dear guest! 
You can use the bot, but some commands may be restricted.
You can use the following commands:
    - list: to view the entries
    - find <title>: to find a title by name
    - watch: to view the watch list
    - suggest: to suggest me a movie!"""


def load_bot_commands():
    SIGNATURE = inspect.Signature(
        parameters=[
            inspect.Parameter(
                "pos",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=list[str],
            ),
            inspect.Parameter(
                "kwargs",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=dict[str, str],
            ),
            inspect.Parameter(
                "flags",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=set[str],
            ),
            inspect.Parameter(
                "bot",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=TeleBot,
            ),
            inspect.Parameter(
                "message",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=types.Message,
            ),
        ]
    )

    bot_commands: dict[
        str,
        Callable[[PositionalArgs, KeywordArgs, Flags, TeleBot, types.Message], None],
    ] = {
        method_name[4:]: getattr(botcmd, method_name)
        for method_name in dir(botcmd)
        if method_name.startswith("cmd_")
    }

    for bot_command in bot_commands.values():
        assert inspect.signature(bot_command) == SIGNATURE, (
            f"{bot_command} has a wrong signature."
        )

    return bot_commands


BOT_COMMANDS = load_bot_commands()


def pre_process_command(func):
    @wraps(func)
    def wrapper(message: types.Message):
        if message.from_user is None or message.from_user.username is None:
            logger.error(
                f"Message without username: {message.chat.id=}; {message.text}"
            )
            return
        username = message.from_user.username
        logger.info(f"{username}: {message.text}")
        if message.chat.id == ME_CHAT_ID:
            extra_flags = set()
        elif username in access_rights_manager:
            extra_flags = {"guest"}
        else:
            bot.reply_to(message, "You are not allowed to use this bot.")
            logger.warning(f"User {username} is not allowed to use the bot")
            return
        func(message, extra_flags)

    return wrapper


@bot.message_handler(commands=["start"])
@pre_process_command
def cmd_start(message: types.Message, extra_flags: set[str]):
    if "guest" in extra_flags:
        bot.send_message(
            message.chat.id,
            GUEST_MESSAGE,
        )
    else:
        bot.send_message(message.chat.id, "Hello, me!")


@bot.message_handler(commands=["help"])
@pre_process_command
def cmd_help(message: types.Message, extra_flags: set[str]):
    if "guest" in extra_flags:
        bot.send_message(
            message.chat.id,
            GUEST_MESSAGE,
        )
    else:
        # TODO: implement in a clever way to avoid code repetitions
        bot.send_message(message.chat.id, "Help message.")


@bot.message_handler(commands=["stop"])
@pre_process_command
def cmd_stop(message: types.Message, extra_flags: set[str]):
    bot.send_message(message.chat.id, "Shutting down.")
    logger.info("Stopping bot via /stop")
    bot.stop_bot()


@bot.message_handler(commands=["log"])
@pre_process_command
def cmd_log(message: types.Message, extra_flags: set[str]):
    if not LOG_FILE.exists():
        bot.reply_to(message, "Log file does not exist.")
        return
    lines = LOG_FILE.read_text().splitlines()
    bot.send_message(message.chat.id, "\n".join(lines[-10:]))


@bot.message_handler(func=lambda msg: True)
@pre_process_command
def echo_all(message: types.Message, extra_flags: set[str]):
    if message.text is None:
        bot.reply_to(message, "Only text is supported.")
        return
    try:
        root, pos, kwargs, flags = parse(message.text)
    except ParsingError as e:
        bot.reply_to(message, f"{e}: {message.text!r}")
        logging.error(f"Parsing error: {e}")
        return
    command_method = BOT_COMMANDS.get(root)
    if command_method is None:
        msg = f"Unknown command: {message.text}"
        bot.reply_to(message, msg)
        logging.warning(msg)
        return
    flags.update(extra_flags)
    if "guest" in flags and root not in ALLOW_GUEST_COMMANDS:
        bot.reply_to(
            message,
            f"Sorry, you are not allowed to use {root}. Type help to see available commands.",
        )
        return
    logging.info(f"Called {root} with {pos=}, {kwargs=}, {flags=}")
    command_method(pos, kwargs, flags, bot, message)


if __name__ == "__main__":
    logger.info("Bot started")
    bot.send_message(ME_CHAT_ID, Report().report_repository_info())
    bot.infinity_polling()
