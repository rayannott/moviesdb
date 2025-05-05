import telebot

from src.mongo import Mongo
from botsrc.utils import list_many_entries
from src.parser import Flags, PositionalArgs


def find(
    message: telebot.types.Message,
    bot: telebot.TeleBot,
    pos: PositionalArgs,
    flags: Flags,
):
    if not pos:
        bot.reply_to(message, "You must specify a title.")
        return
    if "guest" in flags:
        flags = set()
    title = " ".join(pos)
    entries = sorted(Mongo.load_entries())
    filtered = [ent for ent in entries if title.lower() in ent.title.lower()]
    if not filtered:
        bot.reply_to(message, f"No entries found with {title!r}.")
        return
    res = list_many_entries(filtered, "verbose" in flags, "oid" in flags)
    bot.send_message(message.chat.id, res)
