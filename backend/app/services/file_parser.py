def parse_uploaded_file(filename: str, file_bytes: bytes) -> str:
    if filename.endswith(".pdf"):
        return ""
    elif filename.endswith(".docx"):
        return ""
    else:
        return file_bytes.decode("utf-8", errors="ignore")
