import telebot

from src.mongo import Mongo
from botsrc.utils import select_entry_by_oid_part, format_entry
from src.parser import PositionalArgs


def pop(
    message: telebot.types.Message,
    bot: telebot.TeleBot,
    pos: PositionalArgs,
):
    if not pos:
        bot.reply_to(message, "You must specify an oid.")
        return
    entries = sorted(Mongo.load_entries())
    selected_entry = select_entry_by_oid_part(pos[0], entries)
    if selected_entry is None:
        bot.reply_to(message, "Could not find a unique entry.")
        return
    assert selected_entry._id
    if Mongo.delete_entry(selected_entry._id):
        bot.send_message(
            message.chat.id, f"Deleted successfully:\n{format_entry(selected_entry)}"
        )
    else:
        bot.reply_to(message, "Something went wrong.")
