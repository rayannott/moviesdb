import pathlib
import warnings

SQL_QUERY_EXAMPLES_DIR = pathlib.Path("query-examples-local")

PERSISTENT_MEMORY_FILE = pathlib.Path("local") / "persistent_memory.dat"
# TODO: make another document store instead

if not PERSISTENT_MEMORY_FILE.exists():
    warnings.warn(
        f"persistent memory file doesn't exist under {PERSISTENT_MEMORY_FILE}"
    )
