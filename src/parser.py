from shlex import split


class ParsingError(ValueError):
    pass


PositionalArgs = list[str]
KeywordArgs = dict[str, str]
Flags = set[str]


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
    """

    def is_flag(s: str) -> bool:
        return s.startswith("--")

    try:
        parts = split(cmd)
    except ValueError as e:
        raise ParsingError(str(e))

    if not parts:
        raise ParsingError(" No command provided.")

    root: str = parts.pop(0)

    positional: PositionalArgs = []
    kwargs: KeywordArgs = {}
    flags: Flags = set()

    i = 0
    while i < len(parts):
        token = parts[i]
        if is_flag(token):
            arg = token[2:]
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
            positional.append(token)
        i += 1

    return root, positional, kwargs, flags
