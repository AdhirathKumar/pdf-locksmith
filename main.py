from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pypdf import PdfReader, PdfWriter
from uuid import uuid4
from io import BytesIO
from typing import Dict

app = FastAPI(title="PDFLocksmith")

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

RESULT_STORE: Dict[str, Dict[str, bytes]] = {}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "mode": "lock",
            "message": None,
            "error": None,
            "result_id": None,
        },
    )


def _ensure_pdf(file: UploadFile, content: bytes) -> None:
    if file.content_type not in ("application/pdf", "application/x-pdf"):
        if not file.filename.lower().endswith(".pdf"):
            raise ValueError("Please upload a PDF file.")
    if not content:
        raise ValueError("Uploaded file is empty.")


def _lock_pdf(data: bytes, password: str) -> bytes:
    reader = PdfReader(BytesIO(data))
    if getattr(reader, "is_encrypted", False):
        raise ValueError("This PDF is already password protected.")
    if not password:
        raise ValueError("Password is required to lock the document.")
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _unlock_pdf(data: bytes, password: str) -> bytes:
    reader = PdfReader(BytesIO(data))
    if not getattr(reader, "is_encrypted", False):
        raise ValueError("This PDF is not password protected.")
    if not password:
        raise ValueError("Password is required to unlock the document.")
    result = reader.decrypt(password)
    if isinstance(result, int) and result == 0:
        raise ValueError("Incorrect password. Could not unlock the PDF.")
    if result is False:
        raise ValueError("Incorrect password. Could not unlock the PDF.")
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@app.post("/process", response_class=HTMLResponse, name="process_pdf")
async def process_pdf(
    request: Request,
    mode: str = Form(...),
    password: str = Form(""),
    file: UploadFile = File(...),
):
    message = None
    error = None
    result_id = None

    try:
        data = await file.read()
        _ensure_pdf(file, data)

        safe_mode = mode.lower()
        original_name = file.filename or "document.pdf"
        base_name = original_name.rsplit(".", 1)[0]

        if safe_mode == "lock":
            output_bytes = _lock_pdf(data, password)
            output_name = f"{base_name}_locked.pdf"
            message = "PDF locked successfully."
        elif safe_mode == "unlock":
            output_bytes = _unlock_pdf(data, password)
            output_name = f"{base_name}_unlocked.pdf"
            message = "PDF unlocked successfully."
        else:
            raise ValueError("Unknown mode selected.")

        file_id = str(uuid4())
        RESULT_STORE[file_id] = {
            "filename": output_name,
            "content": output_bytes,
        }
        result_id = file_id
    except Exception as exc:
        error = str(exc)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "mode": mode,
            "message": message,
            "error": error,
            "result_id": result_id,
        },
    )


@app.get("/download/{file_id}", name="download_file")
async def download_file(file_id: str):
    entry = RESULT_STORE.pop(file_id, None)
    if entry is None:
        raise HTTPException(status_code=404, detail="File not found.")
    return Response(
        content=entry["content"],
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{entry["filename"]}"'
        },
    )


def main():
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
