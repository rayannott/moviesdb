from collections.abc import Callable


def parse_docstring(docstring: str | None) -> tuple[str, str, str] | None:
    """
    Parses the docstring of a command and returns a tuple:
    - signature
    - short description
    - rest of the docstring"""
    if docstring is None:
        return None
    lines = docstring.splitlines()
    assert len(lines) >= 2, "Docstring must have at least 2 lines"
    signature = lines[0]
    short_desc = lines[1]
    rest = "\n".join(lines[2:])
    return signature, short_desc, rest


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
