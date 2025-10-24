# backend/app.py
import os
import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apis.auth_api import SignUpAPI, LoginAPI
from models import init_models  # from models/db_model.py

# Import ONLY the functions (no router) from gpt_api
from apis.gpt_api import (
    set_session_factory,
    ingest_and_store_endpoint,
    list_courses,
    get_course,
    generate_course_summary,
    get_course_summary, 
)

from apis.flashcards_api import (
    set_session_factory_for_flashcards,
    create_or_replace_flashcards,
    get_flashcards,
)

# --- DB connection lives ONLY here ---
load_dotenv()  # reads .env at project root
DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError(
        "Set DATABASE_URL in .env, e.g. postgresql+psycopg://postgres:pass@localhost:5432/smart_study_buddy"
    )

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

# create tables once
init_models(engine)

# --- FastAPI + URL mappings ---
app = FastAPI(title="APIs")

# Auth routes (class-callables)
app.add_api_route("/auth/signup", SignUpAPI(SessionLocal), methods=["POST"])
app.add_api_route("/auth/login",  LoginAPI(SessionLocal),  methods=["POST"])

# Provide DB session to content ingestion/fetch functions
set_session_factory(SessionLocal)
set_session_factory_for_flashcards(SessionLocal)

# Content ingestion + read routes (function-callables)
app.add_api_route("/addcourse", ingest_and_store_endpoint, methods=["POST"])
app.add_api_route("/courses",      list_courses,              methods=["GET"])
app.add_api_route("/courses/{course_id}", get_course,         methods=["GET"])
app.add_api_route("/courses/{course_id}/summary", generate_course_summary, methods=["POST"])
app.add_api_route("/courses/{course_id}/summary", get_course_summary,      methods=["GET"])

app.add_api_route("/courses/{course_id}/flashcards", create_or_replace_flashcards, methods=["POST"])
app.add_api_route("/courses/{course_id}/flashcards", get_flashcards,              methods=["GET"])

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
