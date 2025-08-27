import datetime
import difflib
import json
import logging
import re

from git import Commit, Repo

from src.paths import ALLOWED_USERS

logger = logging.getLogger(__name__)

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


class AccessRightsManager:
    def __init__(self):
        self.guests = self.load_allowed_users()

    @staticmethod
    def load_allowed_users() -> set[str]:
        if not ALLOWED_USERS.exists():
            return set()
        with ALLOWED_USERS.open("r") as f:
            return set(json.load(f))

    def dump_allowed_users(self):
        with ALLOWED_USERS.open("w") as fw:
            json.dump(list(self.guests), fw)

    def add(self, username: str):
        self.guests.add(username)
        self.dump_allowed_users()

    def remove(self, username: str) -> bool:
        if username not in self.guests:
            return False
        self.guests.remove(username)
        self.dump_allowed_users()
        return True

    def __contains__(self, username: str) -> bool:
        self.guests = self.load_allowed_users()
        return username in self.guests


class RepoInfo:
    def __init__(self):
        try:
            self.repo: Repo | None = Repo(".")
            self.recent_commits = list(self.repo.iter_commits(max_count=5))
            self.on_branch: str | None = self.repo.active_branch.name
            self.last_commit: Commit | None = self.recent_commits[0]
        except Exception as e:
            logger.error(f"Error initializing RepoInfo: {e}")
            self.repo = None
            self.recent_commits = []
            self.on_branch = None
            self.last_commit = None

    def get_last_commit_timestamp(self) -> str:
        return (
            self.last_commit.authored_datetime.strftime("%d %b %Y")
            if self.last_commit
            else "Unknown"
        )

    def get_branch(self) -> str:
        return self.on_branch if self.on_branch else "Unknown"

    def get_last_commit(self) -> Commit | None:
        return self.last_commit if self.last_commit else None
