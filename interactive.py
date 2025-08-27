from src.apps import App

if __name__ == "__main__":
    print("python interactive mode is running")
    app = App()
    print(f"{len(app.entries)} entries loaded")
