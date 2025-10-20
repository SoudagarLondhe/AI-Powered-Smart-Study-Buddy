# backend/apis/gpt_api.py
import os
import json
import pathlib
from tempfile import NamedTemporaryFile
from typing import Callable, List, Optional

from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile, File, Form, Body
from sqlalchemy import select, func
from sqlalchemy.orm import Session

# File parsers
import pdfplumber
from docx import Document as DocxDocument
from pptx import Presentation

# DB model (single models file)
from models import Course

load_dotenv()

# ---------------- session factory wiring ----------------
_SESSION_FACTORY: Optional[Callable[[], Session]] = None

def set_session_factory(factory: Callable[[], Session]) -> None:
    """
    Call this once in app.py after you build SessionLocal:
        from apis.gpt_api import set_session_factory
        set_session_factory(SessionLocal)
    """
    global _SESSION_FACTORY
    _SESSION_FACTORY = factory

# ---------------- response helpers ----------------
def _fail(msg: str) -> dict:
    return {"status": "FAIL", "statusCode": 200, "message": msg, "data": ""}

def _success(data_str: str, message: str = "") -> dict:
    return {"status": "SUCCESS", "statusCode": 200, "message": message, "data": data_str}

# ---------------- extraction helpers ----------------
MAX_BYTES = 50 * 1024 * 1024  # 50 MB per file

def _read_pdf(path: str) -> str:
    parts: List[str] = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            parts.append(p.extract_text() or "")
    return "\n".join(parts).strip()

def _read_docx(path: str) -> str:
    doc = DocxDocument(path)
    return "\n".join(p.text for p in doc.paragraphs).strip()

def _read_pptx(path: str) -> str:
    prs = Presentation(path)
    parts: List[str] = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                parts.append(shape.text)
    return "\n".join(parts).strip()

def _extract_text_from_upload(upload: UploadFile) -> str:
    name = upload.filename or "uploaded"
    _, ext = os.path.splitext(name.lower())

    # quick size check
    upload.file.seek(0, os.SEEK_END)
    size = upload.file.tell()
    upload.file.seek(0)
    if size > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"{name} exceeds {MAX_BYTES // (1024*1024)}MB limit")

    with NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(upload.file.read())
        tmp_path = tmp.name

    try:
        if ext == ".pdf":
            text = _read_pdf(tmp_path)
        elif ext == ".docx":
            text = _read_docx(tmp_path)
        elif ext == ".pptx":
            text = _read_pptx(tmp_path)
        else:
            raise HTTPException(status_code=415, detail=f"Unsupported file type '{ext}'. Use PDF, DOCX, or PPTX.")
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    if not text:
        raise HTTPException(status_code=400, detail=f"No readable text found in {name}. If it is a scanned PDF, add OCR.")
    return text

def _extract_many(uploads: List[UploadFile]) -> List[tuple[str, str]]:
    """Returns list of (stem, text) where stem is filename without extension."""
    out: List[tuple[str, str]] = []
    for up in uploads:
        text = _extract_text_from_upload(up)
        stem = pathlib.Path(up.filename or "uploaded").stem
        out.append((stem, text))
    return out

def _derive_course_name(stems: List[str], override: Optional[str]) -> str:
    """Pick a readable course name for a bundle if client didn't pass one."""
    if override:
        return override[:255]
    if not stems:
        return "Untitled"
    # Join up to first 3 names; if more, indicate the count.
    base = " & ".join(stems[:3])
    if len(stems) > 3:
        base += f" (+{len(stems)-3} more)"
    return base[:255]

