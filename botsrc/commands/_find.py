import logging

import telebot
from telebot import types

from botsrc.utils import list_many_entries
from src.mongo import Mongo
from src.parser import Flags, PositionalArgs

logger = logging.getLogger(__name__)


def find(
    message: types.Message,
    bot: telebot.TeleBot,
    pos: PositionalArgs,
    flags: Flags,
):
    if not pos:
        bot.reply_to(message, "You must specify a title.")
        logger.info("title not specified")
        return
    if "guest" in flags and flags:
        logger.info(f"guest user tried to use flags {flags}; prevented")
        flags = set()
    title = " ".join(pos)
    entries = sorted(Mongo.load_entries())
    filtered = [ent for ent in entries if title.lower() in ent.title.lower()]
    if not filtered:
        bot.reply_to(message, f"No entries found with {title!r}.")
        logger.info(f"no entries found with {title!r}")
        return
    res = list_many_entries(filtered, "verbose" in flags, "oid" in flags)
    bot.send_message(message.chat.id, res)
    logger.info(f"found {len(filtered)} entries with {title!r}")
