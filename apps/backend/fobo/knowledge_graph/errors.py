class UnresolvedBook(Exception):
    """Zero matches. Escalates UNRESOLVED_BOOK."""


class AmbiguousBook(Exception):
    """More than one match. Escalates AMBIGUOUS_BOOK. Never auto-pick."""
