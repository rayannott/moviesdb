import pytest

from src.parser import parse, ParsingError

TESTS = [
    ("tag add", ("tag", ["add"], {}, set())),
    ("util --on", ("util", [], {}, {"on"})),
    ("cmd help --n=10", ("cmd", ["help"], {"n": "10"}, set())),
    (
        "abcd --do this --and that --then=those --verbose",
        ("abcd", [], {"do": "this", "and": "that", "then": "those"}, {"verbose"}),
    ),
    ("cmd --do --this", ("cmd", [], {}, {"do", "this"})),
    ('cmd --key ""', ("cmd", [], {"key": ""}, set())),
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


def test_empty_string():
    with pytest.raises(ParsingError):
        parse("")


def test_empty_flag_name():
    with pytest.raises(ParsingError):
        parse("cmd --")


def test_empty_keyword_arg_name():
    with pytest.raises(ParsingError):
        parse("cmd --key=")


def test_misplaced_positional_arg():
    with pytest.raises(ParsingError):
        parse("cmd --key val misplaced")


@pytest.mark.parametrize(
    "cmd",
    [
        "-name",
        "--name",
        "--name",
        "ab=cd",
    ],
)
def test_misplaced_flag(cmd):
    with pytest.raises(ParsingError):
        parse(cmd)
