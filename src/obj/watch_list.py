from collections.abc import Callable


class WatchList:
    def __init__(self, watch_list_entries: list[tuple[str, bool]]):
        self.watch_list = watch_list_entries

    @property
    def titles(self) -> list[str]:
        return [entry[0] for entry in self.watch_list]

    @property
    def movies(self) -> list[str]:
        return [entry[0] for entry in self.watch_list if not entry[1]]

    @property
    def series(self) -> list[str]:
        return [entry[0] for entry in self.watch_list if entry[1]]

    def __contains__(self, title_is_series: tuple[str, bool]) -> bool:
        return title_is_series in self.watch_list

    def __eq__(self, other: "WatchList") -> bool:  # type: ignore[override]
        return self.watch_list == other.watch_list

    def remove(self, title: str, is_series: bool):
        try:
            idx = self.watch_list.index((title, is_series))
            self.watch_list.pop(idx)
            return True
        except ValueError:
            return False

    def add(self, title: str, is_series: bool):
        if (title, is_series) not in self.watch_list:
            self.watch_list.append((title, is_series))
            return True
        return False

    def __len__(self) -> int:
        return len(self.watch_list)

    def __iter__(self):
        return iter(self.titles)

    def filter_items(self, key: Callable[[str, bool], bool]) -> list[tuple[str, bool]]:
        return [entry for entry in self.watch_list if key(*entry)]

    def items(self) -> list[tuple[str, bool]]:
        return self.watch_list

    def get(self, title: str, default=None) -> bool | None:
        for entry in self.watch_list:
            if entry[0] == title:
                return entry[1]
        return default

    def copy(self):
        return WatchList(self.watch_list.copy())
