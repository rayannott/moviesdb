from dependency_injector.wiring import Provide, inject

from src.applications.tui.app import App
from src.dependencies import Container
from src.services.chatbot_service import ChatbotService
from src.services.entry_service import EntryService
from src.services.export_service import ExportService
from src.services.guest_service import GuestService
from src.services.watchlist_service import WatchlistService


@inject
def main(
    entry_service: EntryService = Provide[Container.entry_service],
    watchlist_service: WatchlistService = Provide[Container.watchlist_service],
    chatbot_service: ChatbotService = Provide[Container.chatbot_service],
    guest_service: GuestService = Provide[Container.guest_service],
    export_service: ExportService = Provide[Container.export_service],
) -> None:
    app = App(
        entry_service=entry_service,
        watchlist_service=watchlist_service,
        chatbot_service=chatbot_service,
        guest_service=guest_service,
        export_service=export_service,
    )
    app.run()


if __name__ == "__main__":
    main()
