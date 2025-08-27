import os
import warnings

import dotenv

dotenv.load_dotenv()


MONGODB_PASSWORD = os.environ.get("MONGODB_PASSWORD") or ""
assert MONGODB_PASSWORD

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or ""
assert TELEGRAM_TOKEN

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or ""
if not OPENAI_API_KEY:
    warnings.warn("OpenAI API key not found in environment variables.")

OPENAI_PROJECT_ID = os.environ.get("OPENAI_PROJECT_ID") or ""
if not OPENAI_PROJECT_ID:
    warnings.warn("OpenAI Project ID not found in environment variables.")

OMDB_API_KEY = os.environ.get("OMDB_API") or ""
if not OMDB_API_KEY:
    warnings.warn("OMDB API key is not found in environment variables.")

SUPABASE_API_KEY = os.environ.get("SUPABASE_API_KEY") or ""
if not SUPABASE_API_KEY:
    warnings.warn("Supabase API key is not found in environment variables.")

SUPABASE_PROJECT_ID = os.environ.get("SUPABASE_PROJECT_ID") or ""
if not SUPABASE_PROJECT_ID:
    warnings.warn("Supabase Project ID is not found in environment variables.")

IMAGES_SERIES_BUCKET_NAME = os.environ.get("IMAGES_SERIES_BUCKET_NAME") or ""
if not IMAGES_SERIES_BUCKET_NAME:
    warnings.warn("ImageStore bucket name is not found in environment variables.")

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID") or ""
if not AWS_ACCESS_KEY_ID:
    warnings.warn("AWS Access Key ID is not found in environment variables.")

AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY") or ""
if not AWS_SECRET_ACCESS_KEY:
    warnings.warn("AWS Secret Access Key is not found in environment variables.")
