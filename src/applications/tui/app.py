from typing import TYPE_CHECKING

from src.dependencies import Container

# this is to avoid long imports when not actually using the app in the cli
if TYPE_CHECKING:
    from src.applications.tui.tui_app import TUIApp


def create_app(container: Container) -> "TUIApp":
    from rich.console import Console

    cns = Console()
    with cns.status("Loading dependencies..."):
        from src.applications.tui.tui_app import TUIApp

    with cns.status("Assembling app..."):
        app = TUIApp(
            entry_service=container.entry_service(),
            watchlist_service=container.watchlist_service(),
            chatbot_service=container.chatbot_service(),
            guest_service=container.guest_service(),
            export_service=container.export_service(),
            image_service_factory=container.image_service,
        )

    return app
