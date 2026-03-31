"""CLI entry point for the TUI application."""

import click
import cryptography.fernet

from src.settings import needs_unlock, unlock_secrets


@click.command()
@click.version_option(package_name="moviesdb")
def main() -> None:
    """Movies & series personal database — TUI."""
    if needs_unlock():
        password = click.prompt("Unlock secrets", hide_input=True)
        try:
            unlock_secrets(password)
        except cryptography.fernet.InvalidToken:
            click.echo("Failed to decrypt secrets. Wrong password?", err=True)
            raise SystemExit(1)

    # Deferred: Container class body calls Settings() at definition time,
    # so it must be imported after secrets are available in os.environ.
    from src.applications.tui.app import create_app
    from src.dependencies import Container

    container = Container()
    app = create_app(container)
    app.run()
