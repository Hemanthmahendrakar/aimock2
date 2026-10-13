"""
Deterministic text extraction from resume files. No AI/LLM calls here
— this is mechanical parsing, dispatched by content type. The actual
"resume analysis" into a structured profile is a separate step (see
candidate_profile_builder.py), so this module has exactly one job.
"""
import io


class UnsupportedContentType(Exception):
    def __init__(self, content_type: str):
        super().__init__(f"Cannot extract text from content type: {content_type}")


class ExtractionFailed(Exception):
    def __init__(self, reason: str):
        super().__init__(f"Text extraction failed: {reason}")


def extract_text_from_pdf(data: bytes) -> str:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        pages_text = [page.extract_text() or "" for page in reader.pages]
    except PdfReadError as exc:
        raise ExtractionFailed(f"not a readable PDF ({exc})") from exc
    return "\n".join(pages_text).strip()


def extract_text_from_docx(data: bytes) -> str:
    import docx  # python-docx
    from docx.opc.exceptions import PackageNotFoundError

    try:
        document = docx.Document(io.BytesIO(data))
    except (PackageNotFoundError, KeyError, ValueError) as exc:
        raise ExtractionFailed(f"not a readable DOCX ({exc})") from exc
    paragraphs = [p.text for p in document.paragraphs]
    return "\n".join(paragraphs).strip()


_EXTRACTORS = {
    "application/pdf": extract_text_from_pdf,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        extract_text_from_docx,
}


def extract_text(*, content_type: str, data: bytes) -> str:
    extractor = _EXTRACTORS.get(content_type)
    if extractor is None:
        raise UnsupportedContentType(content_type)
    return extractor(data)
