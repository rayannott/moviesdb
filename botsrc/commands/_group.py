import logging

import telebot
from telebot import types

from botsrc.utils import list_many_groups
from src.mongo import Mongo
from src.obj.entry_group import groups_from_list_of_entries
from src.parser import PositionalArgs

logger = logging.getLogger(__name__)


def group(
    message: types.Message,
    bot: telebot.TeleBot,
    pos: PositionalArgs,
):
    entries = Mongo.load_entries()
    groups = groups_from_list_of_entries(entries)
    if pos:
        title = " ".join(pos)
        groups = [group for group in groups if title.lower() in group.title.lower()]
    if not groups:
        bot.send_message(message.chat.id, "No groups found.")
        logger.info("no groups found")
        return
    msg = list_many_groups(groups)
    bot.send_message(message.chat.id, msg)
    logger.info(f"found {len(groups)} groups")
