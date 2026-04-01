#!/usr/bin/env python3
"""Encrypt (or re-encrypt) the moviesdb .env secrets file.

Usage:
    uv run python scripts/encrypt_env.py                      # encrypt default ~/.config/moviesdb/.env
    uv run python scripts/encrypt_env.py /path/to/.env        # encrypt a custom .env
    uv run python scripts/encrypt_env.py --remove-source      # delete the plaintext after encryption
"""

import sys
from pathlib import Path

import click

from src.crypto import encrypt_file
from src.settings import CONFIG_ENV, CONFIG_ENV_ENCRYPTED


@click.command()
@click.argument(
    "env_file",
    type=click.Path(exists=True, path_type=Path),
    default=CONFIG_ENV,
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output path for the encrypted file (defaults to <env_dir>/.env.encrypted).",
)
@click.option(
    "--remove-source",
    is_flag=True,
    help="Remove the plaintext .env after successful encryption.",
)
def main(env_file: Path, output: Path | None, remove_source: bool) -> None:
    """Encrypt a .env file using Fernet symmetric encryption."""
    dest = output or CONFIG_ENV_ENCRYPTED

    password = click.prompt("Set encryption password", hide_input=True)
    confirm = click.prompt("Confirm password", hide_input=True)
    if password != confirm:
        click.echo("Passwords do not match.", err=True)
        sys.exit(1)
    if not password:
        click.echo("Password cannot be empty.", err=True)
        sys.exit(1)

    encrypt_file(env_file, password, dest)
    click.echo(f"Encrypted {env_file} -> {dest}")

    if remove_source:
        env_file.unlink()
        click.echo(f"Removed {env_file}")


if __name__ == "__main__":
    main()
