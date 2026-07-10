import io
from typing import Callable

import pdfplumber
from docx import Document

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _limit_size(file_bytes: bytes) -> None:
    if len(file_bytes) > MAX_FILE_SIZE:
        raise ValueError(f"File exceeds maximum allowed size of {MAX_FILE_SIZE / (1024 * 1024):.0f} MB")


def extract_text_from_pdf(file_bytes: bytes) -> str:
    _limit_size(file_bytes)
    text_parts = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
    except Exception as exc:
        raise ValueError(f"Failed to parse PDF: {exc}") from exc

    return "\n\n".join(text_parts).strip()


def extract_text_from_docx(file_bytes: bytes) -> str:
    _limit_size(file_bytes)
    try:
        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n".join(paragraphs).strip()
    except Exception as exc:
        raise ValueError(f"Failed to parse DOCX: {exc}") from exc


def extract_text_from_txt(file_bytes: bytes) -> str:
    _limit_size(file_bytes)
    return file_bytes.decode("utf-8", errors="ignore").strip()


PARSERS: dict[str, Callable[[bytes], str]] = {
    ".txt": extract_text_from_txt,
    ".md": extract_text_from_txt,
    ".pdf": extract_text_from_pdf,
    ".docx": extract_text_from_docx,
}


def parse_uploaded_file(filename: str, file_bytes: bytes) -> str:
    """Extract text from supported text-based files.

    Supported extensions: .txt, .md, .pdf, .docx
    """
    filename_lower = filename.lower()
    for ext, parser in PARSERS.items():
        if filename_lower.endswith(ext):
            return parser(file_bytes)

    raise ValueError(
        f"Unsupported file type for '{filename}'. "
        f"Supported extensions: {', '.join(PARSERS.keys())}"
    )


def is_supported_file(filename: str) -> bool:
    filename_lower = filename.lower()
    return any(filename_lower.endswith(ext) for ext in PARSERS.keys())
