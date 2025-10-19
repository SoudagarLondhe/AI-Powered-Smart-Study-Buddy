import os
import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apis.auth_api import SignUpAPI, LoginAPI, GenerateQuizAPI
# from apis.gpt_api import SummarizeAPI

from apis.gpt_api import router as gpt_router
from models import init_models  # uses metadata only (no DB setup here)

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

app.add_api_route("/auth/signup", SignUpAPI(SessionLocal), methods=["POST"])
app.add_api_route("/auth/login",  LoginAPI(SessionLocal),  methods=["POST"])
app.add_api_route("/auth/generate/quiz", GenerateQuizAPI(SessionLocal), methods=["POST","DELETE"])


# app.add_api_route("/ai/summarize", SummarizeAPI(), methods=["POST"])

app.include_router(gpt_router)

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
