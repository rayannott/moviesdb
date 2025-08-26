import logging

import telebot
from telebot import types

from src.parser import Flags

logger = logging.getLogger(__name__)


def image(
    message: types.Message,
    bot: telebot.TeleBot,
    flags: Flags,
): ...
