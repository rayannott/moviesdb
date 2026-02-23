"""API entrypoint. Run with: uv run fastapi dev api.py"""

from src.applications.api.app import create_app
from src.dependencies import Container

app = create_app(Container())
