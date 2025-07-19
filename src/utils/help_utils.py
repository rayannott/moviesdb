from rich.text import Text
from rich.table import Table
from rich.align import Align

from src.utils.rich_utils import get_rich_table
from src.utils.utils import possible_match


_missing = object()


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


def get_rich_help(
    query: str | None, help_messages: dict[str, tuple[str, str, str] | None]
) -> Text | Table | Align:
    headers = ["Command", "Description", "Details"]
    styles = ["cyan", "white", "white"]
    if query is None:
        return get_rich_table(
            [list(v) for v in help_messages.values() if v is not None],
            headers,
            styles=styles,  # type: ignore
            title="Help",
        )
    this_help = help_messages.get(query, _missing)
    if this_help is _missing:
        res = f'Unknown command: "{query}". '
        if (pm := possible_match(query, set(help_messages))) is not None:
            res += f'Did you mean "{pm}"?'
        return Text(res, style="bold red")
    if this_help is None:
        return Text("Help message is missing.", style="bold red")
    return get_rich_table([list(this_help)], headers=headers, styles=styles)  # type: ignore
