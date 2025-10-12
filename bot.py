import logging
from functools import wraps

from telebot import TeleBot, types

from botsrc.compiled import BOT_COMMANDS
from botsrc.helper import get_help
from botsrc.utils import (
    ALLOW_GUEST_COMMANDS,
    HELP_GUEST_MESSAGE,
    ME_CHAT_ID,
    report_repository_info,
)
from setup_logging import setup_logging
from src.parser import ParsingError, parse
from src.utils.env import TELEGRAM_TOKEN
from botsrc.bot_guest_manager import GuestManager
from botsrc.commands import upload_photo

logger = logging.getLogger(__name__)
setup_logging()

bot = TeleBot(TELEGRAM_TOKEN)
guest_manager = GuestManager()


def pre_process_command(func):
    @wraps(func)
    def wrapper(message: types.Message):
        if message.from_user is None or message.from_user.username is None:
            logger.error(
                f"Message without username: {message.chat.id=}; {message.text}"
            )
            return
        username = message.from_user.username
        name = message.from_user.first_name
        logger.info(f"{name}(@{username};id={message.chat.id}):{message.text}")
        if message.chat.id == ME_CHAT_ID:
            extra_flags = set()
        elif username in guest_manager:
            extra_flags = {"guest"}
        else:
            bot.reply_to(message, "You are not allowed to use this bot.")
            logger.info(f"User {username} is not allowed to use the bot")
            return
        func(message, extra_flags)

    return wrapper


def managed_help(
    root: str, pos: list[str], flags: set[str], bot: TeleBot, message: types.Message
) -> bool:
    if root == "help":
        if "guest" in flags:
            msg = HELP_GUEST_MESSAGE
        elif not pos:
            msg = get_help(BOT_COMMANDS)
        elif len(pos) == 1:
            msg = get_help(BOT_COMMANDS, pos[0])
        else:
            msg = "Too many arguments."
        bot.send_message(message.chat.id, msg)
        return True
    if "help" in flags:
        msg = get_help(BOT_COMMANDS, root)
        bot.send_message(message.chat.id, msg)
        return True
    return False


@bot.message_handler(commands=["start"])
@pre_process_command
def cmd_start(message: types.Message, extra_flags: set[str]):
    if "guest" in extra_flags:
        bot.send_message(
            message.chat.id, "Hello, dear guest! Type /help to see available commands."
        )
        logger.info("guest message shown")
    else:
        bot.send_message(message.chat.id, "Hello, me!")


@bot.message_handler(commands=["stop"])
@pre_process_command
def on_stop(message: types.Message, extra_flags: set[str]):
    bot.send_message(message.chat.id, "Shutting down.")
    logger.info("Stopping bot via /stop")
    bot.stop_bot()


# received a photo:
@bot.message_handler(content_types=["photo"])
@pre_process_command
def handle_photo(message: types.Message, extra_flags: set[str]):
    upload_photo(message, bot)


@bot.message_handler(func=lambda msg: True)
@pre_process_command
def other(message: types.Message, extra_flags: set[str]):
    if message.text is None:
        bot.reply_to(message, "Only text is supported.")
        return
    try:
        root, pos, kwargs, flags = parse(message.text.lstrip("/"))
    except ParsingError as e:
        bot.reply_to(message, f"{e}: {message.text!r}")
        logger.info("parsing error", exc_info=True)
        return
    root = root.lower()
    flags.update(extra_flags)
    if managed_help(root, pos, flags, bot, message):
        return
    command_method = BOT_COMMANDS.get(root)
    if command_method is None:
        msg = f"Unknown command: {message.text}"
        bot.reply_to(message, msg)
        logger.info(msg)
        return
    if "guest" in flags and root not in ALLOW_GUEST_COMMANDS:
        bot.reply_to(
            message,
            f"Sorry, you are not allowed to use {root}. Type /help to see available commands.",
        )
        logger.info(f"guest: command {root} not allowed")
        return
    logger.info(f"Called {root} with {pos=}, {kwargs=}, {flags=}")
    command_method(pos, kwargs, flags, bot, message)


if __name__ == "__main__":
    logger.info("Bot started")
    bot.send_message(ME_CHAT_ID, report_repository_info())
    bot.infinity_polling()
