import inspect

from src.app import App

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
    app = App()
    for cmd_method in app.command_methods.values():
        assert inspect.signature(cmd_method) == SIGNATURE
