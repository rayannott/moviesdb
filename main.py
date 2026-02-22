from dependency_injector.wiring import Provide, inject

from src.applications.tui.app import TUIApp
from src.dependencies import Container
from src.services.chatbot_service import ChatbotService
from src.services.entry_service import EntryService
from src.services.export_service import ExportService
from src.services.guest_service import GuestService
from src.services.image_service import ImageService
from src.services.watchlist_service import WatchlistService


@inject
def main(
    entry_service: EntryService = Provide[Container.entry_service],
    watchlist_service: WatchlistService = Provide[Container.watchlist_service],
    chatbot_service: ChatbotService = Provide[Container.chatbot_service],
    guest_service: GuestService = Provide[Container.guest_service],
    export_service: ExportService = Provide[Container.export_service],
    image_service: ImageService = Provide[Container.image_service],
) -> None:
    app = TUIApp(
        entry_service=entry_service,
        watchlist_service=watchlist_service,
        chatbot_service=chatbot_service,
        guest_service=guest_service,
        export_service=export_service,
        image_service=image_service,
    )
    app.run()


if __name__ == "__main__":
    container = Container()
    container.wire(modules=[__name__])
    main()
