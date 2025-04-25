import os
import logging
import dotenv
import inspect
from functools import wraps
from collections.abc import Callable

from telebot import TeleBot, types

from src.parser import Flags, KeywordArgs, ParsingError, PositionalArgs, parse
import botsrc.cmds as botcmd

dotenv.load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
assert TOKEN is not None

ALLOW_USER = "rayannott"


# TODO: set up file logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s]:%(asctime)s:%(module)s:%(message)s",
)
logger = logging.getLogger(__name__)

bot = TeleBot(TOKEN)


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
        assert (
            inspect.signature(bot_command) == SIGNATURE
        ), f"{bot_command} has a wrong signature."

    return bot_commands


BOT_COMMANDS = load_bot_commands()


def pre_process_command(func):
    @wraps(func)
    def wrapper(message: types.Message):
        logger.info(message.text)
        if message.from_user is None:
            return
        if message.from_user.username != ALLOW_USER:
            bot.reply_to(message, "You are not allowed to use this bot.")
            return
        func(message)

    return wrapper


@bot.message_handler(commands=["start"])
@pre_process_command
def cmd_start(message: types.Message):
    bot.send_message(message.chat.id, "Hello, me!")


@bot.message_handler(commands=["help"])
@pre_process_command
def cmd_help(message: types.Message):
    # TODO: implement in a clever way to avoid code repetitions
    bot.send_message(message.chat.id, "Help message.")


@bot.message_handler(commands=["stop"])
@pre_process_command
def cmd_stop(message: types.Message):
    bot.send_message(message.chat.id, "Shutting down.")
    logger.info("Stopping bot via /stop")
    bot.stop_bot()


@bot.message_handler(func=lambda msg: True)
@pre_process_command
def echo_all(message: types.Message):
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
    logging.info(f"Called {root} with {pos=}, {kwargs=}, {flags=}")
    command_method(pos, kwargs, flags, bot, message)


if __name__ == "__main__":
    logger.info("Bot started")
    bot.infinity_polling()
