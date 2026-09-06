"""Store images attached to enhancement ideas.

Screenshots arrive straight off the clipboard, so they can be large and are whatever the
OS chose to encode. Everything is normalized on the way in — decoded, downscaled to a sane
long edge, and re-encoded — so the database holds predictable, modest blobs regardless of
what was pasted.
"""
from __future__ import annotations

import io

from sqlalchemy.orm import Session

from app.models.idea_screenshot import IdeaScreenshot

ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # refuse before decoding
MAX_EDGE = 1600  # plenty to read UI text at full size


class ScreenshotError(Exception):
    """Raised when an upload can't be stored. ``status`` is the HTTP code to return."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _normalize(raw: bytes) -> tuple[bytes, str, int, int]:
    """Decode, downscale, re-encode. Returns (data, content_type, width, height)."""
    from PIL import Image, UnidentifiedImageError

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError) as e:
        raise ScreenshotError("That file isn't an image we can read.", 415) from e

    # Transparency has to survive as PNG; anything else is smaller as JPEG.
    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    img = img.convert("RGBA" if has_alpha else "RGB")

    if max(img.size) > MAX_EDGE:
        img.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)

    buf = io.BytesIO()
    if has_alpha:
        img.save(buf, format="PNG", optimize=True)
        content_type = "image/png"
    else:
        img.save(buf, format="JPEG", quality=85, optimize=True)
        content_type = "image/jpeg"
    return buf.getvalue(), content_type, img.width, img.height


def add_screenshot(
    db: Session, idea_id: int, filename: str, content_type: str, raw: bytes
) -> IdeaScreenshot:
    if content_type not in ALLOWED_TYPES:
        raise ScreenshotError(f"Unsupported image type: {content_type or 'unknown'}.", 415)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ScreenshotError("That image is larger than 5 MB.", 413)
    if not raw:
        raise ScreenshotError("That image is empty.", 400)

    data, stored_type, width, height = _normalize(raw)
    shot = IdeaScreenshot(
        idea_id=idea_id,
        filename=(filename or "screenshot")[:255],
        content_type=stored_type,
        width=width,
        height=height,
        byte_size=len(data),
        data=data,
    )
    db.add(shot)
    db.commit()
    db.refresh(shot)
    return shot


def list_screenshots(db: Session, idea_id: int) -> list[IdeaScreenshot]:
    return (
        db.query(IdeaScreenshot)
        .filter(IdeaScreenshot.idea_id == idea_id)
        .order_by(IdeaScreenshot.created_at)
        .all()
    )


def get_screenshot(db: Session, screenshot_id: int) -> IdeaScreenshot | None:
    return db.query(IdeaScreenshot).filter(IdeaScreenshot.id == screenshot_id).first()


def delete_screenshot(db: Session, screenshot_id: int) -> bool:
    shot = get_screenshot(db, screenshot_id)
    if not shot:
        return False
    db.delete(shot)
    db.commit()
    return True
