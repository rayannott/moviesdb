import pathlib

SQL_QUERY_EXAMPLES_DIR = pathlib.Path("query-examples-local")
SQL_QUERY_EXAMPLES_DIR.mkdir(exist_ok=True)

LOCAL_DIR = pathlib.Path.home() / ".local" / "share" / "moviesdb"
LOCAL_DIR.mkdir(parents=True, exist_ok=True)

STDOUT_STREAM_FILE = pathlib.Path("bot.out")

LOGS_DIR = pathlib.Path("logs")
LOGS_DIR.mkdir(exist_ok=True)
