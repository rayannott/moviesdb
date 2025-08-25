from src.utils.env import (
    MONGODB_PASSWORD,
    TELEGRAM_TOKEN,
    OPENAI_API_KEY,
    OPENAI_PROJECT_ID,
    OMDB_API_KEY,
    SUPABASE_API_KEY,
    SUPABASE_PROJECT_ID,
)


def test_found_env():
    assert MONGODB_PASSWORD
    assert TELEGRAM_TOKEN
    assert OPENAI_API_KEY
    assert OPENAI_PROJECT_ID
    assert OMDB_API_KEY
    assert SUPABASE_API_KEY
    assert SUPABASE_PROJECT_ID
