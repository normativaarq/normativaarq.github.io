"""CTE Explorer -- tiny FastAPI app.

Run:
    uvicorn app.main:app --reload

Then open http://127.0.0.1:8000
"""

import pathlib

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.database import DATA_DIR
from app.search import search

BASE_DIR = pathlib.Path(__file__).resolve().parent
INDEX_HTML = (BASE_DIR / "templates" / "index.html").read_text(encoding="utf-8")

app = FastAPI(title="CTE Explorer (research prototype)")

# Serves the original PDFs so results can link straight to
# /pdf/<filename>#page=N for the user to verify a passage themselves.
DATA_DIR.mkdir(exist_ok=True)
app.mount("/pdf", StaticFiles(directory=str(DATA_DIR)), name="pdf")


@app.get("/", response_class=HTMLResponse)
def index():
    return INDEX_HTML


@app.get("/api/search")
def api_search(q: str = Query(..., min_length=1, description="Natural-language question")):
    return {"query": q, "results": search(q)}
