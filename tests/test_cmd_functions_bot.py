import inspect

from telebot import TeleBot, types

from botsrc.compiled import load_bot_commands


def test_cmd_functions_bot():
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

    bot_commands = load_bot_commands()

    for bot_command in bot_commands.values():
        assert inspect.signature(bot_command) == SIGNATURE, (
            f"{bot_command} has a wrong signature."
        )
