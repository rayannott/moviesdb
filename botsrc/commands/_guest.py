import logging

import telebot
from telebot import types

from src.parser import KeywordArgs
from src.utils.utils import AccessRightsManager

logger = logging.getLogger(__name__)


def guest(
    message: types.Message,
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
    logger.info(f"{msg}; (current guests: {am.guests})")
