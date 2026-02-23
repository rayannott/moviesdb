"""CLI entry point for the TUI application."""

import click

from src.applications.tui.app import create_app
from src.dependencies import Container


@click.command()
@click.version_option(package_name="moviesdb")
def main() -> None:
    """Movies & series personal database — TUI."""
    container = Container()
    app = create_app(container)
    app.run()
