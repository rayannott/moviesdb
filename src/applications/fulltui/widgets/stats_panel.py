"""Compact statistics panel and rating distribution widgets."""

from collections import Counter
from statistics import mean, stdev

from rich.text import Text
from textual.widgets import Sparkline, Static

from src.services.entry_service import StatsResult


def _std(data: list[float]) -> float:
    return stdev(data) if len(data) > 1 else 0.0


def _rating_color(rating: float) -> str:
    min_val, max_val = 3.0, 10.0
    clamped = max(min_val, min(rating, max_val))
    ratio = (clamped - min_val) / (max_val - min_val)
    r = round(255 * (1 - ratio))
    g = round(255 * ratio)
    return f"rgb({r},{g},0)"


class StatsPanel(Static):
    """Compact panel showing database statistics."""

    def __init__(self, stats: StatsResult, **kwargs) -> None:  # type: ignore[override]
        super().__init__(**kwargs)
        self._stats = stats

    def on_mount(self) -> None:
        self.update(self._build())

    def _build(self) -> Text:
        s = self._stats
        lines = Text()

        lines.append("  Entries  ", style="bold underline")
        lines.append(f"\n  Total: {s.total}\n")

        if s.movie_ratings:
            avg_m = mean(s.movie_ratings)
            std_m = _std(s.movie_ratings)
            color_m = _rating_color(avg_m)
            lines.append("  Movies:  ")
            lines.append(f"{avg_m:.2f}", style=color_m)
            lines.append(f" ± {std_m:.2f}  (n={len(s.movie_ratings)})\n")

        if s.series_ratings:
            avg_s = mean(s.series_ratings)
            std_s = _std(s.series_ratings)
            color_s = _rating_color(avg_s)
            lines.append("  Series:  ")
            lines.append(f"{avg_s:.2f}", style=color_s)
            lines.append(f" ± {std_s:.2f}  (n={len(s.series_ratings)})\n")

        unique = len(s.groups)
        rewatched = sum(1 for g in s.groups if len(g.ratings) > 1)
        lines.append(f"\n  Unique titles: {unique}\n")
        lines.append(f"  Re-watched: {rewatched}\n")

        lines.append(f"\n  Watchlist: {s.watchlist_count}")
        lines.append(f"  ({s.watchlist_movies_count}m / {s.watchlist_series_count}s)")

        return lines


class RatingDistributionPanel(Static):
    """Compact panel with a sparkline histogram of ratings."""

    def __init__(self, all_ratings: list[float], **kwargs) -> None:  # type: ignore[override]
        super().__init__(**kwargs)
        self._ratings = all_ratings

    def compose(self):  # type: ignore[override]
        counts = Counter(int(r) for r in self._ratings)
        data = [float(counts.get(i, 0)) for i in range(1, 11)]
        yield Static("  Rating distribution", classes="dist-label")
        yield Sparkline(data, summary_function=max, id="sparkline")
        labels = "  ".join(f"{i:>2}" for i in range(1, 11))
        yield Static(f"  {labels}", classes="dist-axis")
