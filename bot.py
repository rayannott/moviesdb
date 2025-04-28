import logging
from functools import wraps

from telebot import TeleBot, types

from src.parser import ParsingError, parse
from src.utils.env import TELEGRAM_TOKEN
from src.utils.utils import AccessRightsManager
from botsrc.utils import ALLOW_GUEST_COMMANDS, ME_CHAT_ID, Report, HELP_GUEST_MESSAGE
from botsrc.compiled import BOT_COMMANDS
from setup_logging import setup_logging


logger = logging.getLogger(__name__)
setup_logging()

bot = TeleBot(TELEGRAM_TOKEN)
access_rights_manager = AccessRightsManager()


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
            logger.info(f"User {username} is not allowed to use the bot")
            return
        func(message, extra_flags)

    return wrapper


@bot.message_handler(commands=["start"])
@pre_process_command
def cmd_start(message: types.Message, extra_flags: set[str]):
    if "guest" in extra_flags:
        bot.send_message(
            message.chat.id, "Hello, dear guest! Type /help to see available commands."
        )
    else:
        bot.send_message(message.chat.id, "Hello, me!")


@bot.message_handler(commands=["help"])
@pre_process_command
def on_help(message: types.Message, extra_flags: set[str]):
    if "guest" in extra_flags:
        bot.send_message(message.chat.id, HELP_GUEST_MESSAGE)
    else:
        # TODO: implement in a clever way to avoid code repetitions
        bot.send_message(message.chat.id, "Help message.")


@bot.message_handler(commands=["stop"])
@pre_process_command
def on_stop(message: types.Message, extra_flags: set[str]):
    bot.send_message(message.chat.id, "Shutting down.")
    logger.info("Stopping bot via /stop")
    bot.stop_bot()


@bot.message_handler(func=lambda msg: True)
@pre_process_command
def other(message: types.Message, extra_flags: set[str]):
    if message.text is None:
        bot.reply_to(message, "Only text is supported.")
        return
    try:
        root, pos, kwargs, flags = parse(message.text)
    except ParsingError as e:
        bot.reply_to(message, f"{e}: {message.text!r}")
        logging.error(f"Parsing error: {e}")
        return
    root = root.lstrip("/")
    command_method = BOT_COMMANDS.get(root)
    if command_method is None:
        msg = f"Unknown command: {message.text}"
        bot.reply_to(message, msg)
        logging.info(msg)
        return
    flags.update(extra_flags)
    if "guest" in flags and root not in ALLOW_GUEST_COMMANDS:
        bot.reply_to(
            message,
            f"Sorry, you are not allowed to use {root}. Type /help to see available commands.",
        )
        return
    logging.info(f"Called {root} with {pos=}, {kwargs=}, {flags=}")
    command_method(pos, kwargs, flags, bot, message)


if __name__ == "__main__":
    logger.info("Bot started")
    bot.send_message(ME_CHAT_ID, Report().report_repository_info())
    bot.infinity_polling()
