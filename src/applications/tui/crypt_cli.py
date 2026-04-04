"""`movies crypt` subcommands for .env encryption."""

import sys
from pathlib import Path

import click
from cryptography.fernet import InvalidToken

from src.crypto import decrypt_file, encrypt_file
from src.settings import CONFIG_ENV, CONFIG_ENV_ENCRYPTED


@click.group("crypt")
def crypt_group() -> None:
    """Encrypt or decrypt .env secrets (Fernet + PBKDF2)."""


@crypt_group.command("encrypt")
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
    help="Output path for the encrypted file (defaults to ~/.config/moviesdb/.env.encrypted).",
)
@click.option(
    "--remove-source",
    is_flag=True,
    help="Remove the plaintext .env after successful encryption.",
)
def crypt_encrypt(env_file: Path, output: Path | None, remove_source: bool) -> None:
    """Encrypt a .env file."""
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


@crypt_group.command("decrypt")
@click.argument(
    "encrypted_file",
    type=click.Path(exists=True, path_type=Path),
    default=CONFIG_ENV_ENCRYPTED,
)
def crypt_decrypt(encrypted_file: Path) -> None:
    """Decrypt an encrypted .env and print plaintext to stdout (sensitive)."""
    password = click.prompt("", hide_input=True, prompt_suffix="")
    try:
        data = decrypt_file(encrypted_file, password)
    except InvalidToken:
        click.echo("Decryption failed. Wrong password or corrupted file.", err=True)
        raise SystemExit(1)
    click.echo(data.decode(), nl=False)
    if data and not data.endswith(b"\n"):
        click.echo()
