import logging

import telebot

from botsrc.utils import ME_CHAT_ID

logger = logging.getLogger(__name__)


def suggest(message: telebot.types.Message, bot: telebot.TeleBot):
    if message.text is None or not message.text.strip():
        bot.reply_to(message, "Please provide a text message.")
        logger.info("empty message text")
        return
    username = message.from_user.username if message.from_user else ""
    name = message.from_user.first_name if message.from_user else ""
    # TODO: add logic and next step hanlers

    sugg_text = f"Suggestion from {name}(@{username}):\n{message.text}"
    bot.send_message(ME_CHAT_ID, sugg_text)
    bot.send_message(message.chat.id, "Thank you for your suggestion!")
    logger.info(sugg_text)
