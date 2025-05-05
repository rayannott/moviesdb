import telebot

from src.mongo import Mongo
from botsrc.utils import format_title
from src.parser import Flags, PositionalArgs, KeywordArgs


def watch(
    message: telebot.types.Message,
    bot: telebot.TeleBot,
    pos: PositionalArgs,
    flags: Flags,
    kwargs: KeywordArgs,
):
    watch_list = Mongo.load_watch_list()
    if not (pos or kwargs or flags):
        bot.send_message(
            message.chat.id,
            f"Movies: {', '.join(watch_list.movies)}\n\nSeries: {', '.join(watch_list.series)}",
        )
        return
    if "guest" in flags:
        bot.reply_to(message, "Sorry, you can't modify anything.")
        return
    watch_title = " ".join(pos)
    is_series = watch_title.endswith("+")
    title = watch_title.rstrip("+ ")
    title_fmt = format_title(title, is_series)
    if "delete" in flags:
        if not watch_list.remove(title, is_series):
            bot.reply_to(message, f"{title_fmt} is not in the watch list.")
            return
        if not Mongo.delete_watchlist_entry(title, is_series):
            bot.reply_to(message, f"There is no such watch list entry: {title_fmt}.")
            return
        bot.send_message(message.chat.id, f"Deleted {title_fmt} from watch list.")
        return
    if not watch_list.add(title, is_series):
        bot.reply_to(message, f"{title_fmt} is already in the watch list.")
        return
    Mongo.add_watchlist_entry(title, is_series)
    bot.send_message(message.chat.id, f"Added {title_fmt} to watch list.")
