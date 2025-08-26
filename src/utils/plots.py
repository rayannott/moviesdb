import datetime
from collections import defaultdict
from math import sqrt
from statistics import mean, stdev

import plotly.graph_objects as go
import plotly.io as pio

from src.obj.entry import Entry

pio.renderers.default = "browser"


def get_plot(entries: list[Entry]) -> go.Figure:
    def factory() -> tuple[list[float], list[float], list[str], list[str]]:
        return ([], [], [], [])

    def mean_f(sequence: list[float]) -> float:
        return mean(sequence) if sequence else 0.0

    def sem_f(sequence: list[float]) -> float:
        return stdev(sequence) / sqrt(len(sequence)) if len(sequence) > 1 else 0.0

    def month_start(year: int, month: int) -> datetime.date:
        return datetime.date(year, month, 1)

    data: defaultdict[
        tuple[int, int], tuple[list[float], list[float], list[str], list[str]]
    ] = defaultdict(factory)
    for entry in entries:
        if entry.date is None:
            continue
        year, month = entry.date.year, entry.date.month
        formatted_entry = (
            f"[{entry.rating:.2f}] <b>{entry.title}</b> ({entry.date:%d.%m})"
        )
        if not entry.is_series:
            data[(year, month)][0].append(entry.rating)
            data[(year, month)][2].append(formatted_entry)
        else:
            data[(year, month)][1].append(entry.rating)
            data[(year, month)][3].append(formatted_entry)

    months = sorted(data.keys())
    month_labels = [month_start(year, month) for year, month in months]

    movie_means = [mean_f(data[month][0]) for month in months]
    movie_sems = [sem_f(data[month][0]) for month in months]
    movie_hover_texts = ["<br>".join(data[month][2]) for month in months]

    series_means = [mean_f(data[month][1]) for month in months]
    series_sems = [sem_f(data[month][1]) for month in months]
    series_hover_texts = ["<br>".join(data[month][3]) for month in months]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            name="Movies",
            x=month_labels,
            y=movie_means,
            error_y=dict(
                type="data",
                array=movie_sems,
                visible=True,
            ),
            marker_color="lightblue",
            text=movie_hover_texts,
            textposition="none",
            hovertemplate=("%{y:.2f} ± %{error_y.array:.2f}<br><extra>%{text}</extra>"),
        )
    )

    fig.add_trace(
        go.Bar(
            name="Series",
            x=month_labels,
            y=series_means,
            error_y=dict(
                type="data",
                array=series_sems,
                visible=True,
            ),
            marker_color="lightcoral",
            text=series_hover_texts,
            textposition="none",
            hovertemplate=("%{y:.2f} ± %{error_y.array:.2f}<br><extra>%{text}</extra>"),
        )
    )

    today = datetime.datetime.now().date()
    two_years_ago = today.replace(year=today.year - 2)

    fig.update_layout(
        barmode="group",
        title="Average Ratings per Month",
        xaxis_title="Month",
        yaxis_title="Rating",
        template="plotly_dark",
        xaxis=dict(
            tickformat="%Y-%m",
            tickangle=45,
            range=[two_years_ago, today],
            fixedrange=False,
        ),
        dragmode="pan",
        yaxis=dict(
            fixedrange=True,
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=1.1,
            xanchor="center",
            x=0.5,
        ),
    )

    return fig
