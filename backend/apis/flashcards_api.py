# backend/apis/flashcards_api.py
import os
import json
from typing import Callable, List, Optional

from fastapi import Body
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from models import Course, Flashcard
from openai import OpenAI

_SESSION_FACTORY: Optional[Callable[[], Session]] = None

def set_session_factory_for_flashcards(factory: Callable[[], Session]) -> None:
    global _SESSION_FACTORY
    _SESSION_FACTORY = factory

def _fail(msg: str) -> dict:
    return {"status": "FAIL", "statusCode": 200, "message": msg, "data": ""}

def _success(data_str: str, message: str = "") -> dict:
    return {"status": "SUCCESS", "statusCode": 200, "message": message, "data": data_str}

def _get_openai_client() -> OpenAI:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing OPENAI_API_KEY")
    return OpenAI(api_key=key)

def _generate_flashcards_from_text(text: str, n: int = 10) -> List[dict]:
    client = _get_openai_client()
    system = (
        "You create educational flashcards. "
        "Keep language simple and clear. Each card has a concise front (prompt) and a helpful back (answer)."
    )
    user = (
        "From the content below, create EXACTLY {n} flashcards. "
        "Return ONLY a strict JSON array of objects with keys 'front' and 'back' (no markdown, no extra text). "
        "Front: a short question/fill-in/prompt. Back: a brief but clear answer or explanation.\n\n"
        "<content>\n"
        f"{text}\n"
        "</content>"
    ).replace("{n}", str(n))

    resp = client.responses.create(model="gpt-4o-mini", input=f"{system}\n\n{user}", temperature=0.2)
    raw = getattr(resp, "output_text", None) or str(resp)

    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("not a list")
    except Exception:
        start = raw.find("["); end = raw.rfind("]")
        if start != -1 and end != -1 and end > start:
            data = json.loads(raw[start:end+1])
        else:
            raise ValueError("Model did not return JSON")

    cards: List[dict] = []
    for item in data:
        if not isinstance(item, dict): continue
        front = str(item.get("front", "")).strip()
        back = str(item.get("back", "")).strip()
        if front and back:
            cards.append({"front": front[:500], "back": back[:1200]})
        if len(cards) == n: break

    if len(cards) < n:
        for _ in range(n - len(cards)):
            cards.append({"front": f"Key idea {len(cards)+1}?", "back": "Brief explanation."})
    elif len(cards) > n:
        cards = cards[:n]
    return cards

def create_or_replace_flashcards(course_id: int):
    if _SESSION_FACTORY is None:
        return _fail("Server misconfigured: no DB session factory is set.")

    # fetch only needed columns (avoid non-existent fields)
    with _SESSION_FACTORY() as db:
        row = db.execute(
            select(Course.course_id, Course.course_name, Course.course_content)
            .where(Course.course_id == course_id)
        ).one_or_none()
        if not row:
            return _fail(f"Course id={course_id} not found")

        _, _, content = row
        content = (content or "").strip()
        if not content:
            return _fail(f"Course id={course_id} has no content")

    try:
        cards = _generate_flashcards_from_text(content, n=10)
    except RuntimeError as e:
        return _fail(str(e))
    except Exception as e:
        return _fail(f"AI call failed: {type(e).__name__}")

    with _SESSION_FACTORY() as db:
        db.execute(delete(Flashcard).where(Flashcard.course_id == course_id))
        for idx, card in enumerate(cards, start=1):
            db.add(Flashcard(course_id=course_id, card_index=idx,
                             front_text=card["front"], back_text=card["back"]))
        db.commit()

    return _success(f"Inserted 10 flashcards for course_id={course_id}",
                    message="Flashcards generated and replaced successfully.")


# ---------------- GET: /courses/{course_id}/flashcards ----------------
def get_flashcards(course_id: int):
    """
    GET /courses/{course_id}/flashcards
    Returns flashcards for the course, ordered by card_index.
    Response 'data' is a JSON string of:
      [{ "flashcard_id": ..., "card_index": 1, "front_text": "...", "back_text": "..." }, ...]
    """
    if _SESSION_FACTORY is None:
        return _fail("Server misconfigured: no DB session factory is set.")

    with _SESSION_FACTORY() as db:
        rows = db.execute(
            select(Flashcard)
            .where(Flashcard.course_id == course_id)
            .order_by(Flashcard.card_index.asc())
        ).scalars().all()

        payload = [
            {
                "flashcard_id": r.flashcard_id,
                "card_index": r.card_index,
                "front_text": r.front_text,
                "back_text": r.back_text,
            }
            for r in rows
        ]

    return _success(
        data_str=json.dumps(payload, ensure_ascii=False),
        message=f"Fetched {len(payload)} flashcard(s) for course_id={course_id}."
    )