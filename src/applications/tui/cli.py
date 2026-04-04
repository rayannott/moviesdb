"""CLI entry point for the TUI application."""

import click
from cryptography.fernet import InvalidToken

from src.applications.tui.crypt_cli import crypt_group
from src.settings import needs_unlock, unlock_secrets


@click.group(invoke_without_command=True)
@click.version_option(package_name="moviesdb")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Movies & series personal database — TUI."""
    if ctx.invoked_subcommand is None:
        _run_tui()


main.add_command(crypt_group)


def _run_tui() -> None:
    if needs_unlock():
        password = click.prompt("Unlock secrets", hide_input=True)
        try:
            unlock_secrets(password)
        except InvalidToken:
            click.echo("Failed to decrypt secrets. Wrong password?", err=True)
            raise SystemExit(1)
        click.echo("\033[A\033[2K", nl=False)  # erase the prompt line

    # Deferred: Container class body calls Settings() at definition time,
    # so it must be imported after secrets are available in os.environ.
    from src.applications.tui.app import create_app
    from src.dependencies import Container

    container = Container()
    app = create_app(container)
    app.run()
