from src.applications.tui.app import TUIApp
from src.dependencies import Container

if __name__ == "__main__":
    print("python interactive mode is running")
    container = Container()

    app = TUIApp(
        entry_service=container.entry_service(),
        watchlist_service=container.watchlist_service(),
        chatbot_service=container.chatbot_service(),
        guest_service=container.guest_service(),
        export_service=container.export_service(),
        image_service=container.image_service(),
    )
    print(f"{len(app.entries)} entries loaded")
