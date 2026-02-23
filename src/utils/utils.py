import datetime
import difflib
import re
import subprocess

DATE_PATTERNS = ["%d.%m.%Y", "%d.%m.%y"]


HASHTAG_RE = re.compile(r"#[\w-]+")
RATINGS_RE = re.compile(r"\[([0-9 _.]+)\]")


F_SERIES = "series"
F_MOVIES = "movies"
F_ALL = "all"

TAG_WATCH_AGAIN = "watch-again"
TAG_WATCH_AGAIN_ALIAS = "wa"


def replace_tag_alias(tagname: str) -> str:
    return tagname if tagname != TAG_WATCH_AGAIN_ALIAS else TAG_WATCH_AGAIN


def find_hashtags(text: str) -> set[str]:
    return set(replace_tag_alias(ht[1:]) for ht in HASHTAG_RE.findall(text))


def remove_hashtags(text: str) -> str:
    return HASHTAG_RE.sub("", text).strip()


def parse_per_season_ratings(note_str: str) -> list[float | None]:
    def try_float(s: str) -> float | None:
        try:
            return float(s)
        except (ValueError, TypeError):
            return None

    match_ = RATINGS_RE.search(note_str)
    if not match_:
        return []
    ratings = match_.group(1).split()
    return [try_float(r) for r in ratings]


def different_lines(text1: str, text2: str) -> list[str]:
    lines1 = text1.splitlines()
    lines2 = text2.splitlines()
    return [
        line
        for line in difflib.unified_diff(lines1, lines2, lineterm="")
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]


def possible_match(
    token: str, tokens: set[str], score_threshold: float = 0.6
) -> str | None:
    """Returns the most similar token to `token`
    from the set of tokens `tokens` given that
    its score is at least `score_threshold`."""
    # token_score_pairs = [
    #     (tok, score)
    #     for tok in tokens
    #     if (score := difflib.SequenceMatcher(None, token, tok).ratio()) >= score_threshold
    # ]
    # return max(token_score_pairs, key=lambda x: x[1], default=(None, 0))[0]
    matches = difflib.get_close_matches(token, tokens, n=1, cutoff=score_threshold)
    return matches[0] if matches else None


def parse_date(date_str: str) -> datetime.datetime | None:
    if date_str == "None":
        return None
    for pattern in DATE_PATTERNS:
        try:
            return datetime.datetime.strptime(date_str, pattern)
        except ValueError:
            continue
    return None


def is_installed(cmd: str) -> bool:
    try:
        subprocess.run(
            [cmd, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return True
    except FileNotFoundError:
        return False
