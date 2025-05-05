import telebot

from src.mongo import Mongo
from botsrc.utils import list_many_entries
from src.parser import Flags


def list_(
    message: telebot.types.Message,
    bot: telebot.TeleBot,
    flags: Flags,
):
    if "guest" in flags:
        flags = set()
    entries = sorted(Mongo.load_entries())
    msg = list_many_entries(
        entries[-5:],
        "verbose" in flags,
        "oid" in flags,
        override_title="Last 5 entries:",
    )
    bot.send_message(message.chat.id, msg)
