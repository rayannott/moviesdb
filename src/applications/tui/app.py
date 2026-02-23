from typing import TYPE_CHECKING

from src.dependencies import Container

if TYPE_CHECKING:
    from src.applications.tui.tui_app import TUIApp


def create_app(container: Container) -> "TUIApp":
    from src.applications.tui.tui_app import TUIApp

    return TUIApp(
        entry_service=container.entry_service(),
        watchlist_service=container.watchlist_service(),
        chatbot_service=container.chatbot_service(),
        guest_service=container.guest_service(),
        export_service=container.export_service(),
        image_service=container.image_service(),
    )
