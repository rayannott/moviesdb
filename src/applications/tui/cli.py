"""CLI entry point for the TUI application."""

import click

from src.dependencies import Container


@click.command()
@click.version_option(package_name="moviesdb")
@click.option("--fulltui", is_flag=True, help="Launch full-screen TUI.")
def main(fulltui: bool) -> None:
    """Movies & series personal database — TUI."""
    container = Container()
    if fulltui:
        from src.applications.fulltui.app import create_fulltui_app

        create_fulltui_app(container).run()
    else:
        from src.applications.tui.app import create_app

        create_app(container).run()
