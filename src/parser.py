import re
from shlex import split


class ParsingError(ValueError):
    pass


PositionalArgs = list[str]
KeywordArgs = dict[str, str]
Flags = set[str]


VALID_ROOT_NAME_RE = re.compile(r"^\w[\w-]*$")


def parse(cmd: str) -> tuple[str, PositionalArgs, KeywordArgs, Flags]:
    """
    Parse a command string into root command, positional arguments, keyword arguments, and flags.

    >>> parse("tag add")
    ("tag", ["add"], {}, set())
    >>> parse("util --on")
    ("util", [], {}, {"on"})
    >>> parse("cmd help --n=10")
    ("cmd", ["help"], {"n": 10}, set())
    >>> parse("abcd --do this --and that --then=those --verbose")
    ("abcd", [], {"do": "this", "and": "that", "then": "those"}, {"verbose"})
    >>> parse("cmd --do --this")
    ("cmd", [], {}, {"do", "this"})
    >>> parse("cmd abc --do this --not --that --then=those --flag")
    ("cmd", ["abc"], {"do": "this", "then": "those"}, {"not", "that", "flag"})
    >>> parse('watch movie --online --title="how are you"')
    ("watch", ["movie"], {"title": "how are you"}, {"online"})
    >>> parse("")
    Traceback (most recent call last):
        ...
    ParsingError


    Raises
        ParsingError: If the command string is malformed or contains invalid arguments.
    """

    def is_flag(s: str) -> bool:
        return s.startswith(("--", "—"))

    def strip_flag_chrs(s: str) -> str:
        return s.lstrip("-—")

    try:
        parts = split(cmd)
    except ValueError as e:
        raise ParsingError(str(e))

    if not parts:
        raise ParsingError(" No command provided.")

    root: str = parts.pop(0)

    if not VALID_ROOT_NAME_RE.match(root):
        raise ParsingError(
            f" Invalid command name {root!r}. "
            "Command names can only contain alphanumeric characters, underscores, and hyphens,"
            " and must start with an alphanumeric character."
        )

    positional: PositionalArgs = []
    kwargs: KeywordArgs = {}
    flags: Flags = set()

    i = 0
    while i < len(parts):
        token = parts[i]
        if is_flag(token):
            arg = strip_flag_chrs(token)
            if not arg:
                raise ParsingError(" Empty flag/key name.")
            if "=" in arg:
                key, value = arg.split("=", 1)
                if not value:
                    raise ParsingError(f" Empty value for argument {key!r}.")
                kwargs[key] = value
            else:
                if i + 1 < len(parts) and not is_flag(parts[i + 1]):
                    kwargs[arg] = parts[i + 1]
                    i += 1
                else:
                    flags.add(arg)
        else:
            if flags or kwargs:
                raise ParsingError(
                    f" Invalid positional argument {token!r} after flags or keyword arguments."
                )
            positional.append(token)
        i += 1

    return root, positional, kwargs, flags
