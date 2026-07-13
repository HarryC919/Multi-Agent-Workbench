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


# Plain-text extensions we can decode as UTF-8.
TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".less",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".py",
    ".pyw",
    ".java",
    ".c",
    ".cpp",
    ".cc",
    ".h",
    ".hpp",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".sql",
    ".sh",
    ".bash",
    ".zsh",
    ".ps1",
    ".bat",
    ".cmd",
    ".csv",
    ".log",
    ".ini",
    ".cfg",
    ".toml",
}

PARSERS: dict[str, Callable[[bytes], str]] = {
    ".pdf": extract_text_from_pdf,
    ".docx": extract_text_from_docx,
}

# Register all text extensions to the UTF-8 decoder.
for ext in TEXT_EXTENSIONS:
    PARSERS[ext] = extract_text_from_txt


def _looks_like_text(file_bytes: bytes) -> bool:
    """Heuristic: consider binary if there are many null bytes or very high non-printable ratio."""
    if not file_bytes:
        return True
    sample = file_bytes[:4096]
    null_count = sample.count(b"\x00")
    if null_count > 0:
        return False
    # Allow common whitespace and printable ASCII/UTF-8 range.
    non_text = sum(1 for b in sample if b < 0x09 or (0x0E <= b <= 0x1F and b not in (0x0A, 0x0D)))
    return non_text / len(sample) < 0.05


def parse_uploaded_file(filename: str, file_bytes: bytes) -> str:
    """Extract text from supported text-based files.

    Supported extensions include common plain-text/code formats, Markdown,
    PDF, and DOCX. For unknown extensions, a UTF-8 text heuristic is used.
    """
    _limit_size(file_bytes)
    filename_lower = filename.lower()

    # Extension-based dispatch
    for ext, parser in PARSERS.items():
        if filename_lower.endswith(ext):
            return parser(file_bytes)

    # Fallback: try UTF-8 if it looks like text
    if _looks_like_text(file_bytes):
        return extract_text_from_txt(file_bytes)

    raise ValueError(
        f"Unsupported file type for '{filename}'. "
        "Please upload a text-based file (txt, md, code files, pdf, docx, etc.)."
    )


def is_supported_file(filename: str, file_bytes: bytes | None = None) -> bool:
    filename_lower = filename.lower()
    if any(filename_lower.endswith(ext) for ext in PARSERS.keys()):
        return True
    if file_bytes is not None and _looks_like_text(file_bytes):
        return True
    return False
