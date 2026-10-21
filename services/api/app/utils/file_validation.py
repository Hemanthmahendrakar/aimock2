"""
Lightweight file-signature ("magic bytes") checks. We don't trust a
client-supplied Content-Type header — it's trivial to spoof — so we
peek at the first few bytes of the actual file to confirm the type
before it ever reaches storage.
"""

_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/webp": (b"RIFF",),  # followed by "WEBP" at offset 8, checked separately
    "image/svg+xml": (b"<?xml", b"<svg"),
}


class FileValidationError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


def detect_content_type(data: bytes) -> str | None:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    stripped = data[:256].lstrip()
    if stripped.startswith(b"<?xml") or stripped.startswith(b"<svg"):
        return "image/svg+xml"
    if data[:5] == b"%PDF-":
        return "application/pdf"
    if data[:4] == b"PK\x03\x04":
        # DOCX (and every other OOXML/zip format) shares this signature.
        # Full disambiguation would mean opening it as a zip and checking
        # for word/document.xml — deferred to actual extraction time,
        # where python-docx failing to open it surfaces as an
        # extraction error rather than a rejected upload.
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    # --- Phase 13: student answer-recording audio ---
    if data[:4] == b"\x1aE\xdf\xa3":
        return "audio/webm"  # also matches Matroska/.mkv, but browsers only emit webm here
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "audio/wav"
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mpeg"
    if data[:4] == b"OggS":
        return "audio/ogg"
    return None


_CONTENT_TYPE_LABELS: dict[str, str] = {
    "image/png": "PNG",
    "image/jpeg": "JPEG",
    "image/webp": "WEBP",
    "image/svg+xml": "SVG",
    "application/pdf": "PDF",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
    "audio/webm": "WEBM",
    "audio/wav": "WAV",
    "audio/mpeg": "MP3",
    "audio/ogg": "OGG",
}


def validate_upload(
    *, data: bytes, max_size_bytes: int, allowed_content_types: tuple[str, ...]
) -> str:
    """Returns the detected (trusted) content type, or raises FileValidationError."""
    if len(data) == 0:
        raise FileValidationError("The uploaded file is empty.")
    if len(data) > max_size_bytes:
        raise FileValidationError(
            f"File is too large. Maximum size is {max_size_bytes // (1024 * 1024)}MB."
        )
    detected = detect_content_type(data)
    if detected is None or detected not in allowed_content_types:
        allowed_labels = ", ".join(
            _CONTENT_TYPE_LABELS.get(ct, ct) for ct in allowed_content_types
        )
        raise FileValidationError(f"Unsupported file type. Allowed: {allowed_labels}.")
    return detected
