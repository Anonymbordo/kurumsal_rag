"""Toplantı: kayıt parçaları → döküm → görev önerileri → rapor (sahte ASR ile)."""
from conftest import AYSE, LEAD

import app.services.meetings as svc
from app.services.transcribe import Segment

MERT = {"X-User-Id": "mert"}

SCRIPTS = {
    "ayse": [Segment(1.0, 5.0, "Geçen sprintte ödeme servisi sorunsuz çıktı"),
             Segment(20.0, 26.0, "Fatura dışa aktarma zaman aşımını ben yarın düzeltirim")],
    "mert": [Segment(8.0, 14.0, "iOS bildirim izni akışı bazı cihazlarda takılıyor"),
             Segment(30.0, 36.0, "Selin yeni sürüm için regresyon testlerini hazırlamalı")],
}


class FakeASR:
    name = "fake"

    def transcribe(self, path):
        uid = path.rsplit("_", 1)[1].split(".")[0]
        return SCRIPTS[uid]


def test_meeting_flow(client, monkeypatch):
    monkeypatch.setattr(svc, "get_transcriber", lambda: FakeASR())
    monkeypatch.setattr(svc, "start_processing", svc.process)  # testte senkron
    monkeypatch.setattr(svc, "get_decoder", lambda: None)

    m = client.post("/api/meetings", json={"title": "Sprint 19 planlama", "participants": ["ayse", "mert"]}, headers=LEAD).json()
    assert m["status"] == "live" and m["room"].startswith("ga-sprint19planlama-")
    assert {p["id"] for p in m["participants"]} == {"ayse", "mert", "burak"}

    for who in (AYSE, MERT):
        r = client.post(f"/api/meetings/{m['id']}/recordings", headers=who).json()
        for seq in range(2):
            ok = client.post(f"/api/meetings/recordings/{r['id']}/chunks?seq={seq}", content=b"webm" * 10, headers=who)
            assert ok.status_code == 200
        # sıra dışı parça reddedilir
        assert client.post(f"/api/meetings/recordings/{r['id']}/chunks?seq=5", content=b"x", headers=who).status_code == 409
        # başkasının kaydına yazılamaz
        assert client.post(f"/api/meetings/recordings/{r['id']}/chunks?seq=2", content=b"x", headers=LEAD).status_code == 404

    assert client.post(f"/api/meetings/{m['id']}/end", headers=MERT).status_code == 403
    client.post(f"/api/meetings/{m['id']}/end", headers=LEAD)
    done = client.get(f"/api/meetings/{m['id']}", headers=AYSE).json()
    assert done["status"] == "done", done["error"]
    speakers = [u["speaker"] for u in done["transcript"]]
    assert speakers == ["Ayşe Kaya", "Mert Demir", "Ayşe Kaya", "Mert Demir"]
    assert "## Görev önerileri" in done["report"] and "Konuşanlar:" in done["report"]

    tasks = client.get(f"/api/documents/{done['document_id']}/tasks", headers=LEAD).json()
    by = {t["source"]["quote"].split(":")[-1].strip()[:20]: t for t in tasks}
    fatura = next(t for t in tasks if "Fatura" in t["source"]["quote"])
    assert fatura["suggested"]["name"] == "Ayşe Kaya"
    assert any("kendisi üstlendi" in r for r in fatura["reasons"])
    regresyon = next(t for t in tasks if "regresyon" in t["source"]["quote"])
    assert regresyon["suggested"]["name"] == "Selin Arslan"  # konuşan Mert ama adı geçen Selin
    assert by  # döküm dokümanı katılımcılarla paylaşıldı
    shared = client.get("/api/documents/shared", headers=AYSE).json()
    assert any(d["id"] == done["document_id"] for d in shared)


def test_meeting_without_audio_fails_clearly(client, monkeypatch):
    monkeypatch.setattr(svc, "start_processing", svc.process)
    m = client.post("/api/meetings", json={"title": "Boş toplantı"}, headers=LEAD).json()
    client.post(f"/api/meetings/{m['id']}/end", headers=LEAD)
    r = client.get(f"/api/meetings/{m['id']}", headers=LEAD).json()
    assert r["status"] == "failed" and "ses kaydı yok" in r["error"]


def test_non_participant_cannot_see(client):
    m = client.post("/api/meetings", json={"title": "Gizli", "participants": ["ayse"]}, headers=LEAD).json()
    assert client.get(f"/api/meetings/{m['id']}", headers=MERT).status_code == 403
    assert all(x["id"] != m["id"] for x in client.get("/api/meetings", headers=MERT).json())
