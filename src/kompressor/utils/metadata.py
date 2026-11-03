"""Metadata handling: EXIF orientation, EXIF payload and ICC profiles.

Policy:
  * EXIF orientation is always *applied* (pixels are corrected) so images look
    right everywhere; the orientation tag is cleared afterwards.
  * EXIF payload and ICC profile are forwarded to the encoder whenever that
    encoder accepts them.  When it does not, the limitation is reported
    instead of silently pretending metadata was kept.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PIL import Image, ImageOps

from kompressor.utils.format_support import normalize_format


@dataclass
class MetadataState:
    """Metadata extracted from a source image plus what was preserved."""

    had_exif: bool = False
    had_icc: bool = False
    orientation_applied: bool = False
    exif_preserved: bool = False
    icc_preserved: bool = False
    notes: list[str] = field(default_factory=list)


def read_metadata(image: Image.Image) -> tuple[bytes | None, bytes | None, MetadataState]:
    """Extract (exif_bytes, icc_bytes, state) from an open image."""
    state = MetadataState()
    exif_bytes: bytes | None = None
    icc_bytes: bytes | None = None

    try:
        exif_bytes = image.info.get("exif")
        if not exif_bytes:
            raw = image.getexif()
            if raw:
                exif_bytes = raw.tobytes()
    except Exception:  # noqa: BLE001 - malformed EXIF must never crash us
        exif_bytes = None
        state.notes.append("Source EXIF could not be parsed; ignored.")

    if exif_bytes:
        state.had_exif = True

    icc_bytes = image.info.get("icc_profile")
    if icc_bytes:
        state.had_icc = True

    return exif_bytes, icc_bytes, state


def apply_orientation(image: Image.Image) -> tuple[Image.Image, bool]:
    """Apply the EXIF orientation tag to the pixel data.

    Returns (image, orientation_was_applied).
    """
    try:
        orientation = image.getexif().get(274)  # 274 = Orientation tag
    except Exception:  # noqa: BLE001
        orientation = None
    if not orientation or orientation == 1:
        return image, False
    try:
        corrected = ImageOps.exif_transpose(image)
    except Exception:  # noqa: BLE001
        return image, False
    if corrected is None:
        return image, False
    return corrected, True


def metadata_save_kwargs(
    pil_fmt: str,
    exif_bytes: bytes | None,
    icc_bytes: bytes | None,
    state: MetadataState,
) -> dict:
    """Build save() kwargs for EXIF/ICC and record what was preserved.

    Some encoders reject the ``exif``/``icc_profile`` keywords; that is
    detected at save time by the caller, which re-invokes this helper with
    ``allow_exif=False`` / ``allow_icc=False``.
    """
    kwargs: dict = {}
    kwargs["icc_profile"] = icc_bytes
    kwargs["exif"] = exif_bytes
    return kwargs


def strip_rejected_metadata(
    pil_fmt: str,
    exif_bytes: bytes | None,
    icc_bytes: bytes | None,
    state: MetadataState,
    error: Exception,
) -> dict | None:
    """If *error* looks like a rejected metadata kwarg, return retry kwargs."""
    msg = str(error).lower()
    if "exif" in msg or "icc" in msg or "unexpected keyword" in msg or "unknown option" in msg:
        retry: dict = {}
        # Keep whichever metadata the encoder is likely to accept.
        if icc_bytes is not None:
            retry["icc_profile"] = icc_bytes
        if exif_bytes is not None and pil_fmt in {"JPEG", "WEBP", "AVIF"}:
            retry["exif"] = exif_bytes
        return retry
    return None


def describe_metadata(state: MetadataState) -> str:
    """Honest, human-readable summary of metadata handling."""
    if not state.had_exif and not state.had_icc:
        return "No EXIF or ICC profile present in the source."
    parts: list[str] = []
    if state.orientation_applied:
        parts.append("EXIF orientation applied to pixels")
    if state.had_exif:
        parts.append("EXIF " + ("preserved" if state.exif_preserved else "not preserved by this encoder"))
    if state.had_icc:
        parts.append("ICC profile " + ("preserved" if state.icc_preserved else "not preserved by this encoder"))
    return "; ".join(parts) + "."


def has_transparency(image: Image.Image) -> bool:
    if image.mode in ("RGBA", "LA", "PA"):
        return True
    if image.mode == "P" and "transparency" in image.info:
        return True
    if image.mode == "A":
        return True
    return False
