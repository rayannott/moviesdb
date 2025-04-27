import inspect
from collections.abc import Callable

from telebot import TeleBot, types

from src.parser import Flags, KeywordArgs, PositionalArgs
import botsrc.cmds as botcmd


def load_bot_commands():
    SIGNATURE = inspect.Signature(
        parameters=[
            inspect.Parameter(
                "pos",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=list[str],
            ),
            inspect.Parameter(
                "kwargs",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=dict[str, str],
            ),
            inspect.Parameter(
                "flags",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=set[str],
            ),
            inspect.Parameter(
                "bot",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=TeleBot,
            ),
            inspect.Parameter(
                "message",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=types.Message,
            ),
        ]
    )

    bot_commands: dict[
        str,
        Callable[[PositionalArgs, KeywordArgs, Flags, TeleBot, types.Message], None],
    ] = {
        method_name[4:]: getattr(botcmd, method_name)
        for method_name in dir(botcmd)
        if method_name.startswith("cmd_")
    }

    for bot_command in bot_commands.values():
        assert inspect.signature(bot_command) == SIGNATURE, (
            f"{bot_command} has a wrong signature."
        )

    return bot_commands


BOT_COMMANDS = load_bot_commands()
