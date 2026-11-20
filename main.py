"""Конспектувач — вебсервіс, що перетворює текст лекції на структурований конспект.

Потік: браузер → POST /api/notes (цей сервіс на Cloud Run) → Claude Messages API → JSON → браузер.
API-ключ Anthropic приходить у змінній ANTHROPIC_API_KEY (на Cloud Run — із Secret Manager).
"""
import os
import time

import anthropic
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-5-5")
MAX_INPUT_CHARS = int(os.environ.get("MAX_INPUT_CHARS", "20000"))
ACCESS_CODE = os.environ.get("ACCESS_CODE", "")  # якщо задано — без коду сервіс не відповідає

app = FastAPI(title="Конспектувач")
app.mount("/static", StaticFiles(directory="static"), name="static")
_client = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # ключ береться з ANTHROPIC_API_KEY
    return _client


# Інструмент (tool use): змушуємо модель повернути конспект строго за JSON-схемою
NOTES_TOOL = {
    "name": "save_notes",
    "description": "Зберегти структурований конспект лекції.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Коротка назва теми лекції"},
            "summary": {"type": "string", "description": "Стислий виклад суті, 3–5 речень"},
            "key_points": {"type": "array", "items": {"type": "string"},
                           "description": "5–8 головних тез"},
            "terms": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"term": {"type": "string"}, "definition": {"type": "string"}},
                    "required": ["term", "definition"],
                },
                "description": "Ключові терміни з визначеннями",
            },
            "questions": {"type": "array", "items": {"type": "string"},
                          "description": "3–5 питань для самоперевірки"},
        },
        "required": ["title", "summary", "key_points", "terms", "questions"],
    },
}

SYSTEM = (
    "Ти помічник студента. Складаєш точні, стислі конспекти лекцій. "
    "Використовуй лише інформацію з наданого тексту, нічого не вигадуй. "
    "Пиши мовою вхідного тексту; якщо вона незрозуміла — українською."
)


class NotesRequest(BaseModel):
    text: str = Field(..., min_length=50)


def clean_notes(n: dict) -> dict:
    """Нормалізує відповідь моделі: модель зрідка відходить від схеми (напр. термін рядком)."""
    def strs(x):
        return [s.strip() for s in x if isinstance(s, str) and s.strip()] if isinstance(x, list) else []

    terms = []
    for t in n.get("terms") or []:
        term = definition = ""
        if isinstance(t, dict):
            term = str(t.get("term") or t.get("name") or "").strip()
            definition = str(t.get("definition") or t.get("description") or "").strip()
            if not term and len(t) == 1:
                (term, definition), = ((str(k), str(v)) for k, v in t.items())
        elif isinstance(t, str):
            for sep in (" — ", " – ", " - ", ": "):
                if sep in t:
                    term, definition = (p.strip() for p in t.split(sep, 1))
                    break
        if term and definition:
            terms.append({"term": term, "definition": definition})

    return {
        "title": str(n.get("title") or "Конспект").strip(),
        "summary": str(n.get("summary") or "").strip(),
        "key_points": strs(n.get("key_points")),
        "terms": terms,
        "questions": strs(n.get("questions")),
    }


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "model": MODEL, "key_configured": bool(os.environ.get("ANTHROPIC_API_KEY"))}


@app.post("/api/notes")
def make_notes(req: NotesRequest, request: Request):
    if ACCESS_CODE and request.headers.get("x-access-code") != ACCESS_CODE:
        raise HTTPException(401, "Невірний код доступу")
    text = req.text.strip()
    if len(text) > MAX_INPUT_CHARS:
        raise HTTPException(413, f"Текст задовгий: максимум {MAX_INPUT_CHARS} символів")

    t0 = time.time()
    try:
        msg = client().messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM,
            tools=[NOTES_TOOL],
            tool_choice={"type": "tool", "name": "save_notes"},
            messages=[{"role": "user", "content": f"Склади конспект цієї лекції:\n\n<lecture>\n{text}\n</lecture>"}],
        )
    except anthropic.AuthenticationError:
        raise HTTPException(500, "Невірний або відсутній ANTHROPIC_API_KEY")
    except anthropic.RateLimitError:
        raise HTTPException(429, "Перевищено ліміт запитів до Claude API, спробуйте пізніше")
    except anthropic.APIError as e:
        raise HTTPException(502, f"Помилка Claude API: {e}")

    notes = next((b.input for b in msg.content if b.type == "tool_use"), None)
    if notes is None:
        raise HTTPException(502, "Модель не повернула конспект")
    return {
        "notes": clean_notes(notes),
        "meta": {
            "model": msg.model,
            "input_tokens": msg.usage.input_tokens,
            "output_tokens": msg.usage.output_tokens,
            "seconds": round(time.time() - t0, 2),
        },
    }
