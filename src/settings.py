from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

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
