from src.applications.tui.app import create_app
from src.dependencies import Container

if __name__ == "__main__":
    print("python interactive mode is running")
    container = Container()

    app = create_app(container)
    print(f"{len(app.entries)} entries loaded")
