import pathlib

SQL_QUERY_EXAMPLES_DIR = pathlib.Path("query-examples-local")
SQL_QUERY_EXAMPLES_DIR.mkdir(exist_ok=True)

LOCAL_DIR = pathlib.Path("export-local")
ALLOWED_USERS = LOCAL_DIR / "allowed_users.json"

STDOUT_STREAM_FILE = pathlib.Path("bot.out")

LOGS_DIR = pathlib.Path("logs")
LOGS_DIR.mkdir(exist_ok=True)
