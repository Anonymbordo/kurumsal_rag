"""Decoder (RAG) entegrasyonu: sahte bir Ollama sunucusuyla."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from conftest import AYSE

import app.services.assistant as assistant
from app.llm.decoder import OllamaDecoder

SEEN: dict = {}


class FakeOllama(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self._json({"models": [{"name": "test:1b"}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN["body"] = body
        if self.path == "/api/generate":  # ısıtma
            return self._json({"done": True})
        pieces = ["Ödeme servisini ", "güncellemen gerekiyor [K1]."]
        final = {"done": True, "eval_count": 2, "prompt_eval_count": 120, "prompt_eval_duration": 4e8, "eval_duration": 2e8}
        if body.get("stream"):
            lines = [{"message": {"content": p}, "logprobs": [{"token": p, "logprob": -0.2}], "done": False} for p in pieces]
            data = "".join(json.dumps(x) + "\n" for x in lines + [final]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self._json({"message": {"role": "assistant", "content": "".join(pieces)},
                    "logprobs": [{"token": "a", "logprob": -0.1}, {"token": "b", "logprob": -0.3}], **final})

    def _json(self, obj):
        data = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _server():
    srv = HTTPServer(("127.0.0.1", 0), FakeOllama)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_explain_without_decoder_uses_records(client):
    r = client.post("/api/conversations", json={"text": "görevimi tam açıklar mısın"}, headers=AYSE).json()
    bot = r["messages"][-1]
    assert bot["blocks"] and bot["blocks"][0]["type"] == "tasks"
    assert "Teslim" in bot["text"] and "henüz bağlanmadı" not in bot["text"]


def test_explain_with_decoder_is_grounded_and_cited(client, monkeypatch):
    srv = _server()
    dec = OllamaDecoder(f"http://127.0.0.1:{srv.server_port}", "test:1b")
    monkeypatch.setattr(assistant, "get_decoder", lambda: dec)
    r = client.post("/api/conversations", json={"text": "görevimi açıklar mısın"}, headers=AYSE).json()
    bot = r["messages"][-1]
    assert "[1]" in bot["text"]
    assert bot["sources"][0].startswith("[1] ")
    assert "ort. token olasılığı %" in bot["sources"][-1]
    system = SEEN["body"]["messages"][0]["content"]
    assert "[K1] Görev" in system and "Uydurma" in system  # kayıtlar istemde
    srv.shutdown()


def test_free_question_goes_to_decoder(client, monkeypatch):
    srv = _server()
    dec = OllamaDecoder(f"http://127.0.0.1:{srv.server_port}", "test:1b")
    monkeypatch.setattr(assistant, "get_decoder", lambda: dec)
    r = client.post("/api/conversations", json={"text": "fatura işinde hangi teknolojiyi kullanmalıyım?"}, headers=AYSE).json()
    assert "güncellemen" in r["messages"][-1]["text"]
    srv.shutdown()


def test_unreachable_decoder_is_not_available():
    assert OllamaDecoder("http://127.0.0.1:9", "x").available() is False


def test_stream_endpoint_sends_deltas_then_saves(client, monkeypatch):
    srv = _server()
    dec = OllamaDecoder(f"http://127.0.0.1:{srv.server_port}", "test:1b")
    monkeypatch.setattr(assistant, "get_decoder", lambda: dec)
    conv = client.post("/api/conversations", json={"text": "fatura nereden başlar?", "defer": True}, headers=AYSE).json()
    assert conv["messages"] == []
    cid = conv["conversation"]["id"]
    r = client.post(f"/api/conversations/{cid}/messages/stream", json={"text": "fatura nereden başlar?"}, headers=AYSE)
    events = [json.loads(l) for l in r.text.splitlines() if l.strip()]
    deltas = [e["text"] for e in events if e["type"] == "delta"]
    assert deltas == ["Ödeme servisini ", "güncellemen gerekiyor [K1]."]
    done = events[-1]
    assert done["type"] == "done" and done["messages"][1]["text"].startswith("Ödeme servisini güncellemen")
    assert "istem 120 token" in done["messages"][1]["sources"][-1]
    saved = client.get(f"/api/conversations/{cid}/messages", headers=AYSE).json()["messages"]
    assert len(saved) == 2
    srv.shutdown()


def test_stream_without_decoder_returns_template(client):
    cid = client.post("/api/conversations", json={"text": "x", "defer": True}, headers=AYSE).json()["conversation"]["id"]
    r = client.post(f"/api/conversations/{cid}/messages/stream", json={"text": "Bugün bana verilen görevler ne?"}, headers=AYSE)
    events = [json.loads(l) for l in r.text.splitlines() if l.strip()]
    assert len(events) == 1 and events[0]["type"] == "done"
    assert events[0]["messages"][1]["blocks"]
