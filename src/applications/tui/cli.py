"""CLI entry point for the TUI application."""

import click


@click.command()
@click.version_option(package_name="moviesdb")
def main() -> None:
    """Movies & series personal database — TUI."""
    from src.applications.tui.app import TUIApp
    from src.dependencies import Container

    container = Container()
    app = TUIApp(
        entry_service=container.entry_service(),
        watchlist_service=container.watchlist_service(),
        chatbot_service=container.chatbot_service(),
        guest_service=container.guest_service(),
        export_service=container.export_service(),
        image_service=container.image_service(),
    )
    app.run()
