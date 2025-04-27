import telebot

from botsrc.utils import ME_CHAT_ID


def suggest(message: telebot.types.Message, bot: telebot.TeleBot):
    if message.text is None:
        bot.reply_to(message, "Please provide a text message.")
        return
    username = message.from_user.username if message.from_user else ""
    name = message.from_user.first_name if message.from_user else ""
    # TODO: add logic and next step hanlers

    bot.send_message(
        ME_CHAT_ID, f"Suggestion from {name}(@{username}):\n{message.text}"
    )
    bot.send_message(message.chat.id, "Thank you for your suggestion!")
