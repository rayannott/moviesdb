from collections.abc import Callable

from src.utils.help_utils import parse_docstring


def get_help(commands: dict[str, Callable], command: str | None = None) -> str:
    """
    Returns the help message for a command or all commands if no command is specified.
    """
    if command is None:
        return "\n".join(
            f"/{cmd} - {parsed_doc[1]}\n  {parsed_doc[0]}"
            if (parsed_doc := parse_docstring(func.__doc__)) is not None
            else f"/{cmd}"
            for cmd, func in commands.items()
        )
    func = commands.get(command)
    if func is None:
        return f"Command {command!r} not found."
    docstring = parse_docstring(func.__doc__)
    if docstring is None:
        return f"Command /{command} has no documentation."
    return f"/{command}\n" + "\n".join(docstring)
