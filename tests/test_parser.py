import pytest

from src.parser import parse

TESTS = [
    ("tag add", ("tag", ["add"], {}, set())),
    ("util --on", ("util", [], {}, {"on"})),
    ("cmd help --n=10", ("cmd", ["help"], {"n": "10"}, set())),
    (
        "abcd --do this --and that --then=those --verbose",
        ("abcd", [], {"do": "this", "and": "that", "then": "those"}, {"verbose"}),
    ),
    ("cmd --do --this", ("cmd", [], {}, {"do", "this"})),
    (
        "cmd abc --do this --not --that --then=those --flag",
        ("cmd", ["abc"], {"do": "this", "then": "those"}, {"not", "that", "flag"}),
    ),
    (
        'watch movie --online --title="how are you"',
        ("watch", ["movie"], {"title": "how are you"}, {"online"}),
    ),
]


@pytest.mark.parametrize(
    "cmd, expected",
    TESTS,
)
def test_parser(cmd, expected):
    assert parse(cmd) == expected
