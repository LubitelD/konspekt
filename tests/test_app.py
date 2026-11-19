"""Локальний тест без мережі: клієнт Claude підміняється заглушкою."""
import os, sys, types
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient
import main

NOTES = {"title": "Алгоритм Дейкстри", "summary": "Пошук найкоротших шляхів.",
         "key_points": ["Жадібний вибір", "Релаксація"], "terms": [{"term": "Релаксація", "definition": "Оновлення d[v]"}],
         "questions": ["Чому ваги мають бути невід'ємні?"]}
calls = []

class FakeMessages:
    def create(self, **kw):
        calls.append(kw)
        return types.SimpleNamespace(
            model=kw["model"],
            content=[types.SimpleNamespace(type="tool_use", input=NOTES, name="save_notes")],
            usage=types.SimpleNamespace(input_tokens=321, output_tokens=123))

main._client = types.SimpleNamespace(messages=FakeMessages())
c = TestClient(main.app)

assert c.get("/").status_code == 200 and "Конспектувач" in c.get("/").text
assert c.get("/api/health").json()["model"] == "claude-haiku-5-5"
r = c.post("/api/notes", json={"text": "Короткий"}); assert r.status_code == 422, r.status_code
r = c.post("/api/notes", json={"text": "x" * 20001}); assert r.status_code == 413, r.status_code
r = c.post("/api/notes", json={"text": "Алгоритм Дейкстри знаходить найкоротші шляхи у графі з невід'ємними вагами."})
assert r.status_code == 200, r.text
assert r.json()["notes"]["title"] == "Алгоритм Дейкстри" and r.json()["meta"]["input_tokens"] == 321
kw = calls[-1]
assert kw["tool_choice"] == {"type": "tool", "name": "save_notes"} and kw["tools"][0]["name"] == "save_notes"
main.ACCESS_CODE = "1234"
assert c.post("/api/notes", json={"text": "y" * 60}).status_code == 401
assert c.post("/api/notes", json={"text": "y" * 60}, headers={"x-access-code": "1234"}).status_code == 200
print("ALL TESTS PASSED")
