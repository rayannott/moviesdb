import inspect

from rich.console import Console

from src.obj.books_mode import BooksMode

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
    ]
)


def test_cmd_signatures():
    _mock_console = Console()
    _mock_entries = []

    def _mock_input(x: str) -> str:
        return x

    app = BooksMode(_mock_entries, _mock_console, _mock_input)
    for cmd_method in app.command_methods.values():
        assert inspect.signature(cmd_method) == SIGNATURE
