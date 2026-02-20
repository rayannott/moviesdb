from dependency_injector.wiring import inject, Provide

from src.dependencies import Container
from src.repos.entries import EntriesRepo


@inject
def main(entries_repo: EntriesRepo = Provide[Container.entries_repo]):
    entries = entries_repo.get_entries()
    # print(entries)


if __name__ == "__main__":
    container = Container()
    container.wire(modules=[__name__])
    main()
