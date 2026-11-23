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
        self._json(
            {
                "message": {"role": "assistant", "content": "Ödeme servisini güncellemen gerekiyor [K1]."},
                "logprobs": [{"token": "a", "logprob": -0.1}, {"token": "b", "logprob": -0.3}],
                "eval_count": 2,
            }
        )

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
    assert "[K1] Görev" in system and "uydurma" in system  # kayıtlar istemde
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
