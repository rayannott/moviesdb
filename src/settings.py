import os
from io import StringIO
from pathlib import Path

from dotenv import dotenv_values
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.crypto import decrypt_file

CONFIG_DIR = Path.home() / ".config" / "moviesdb"
CONFIG_ENV = CONFIG_DIR / ".env"
CONFIG_ENV_ENCRYPTED = CONFIG_DIR / ".env.encrypted"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(CONFIG_ENV, ".env"),
        env_file_encoding="utf-8",
    )

    openai_api_key: str
    openai_project_id: str
    omdb_api: str
    telegram_bot_token: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_images_series_bucket_name: str
    mongodb_password: str
    mongodb_suffix: str
    mongodb_prefix: str
    api_users_file: Path = Path("api_users-local.json")


def needs_unlock() -> bool:
    """Whether the plaintext env is absent but an encrypted copy exists."""
    if not CONFIG_ENV.exists() and not CONFIG_ENV_ENCRYPTED.exists():
        raise FileNotFoundError(
            f"Neither {CONFIG_ENV} nor {CONFIG_ENV_ENCRYPTED} found. "
            "Run `uv run python scripts/encrypt_env.py` to create the encrypted file."
        )
    return not CONFIG_ENV.exists()


def unlock_secrets(password: str) -> None:
    """Decrypt the encrypted env file and inject the vars into ``os.environ``."""

    content = decrypt_file(CONFIG_ENV_ENCRYPTED, password).decode()
    for key, value in dotenv_values(stream=StringIO(content)).items():
        if value is not None:
            os.environ[key] = value
