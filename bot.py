"""Telegram bot entrypoint."""

from src.dependencies import Container
from src.utils.env import TELEGRAM_TOKEN


def main() -> None:
    from src.applications.bot.app import BotApp

    container = Container()

    bot_app = BotApp(
        token=TELEGRAM_TOKEN,
        entry_service=container.entry_service(),
        watchlist_service=container.watchlist_service(),
        guest_service=container.guest_service(),
    )
    bot_app.run()


if __name__ == "__main__":
    main()
