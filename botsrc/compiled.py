from collections.abc import Callable

from telebot import TeleBot, types

from src.parser import Flags, KeywordArgs, PositionalArgs
import botsrc.cmds as botcmd


def load_bot_commands():
    bot_commands: dict[
        str,
        Callable[[PositionalArgs, KeywordArgs, Flags, TeleBot, types.Message], None],
    ] = {
        method_name[4:]: getattr(botcmd, method_name)
        for method_name in dir(botcmd)
        if method_name.startswith("cmd_")
    }
    return bot_commands


BOT_COMMANDS = load_bot_commands()
