import uuid

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.schemas import UploadFileResponse
from app.services.file_parser import is_supported_file, parse_uploaded_file

router = APIRouter()
MAX_FILE_SIZE = 10 * 1024 * 1024


@router.post("/upload", response_model=UploadFileResponse)
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is required")

    content_bytes = await file.read()

    if len(content_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum allowed size of {MAX_FILE_SIZE / (1024 * 1024):.0f} MB",
        )

    if not is_supported_file(file.filename, content_bytes):
        raise HTTPException(
            status_code=400,
            detail="Only text-based files are allowed (txt, md, code files, pdf, docx, etc.)",
        )

    try:
        text = parse_uploaded_file(file.filename, content_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    file_id = str(uuid.uuid4())
    return UploadFileResponse(file_id=file_id, name=file.filename, text_content=text)
