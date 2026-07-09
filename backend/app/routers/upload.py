from fastapi import APIRouter, UploadFile, File, HTTPException

router = APIRouter()


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    allowed_ext = (".txt", ".md", ".pdf", ".docx")
    if not file.filename.endswith(allowed_ext):
        raise HTTPException(status_code=400, detail="Only text-based files are allowed")
    return {"file_id": "placeholder", "name": file.filename, "text_content": "placeholder"}
