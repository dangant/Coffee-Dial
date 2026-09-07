"""Bean and roaster names are the join key between brews, templates and the shelf.

Nothing links those tables by id, so the strings have to line up exactly — a
trailing space pasted in with a bean name is enough to hide a template from the
new-brew form and to stop its brews drawing down the bag. Names are trimmed on
the way in, and compared through :func:`bean_key` so older rows still match.
"""


def clean(value: str | None) -> str | None:
    """Trim a name for storage. Blank (or whitespace-only) becomes None."""
    if value is None:
        return None
    return value.strip() or None


def bean_key(bean_name: str | None, roaster: str | None) -> tuple[str, str | None]:
    """Whitespace- and case-insensitive key for matching a bean across tables."""
    return (
        (bean_name or "").strip().casefold(),
        (roaster or "").strip().casefold() or None,
    )
