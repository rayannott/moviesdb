"""CLI tool for managing API users."""

import getpass

import click

from src.applications.api.auth import AuthUser, UserRole, hash_password, load_users, save_users
from src.settings import Settings


@click.group()
def cli() -> None:
    """Manage MoviesDB API users."""


@cli.command()
@click.argument("username")
@click.option(
    "--role",
    type=click.Choice([r.value for r in UserRole]),
    default=UserRole.VIEWER,
    help="User role (default: viewer).",
)
def add(username: str, role: str) -> None:
    """Add a new API user."""
    settings = Settings()  # type: ignore[call-arg]
    users = load_users(settings.api_users_file)
    if username in users:
        click.echo(f"User '{username}' already exists.")
        raise SystemExit(1)
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        click.echo("Passwords do not match.")
        raise SystemExit(1)
    pw_hash, salt = hash_password(password)
    users[username] = AuthUser(
        username=username,
        password_hash=pw_hash,
        salt=salt,
        role=UserRole(role),
    )
    save_users(settings.api_users_file, users)
    click.echo(f"User '{username}' added with role '{role}'.")


@cli.command("list")
def list_users() -> None:
    """List all API users."""
    settings = Settings()  # type: ignore[call-arg]
    users = load_users(settings.api_users_file)
    if not users:
        click.echo("No users configured.")
        return
    for user in users.values():
        click.echo(f"  {user.username}  role={user.role}")


@cli.command()
@click.argument("username")
def remove(username: str) -> None:
    """Remove an API user."""
    settings = Settings()  # type: ignore[call-arg]
    users = load_users(settings.api_users_file)
    if username not in users:
        click.echo(f"User '{username}' not found.")
        raise SystemExit(1)
    del users[username]
    save_users(settings.api_users_file, users)
    click.echo(f"User '{username}' removed.")


if __name__ == "__main__":
    cli()
