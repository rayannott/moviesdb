import telebot

from src.parser import PositionalArgs
from src.mongo import Mongo
from src.obj.entry_group import groups_from_list_of_entries
from botsrc.utils import list_many_groups


def group(
    message: telebot.types.Message,
    bot: telebot.TeleBot,
    pos: PositionalArgs,
):
    entries = Mongo.load_entries()
    groups = groups_from_list_of_entries(entries)
    if pos:
        title = " ".join(pos)
        groups = [
            group for group in groups if title.lower() in group.title.lower()
        ]
    if not groups:
        bot.send_message(message.chat.id, "No groups found.")
        return
    msg = list_many_groups(groups)
    bot.send_message(message.chat.id, msg)
