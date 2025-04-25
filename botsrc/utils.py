from src.obj.entry import Entry, Type


def select_entry_by_oid_part(oid_part: str, entries: list[Entry]) -> Entry | None:
    selected = [entry for entry in entries if oid_part in str(entry._id)]
    if len(selected) != 1:
        return None
    return selected[0]


def format_entry(entry: Entry, verbose: bool = False, with_oid: bool = False) -> str:
    note_str = f": {entry.notes}" if entry.notes and verbose else ""
    type_str = f" ({entry.type.name.lower()})" if entry.type != Type.MOVIE else ""
    watched_date_str = f" ({entry.date.strftime('%d.%m.%Y')})" if entry.date else ""
    tags_str = f" [{' '.join(entry.tags)}]" if entry.tags else ""
    oid_part = "{" + str(entry._id)[-4:] + "} " if with_oid else ""
    return f"{oid_part}[{entry.rating:.2f}] {entry.title}{type_str}{watched_date_str}{note_str}{tags_str}"
