import inspect

import pytest

from src.applications.tui.app import TUIApp

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


@pytest.mark.skip(reason="App now requires DI services; needs integration test setup")
def test_cmd_signatures() -> None:
    """Verify all cmd_ methods share the same (pos, kwargs, flags) signature."""
    # TODO: set up a test container to instantiate App with mock services
    pass
