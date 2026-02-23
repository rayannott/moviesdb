import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from time import perf_counter as pc
from zoneinfo import ZoneInfo

from src.repos.entries import EntriesRepo
from src.repos.watchlist_entries import WatchlistEntriesRepo
from src.paths import LOCAL_DIR


@dataclass
class ExportResult:
    """Result of an export operation."""

    entries_count: int = 0
    watchlist_count: int = 0
    new_images_count: int = 0
    timings: dict[str, float] = field(default_factory=dict)


class ExportService:
    """Business logic for exporting data to local files."""

    def __init__(
        self,
        entries_repo: EntriesRepo,
        watchlist_repo: WatchlistEntriesRepo,
    ) -> None:
        self._entries_repo = entries_repo
        self._watchlist_repo = watchlist_repo

    def export_entries_and_watchlist(
        self, export_dir: Path | None = None
    ) -> ExportResult:
        """Export entries and watchlist to JSON files."""
        export_dir = export_dir or LOCAL_DIR
        export_dir.mkdir(exist_ok=True)
        result = ExportResult()

        t0 = pc()
        entries = sorted(self._entries_repo.get_all())
        dbfile = export_dir / "db.json"
        with dbfile.open("w", encoding="utf-8") as f:
            json.dump(
                [entry.to_mongo_dict() for entry in entries],
                f,
                indent=2,
                ensure_ascii=False,
            )
        result.entries_count = len(entries)
        t1 = pc()
        result.timings["entries"] = t1 - t0

        watchlist = self._watchlist_repo.get_all()
        wlfile = export_dir / "watch_list.json"
        with wlfile.open("w", encoding="utf-8") as f:
            json.dump(
                [(w.title, w.is_series) for w in watchlist],
                f,
                indent=2,
                ensure_ascii=False,
            )
        result.watchlist_count = len(watchlist)
        t2 = pc()
        result.timings["watch_list"] = t2 - t1

        self._dump_meta(result.timings, with_images=False, export_dir=export_dir)
        return result

    @staticmethod
    def _dump_meta(
        timings: dict[str, float],
        with_images: bool,
        export_dir: Path,
    ) -> None:
        with open(export_dir / "_meta.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "now": datetime.now(tz=ZoneInfo("Europe/Berlin")).isoformat(),
                    "with_images": with_images,
                    "exported_in_sec": timings,
                },
                f,
                indent=2,
            )
