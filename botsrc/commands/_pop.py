import logging

import telebot
from telebot import types

from botsrc.utils import format_entry, select_entry_by_oid_part
from src.mongo import Mongo
from src.parser import PositionalArgs

logger = logging.getLogger(__name__)


def pop(
    message: types.Message,
    bot: telebot.TeleBot,
    pos: PositionalArgs,
):
    if not pos:
        bot.reply_to(message, "You must specify an oid.")
        logger.info("oid not specified")
        return
    entries = sorted(Mongo.load_entries())
    selected_entry = select_entry_by_oid_part(pos[0], entries)
    logger.debug(f"selected entry: {selected_entry}")
    if selected_entry is None:
        bot.reply_to(message, "Could not find a unique entry.")
        return
    assert selected_entry._id
    if Mongo.delete_entry(selected_entry._id):
        bot.send_message(
            message.chat.id, f"Deleted successfully:\n{format_entry(selected_entry)}"
        )
        logger.info(f"deleted entry: {selected_entry} with id={selected_entry._id}")
    else:
        bot.reply_to(message, "Something went wrong.")
        logger.error(f"failed to delete entry: {selected_entry}")
