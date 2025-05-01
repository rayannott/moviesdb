import telebot

from src.utils.utils import AccessRightsManager
from src.parser import KeywordArgs


def guest(
    message: telebot.types.Message,
    bot: telebot.TeleBot,
    kwargs: KeywordArgs,
):
    am = AccessRightsManager()
    if (name := kwargs.get("add")) is not None:
        am.add(name)
        msg = f"{name} added to the guests list"
    elif (name := kwargs.get("remove")) is not None:
        is_ok = am.remove(name)
        msg = (
            f"{name} removed from the guests list"
            if is_ok
            else f"{name} was not in the guest list"
        )
    else:
        msg = "Guests: " + ", ".join(am.guests)
    bot.send_message(message.chat.id, msg)