# ---------------- POST: /addcourse (upload & store ONLY) ----------------
def ingest_and_store_endpoint(
    # Single consistent key for one-or-many files
    files: Optional[List[UploadFile]] = File(default=None),
    course_name: Optional[str] = Form(default=None),
    # JSON fallback (optional raw text ingestion)
    body: Optional[dict] = Body(default=None),
):
    """
    POST /addcourse   (route defined in app.py)
    Behavior:
      - If 'files' contains 1 file: extract text and save ONE course row.
      - If 'files' contains N>1 files: extract each, CONCATENATE them, and save ONE course row.
        The course_name is either provided via form field or derived from filenames.
      - JSON fallback (no files): { "course_name": "...", "content": "..." } saves ONE row.
    """
    if _SESSION_FACTORY is None:
        return _fail("Server misconfigured: no DB session factory is set.")

    try:
        if files is not None and len(files) > 0:
            extracted = _extract_many(files)  # list of (stem, text)
            stems = [s for s, _ in extracted]

            # Build a single combined content block with clear separators
            parts = []
            for stem, text in extracted:
                parts.append(f"=== FILE: {stem} ===\n{text}")
            combined_content = "\n\n".join(parts).strip()

            if not combined_content:
                return _fail("No readable text found in uploaded files.")

            final_name = _derive_course_name(stems, course_name)

            with _SESSION_FACTORY() as db:
                row = Course(course_name=final_name, course_content=combined_content)
                db.add(row)
                db.flush()
                new_id = row.course_id
                db.commit()

            return _success(
                data_str=f"Saved 1 course(s): {final_name}=>id={new_id}",
                message="Stored concatenated text from uploaded files into a single course."
            )

        elif body and isinstance(body, dict) and body.get("content"):
            cname = (body.get("course_name") or "Untitled")[:255]
            content = str(body["content"]).strip()
            if not content:
                return _fail("Content is empty.")

            with _SESSION_FACTORY() as db:
                row = Course(course_name=cname, course_content=content)
                db.add(row)
                db.flush()
                new_id = row.course_id
                db.commit()

            return _success(
                data_str=f"Saved 1 course(s): {cname}=>id={new_id}",
                message="Stored raw text into courses table."
            )

        else:
            return _fail("Provide 'files' (one or many) OR JSON {content, course_name}.")

    except HTTPException:
        raise
    except Exception as e:
        return _fail(f"Ingestion failed: {type(e).__name__}")

# ---------------- GET: /courses (list) ----------------
def list_courses(
    limit: int = 25,
    offset: int = 0,
    q: Optional[str] = None,
):
    """
    GET /courses   (route defined in app.py)
    Lists saved rows with basic pagination and optional name search.
    'data' is a JSON string.
    """
    if _SESSION_FACTORY is None:
        return _fail("Server misconfigured: no DB session factory is set.")

    with _SESSION_FACTORY() as db:
        stmt = select(
            Course.course_id,
            Course.course_name,
            func.length(Course.course_content).label("content_len"),
            Course.created_at,
        )
        if q:
            stmt = stmt.where(func.lower(Course.course_name).like(f"%{q.lower()}%"))
        stmt = stmt.order_by(Course.course_id.desc()).offset(offset).limit(limit)

        rows = db.execute(stmt).all()
        payload = [
            {
                "course_id": r.course_id,
                "course_name": r.course_name,
                "content_len": int(r.content_len or 0),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
        return _success(
            data_str=json.dumps(payload, ensure_ascii=False),
            message=f"Fetched {len(payload)} course(s).",
        )

# ---------------- GET: /courses/{course_id} (detail) ----------------
def get_course(course_id: int):
    """
    GET /courses/{course_id}   (route defined in app.py)
    Returns one row with full content. 'data' is a JSON string.
    """
    if _SESSION_FACTORY is None:
        return _fail("Server misconfigured: no DB session factory is set.")

    with _SESSION_FACTORY() as db:
        row = db.execute(
            select(Course).where(Course.course_id == course_id)
        ).scalar_one_or_none()

        if not row:
            return _fail(f"Course id={course_id} not found")

        payload = {
            "course_id": row.course_id,
            "course_name": row.course_name,
            "course_content": row.course_content,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        return _success(
            data_str=json.dumps(payload, ensure_ascii=False),
            message=f"Fetched course id={course_id}.",
        )
