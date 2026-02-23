from src.applications.tui.tui_app import TUIApp
from src.dependencies import Container


def create_app(container: Container) -> TUIApp:
    return TUIApp(
        entry_service=container.entry_service(),
        watchlist_service=container.watchlist_service(),
        chatbot_service=container.chatbot_service(),
        guest_service=container.guest_service(),
        export_service=container.export_service(),
        image_service=container.image_service(),
    )
