from src.utils.env import (
    MONGODB_PASSWORD,
    OMDB_API_KEY,
    OPENAI_API_KEY,
    OPENAI_PROJECT_ID,
    SUPABASE_API_KEY,
    SUPABASE_PROJECT_ID,
    TELEGRAM_TOKEN,
)


def test_found_env():
    assert MONGODB_PASSWORD
    assert TELEGRAM_TOKEN
    assert OPENAI_API_KEY
    assert OPENAI_PROJECT_ID
    assert OMDB_API_KEY
    assert SUPABASE_API_KEY
    assert SUPABASE_PROJECT_ID
