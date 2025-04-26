import datetime
import warnings
from dataclasses import dataclass

import requests
from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel

from src.utils.env import OMDB_API_KEY


URL_BASE = "http://www.omdbapi.com"


@dataclass
class DataBaseResponse:
    title: str
    year: str
    rated: str
    release_date: datetime.date | None
    runtime: str
    director: str
    actors: str
    plot: str
    genre: str
    country: str
    imdb_rating: float | None
    imdb_votes: int
    imdb_id: str

    @classmethod
    def from_json_response(cls, response: dict) -> "DataBaseResponse":
        return cls(
            title=response["Title"],
            year=response["Year"],
            rated=response["Rated"],
            release_date=datetime.datetime.strptime(
                response["Released"], "%d %b %Y"
            ).date()
            if response["Released"] != "N/A"
            else None,
            runtime=response["Runtime"],
            director=response["Director"],
            actors=response["Actors"],
            plot=response["Plot"],
            genre=response["Genre"],
            country=response["Country"],
            imdb_rating=float(response["imdbRating"])
            if response["imdbRating"] != "N/A"
            else None,
            imdb_votes=response["imdbVotes"],
            imdb_id=response["imdbID"],
        )

    def rich(self) -> Group:
        """Returns a markdown-formatted string representing the movie data."""
        year_str = (
            f"{self.year[0]}-{self.year[1]}"
            if isinstance(self.year, tuple)
            else str(self.year)
        )
        md = Markdown(
            f"# {self.title} ({year_str})\n"
            f"- **Release Date**: {self.release_date.strftime('%d %b %Y') if self.release_date else 'N/A'}\n\n"
            f"- **IMDb Rating**: {self.imdb_rating} ({self.imdb_votes} votes)\n\n"
            f"- **Runtime**: {self.runtime}\n\n"
            f"- **Director**: {self.director}\n\n"
            f"- **Actors**: {self.actors}\n\n"
            f"- **Genre**: {self.genre}\n\n"
            f"- **Country**: {self.country}\n\n"
            f"- **Rated**: {self.rated}\n\n"
            f"- **IMDB Link**: https://www.imdb.com/title/{self.imdb_id}\n\n"
        )
        plot_panel = Panel(self.plot)
        return Group(md, plot_panel)


def get_by_title(title: str) -> DataBaseResponse | None:
    if OMDB_API_KEY is None:
        warnings.warn("OMDB API key not found in environment variables.")
    url = f"{URL_BASE}/?apikey={OMDB_API_KEY}&t={title}"
    response = requests.get(url)
    json_response = response.json()
    if json_response.get("Response") != "True":
        return None
    return DataBaseResponse.from_json_response(json_response)
