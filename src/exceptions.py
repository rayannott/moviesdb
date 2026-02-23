class EntryNotFoundException(Exception):
    """Raised when a requested entity does not exist."""


class MalformedEntryException(Exception):
    """Raised when input data fails domain validation."""


class DuplicateEntryException(Exception):
    """Raised when an entity that must be unique already exists."""
