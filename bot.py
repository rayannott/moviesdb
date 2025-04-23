import os
import logging
import dotenv
from functools import wraps

from telebot import TeleBot, types

from src.app import App
from src.parser import Flags, KeywordArgs, ParsingError, PositionalArgs, parse
from src.obj.entry import Entry
from src.obj.entry_group import EntryGroup
from src.utils.mongo import Mongo
import botsrc.cmds as botcmd

dotenv.load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
assert TOKEN is not None

ALLOW_USER = "rayannott"


logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s]:%(asctime)s:%(module)s:%(message)s",
)
logger = logging.getLogger(__name__)

bot = TeleBot(TOKEN)


def log_message(message: types.Message):
    logger.info(
        f"message from {message.from_user.username if message.from_user is not None else None}: {message.text}"
    )


def pre_process_command(func):
    @wraps(func)
    def wrapper(message: types.Message):
        log_message(message)
        if message.from_user is None:
            return
        if message.from_user.username != ALLOW_USER:
            return
        func(message)

    return wrapper


@bot.message_handler(commands=["start"])
@pre_process_command
def cmd_start(message: types.Message):
    bot.send_message(message.chat.id, "Hello, world!")


@bot.message_handler(commands=["help"])
@pre_process_command
def cmd_help(message: types.Message):
    bot.send_message(message.chat.id, "Help message")


@bot.message_handler(commands=["list"])
@pre_process_command
def cmd_list(message: types.Message):
    entries = sorted(Mongo.load_entries())
    tail_str = "\n".join(str(entry) for entry in entries[-5:])
    bot.send_message(message.chat.id, tail_str)


@bot.message_handler(func=lambda msg: True)
@pre_process_command
def echo_all(message: types.Message):
    if message.text is None:
        bot.reply_to(message, "Only text is suppoted.")
        return
    try:
        root, pos, kwargs, flags = parse(message.text)
    except ParsingError as e:
        bot.reply_to(message, f"{e}: {message.text!r}")
        return
    # TODO: match commands from botsrc.cmds
    if root == "add":
        botcmd.cmd_add(pos, kwargs, flags, bot, message)
    elif root == "watch":
        botcmd.cmd_watch(pos, kwargs, flags, bot, message)
    else:
        bot.reply_to(message, f"Unknown command: {message.text}")


if __name__ == "__main__":
    logger.info("Bot started")
    bot.infinity_polling()
