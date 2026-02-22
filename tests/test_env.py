"""Tests that all required environment variables are present."""

from src.settings import Settings


def test_found_env() -> None:
    """All required settings should be loadable from the environment."""
    settings = Settings()
    assert settings.mongodb_password
    assert settings.telegram_bot_token
    assert settings.openai_api_key
    assert settings.openai_project_id
    assert settings.omdb_api
    assert settings.supabase_api_key
    assert settings.supabase_project_id
    assert settings.aws_access_key_id
    assert settings.aws_secret_access_key
    assert settings.aws_images_series_bucket_name
