import os
from tempfile import NamedTemporaryFile
from textwrap import dedent
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from openai import OpenAI

# File parsers
import pdfplumber
from docx import Document as DocxDocument
from pptx import Presentation

from schemas import SummarizeIn

# ---------------- env & client ----------------
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY. Set it in your environment or .env file.")

client = OpenAI(api_key=API_KEY)
router = APIRouter()

# ---------------- constants ----------------
MAX_BYTES = 50 * 1024 * 1024  # 50 MB per file
SECTION_MARK = "<<SECTION>>"
POINT_MARK   = "<<POINT>>"

# ---------------- envelope helpers ----------------
def _fail(msg: str):
    return {"status": "FAIL", "statusCode": 200, "message": msg, "data": ""}

def _success(data_str: str, message: str = ""):
    return {"status": "SUCCESS", "statusCode": 200, "message": message, "data": data_str}

# ---------------- extraction helpers ----------------
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
    """Returns list of (filename, text)."""
    out: List[tuple[str, str]] = []
    for up in uploads:
        text = _extract_text_from_upload(up)
        out.append((up.filename or "uploaded", text))
    return out

# ---------------- chunking & synthesis ----------------
def _chunk(text: str, max_chars: int = 12000) -> List[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    chunks, start = [], 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        nl = text.rfind("\n", start, end)
        if nl != -1 and nl > start + 1000:
            end = nl
        chunks.append(text[start:end])
        start = end
    return chunks

def _safe_trim(marked_text: str, char_limit: int) -> str:
    """Trim to <= char_limit, but try not to cut in the middle of a marker/point."""
    if char_limit is None or char_limit <= 0:
        return marked_text
    if len(marked_text) <= char_limit:
        return marked_text
    cut = marked_text[:char_limit]

    # Try to end at the last full line or last marker
    last_marker = max(cut.rfind(POINT_MARK), cut.rfind(SECTION_MARK), cut.rfind("\n"))
    if last_marker > 0 and last_marker > char_limit - 120:  # keep within ~120 chars of limit
        cut = cut[:last_marker].rstrip()
    return cut

def _summarize_marked(text: str, prompt: Optional[str], char_limit: int) -> str:
    """
    Create a single, marked string using <<SECTION>> and <<POINT>>.
    We ask the model to obey the char limit; then we trim safely if needed.
    """
    parts = _chunk(text)
    partials: List[str] = []

    # 1) summarize chunks into marked sections
    for i, part in enumerate(parts, 1):
        system = (
            "You are a concise study assistant who outputs plain text with markers. "
            f"Use '{SECTION_MARK}' for section titles and '{POINT_MARK}' for bullet points. "
            "Do NOT output markdown; only plain text with those markers."
        )
        user = dedent(f"""
            Create a compact study summary for this part ({i}/{len(parts)}).
            Constraints:
            - Overall output target (for the whole document): about {char_limit} characters.
            - Use these markers EXACTLY:
              {SECTION_MARK} <Section Title>
              {POINT_MARK} <short point>
            - Prefer compact phrasing; no prose paragraphs.

            Extra instruction (optional): {prompt or ''}

            <content>
            {part}
            </content>
        """).strip()

        resp = client.responses.create(
            model="gpt-4o-mini",
            input=f"{system}\n\n{user}",
            temperature=0.2,
        )
        text_out = getattr(resp, "output_text", None) or str(resp)
        partials.append(text_out.strip())

    if len(partials) == 1:
        combined = partials[0]
    else:
        # 2) synthesize all chunk summaries into a single marked summary
        sep = "\n"
        sectional = sep.join(partials)
        system = (
            "Combine multiple chunk summaries into ONE compact summary. "
            f"Keep ONLY these markers: '{SECTION_MARK}' and '{POINT_MARK}'. No markdown."
        )
        user = dedent(f"""
            Merge the following marked summaries into a single cohesive study outline.
            Keep the result within ~{char_limit} characters if possible.
            Use multiple {SECTION_MARK} blocks, each with several {POINT_MARK} items.

            <marked_summaries>
            {sectional}
            </marked_summaries>
        """).strip()

        final = client.responses.create(
            model="gpt-4o-mini",
            input=f"{system}\n\n{user}",
            temperature=0.2,
        )
        combined = getattr(final, "output_text", None) or str(final)

    # 3) enforce character budget on the final string
    combined = _safe_trim(combined, char_limit)
    return combined.strip()

# ---------------- endpoint ----------------
@router.post("/ai/summarize")
def summarize_endpoint(
    # Multipart (multi or single)
    files: Optional[List[UploadFile]] = File(default=None),
    file: Optional[UploadFile] = File(default=None),
    prompt: Optional[str] = Form(default=None),
    max_words_form: Optional[int] = Form(default=None),  # reinterpreted as CHAR limit
    # JSON (backward compatible)
    body: Optional[SummarizeIn] = Body(default=None),
):
    try:
        char_limit = None
        merged_text = ""
        message = ""

        if files is not None and len(files) > 0:
            extracted = _extract_many(files)
            # Merge all file texts with light separators to hint sections by filename
            merged_text = "\n\n".join(f"=== FILE: {name} ===\n{text}" for name, text in extracted)
            char_limit = max_words_form if max_words_form else 1200
            message = f"Merged {len(extracted)} files."
        elif file is not None:
            merged_text = _extract_text_from_upload(file)
            char_limit = max_words_form if max_words_form else 1200
            message = f"Processed file: {file.filename}"
        elif body is not None and (body.content and body.content.strip()):
            merged_text = body.content.strip()
            # JSON path: use body's max_words as char limit if present
            char_limit = (body.max_words or 1200)
            prompt = body.prompt if body.prompt else prompt
            message = "Processed raw text."
        else:
            return _fail("Provide files (PDF/DOCX/PPTX), a single file, or JSON {content}.")

        if not merged_text.strip():
            return _fail("No readable text found.")

        marked = _summarize_marked(merged_text, prompt, char_limit)
        return _success(marked, message=message)

    except HTTPException:
        raise
    except Exception as e:
        return _fail(f"Summarization failed: {type(e).__name__}")
