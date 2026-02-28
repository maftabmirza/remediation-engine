"""
Search utilities for safe database query patterns.
"""


def like_escape(value: str) -> str:
    """Escape LIKE metacharacters in a search value so that user-supplied
    strings are treated as literals rather than wildcard patterns.

    Characters escaped: backslash (\\), percent (%), underscore (_).
    Use the returned string together with ``escape="\\\\"`` in SQLAlchemy's
    ``.ilike()`` / ``.like()`` calls::

        Column.ilike(f"%{like_escape(term)}%", escape="\\\\")
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
