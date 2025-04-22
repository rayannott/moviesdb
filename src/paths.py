import pathlib
import warnings

DB_FILE = pathlib.Path("db.json")
WATCH_LIST_FILE = pathlib.Path("watch_list.json")
SQL_QUERY_EXAMPLES_DIR = pathlib.Path("query-examples")

PERSISTENT_MEMORY_FILE = pathlib.Path("local") / "persistent_memory.dat"

if not PERSISTENT_MEMORY_FILE.exists():
    warnings.warn(
        f"persistent memory file doesn't exist under {PERSISTENT_MEMORY_FILE}"
    )
