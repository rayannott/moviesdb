"""Telegram bot entrypoint."""

from src.dependencies import Container
from src.settings import Settings


def main() -> None:
    from src.applications.bot.app import BotApp

    container = Container()
    settings = Settings()

    bot_app = BotApp(
        token=settings.telegram_bot_token,
        entry_service=container.entry_service(),
        watchlist_service=container.watchlist_service(),
        guest_service=container.guest_service(),
        image_service=container.image_service(),
    )
    bot_app.run()


if __name__ == "__main__":
    main()
