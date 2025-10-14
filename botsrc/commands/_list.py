import telebot
from telebot import types
from loguru import logger

from botsrc.utils import list_many_entries
from src.mongo import Mongo
from src.parser import Flags


def list_(
    message: types.Message,
    bot: telebot.TeleBot,
    flags: Flags,
):
    if "guest" in flags:
        flags = set()
        logger.debug("guest message; set flags to set()")
    entries = sorted(Mongo.load_entries())
    msg = list_many_entries(
        entries[-5:],
        "verbose" in flags,
        "oid" in flags,
        override_title="Last 5 entries:",
    )
    bot.send_message(message.chat.id, msg)
    logger.debug(msg)
