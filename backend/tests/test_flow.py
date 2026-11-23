from conftest import AYSE, LEAD


def _planning_doc(client):
    docs = client.get("/api/documents/shared", headers=LEAD).json()
    assert docs == []  # liderle paylaşılan yok; planlama notu ekibe ait
    return client.get("/api/documents/1", headers=LEAD).json()


def test_extract_tasks_with_sources(client):
    doc = _planning_doc(client)
    tasks = client.post("/api/documents/1/extract", headers=LEAD).json()
    assert [t["source"]["ref"] for t in tasks] == ["§2", "§3", "§4", "§5", "§6", "§7"]
    for t in tasks:
        s = t["source"]
        # her görev dokümandaki gerçek bir alıntıya bağlı olmalı
        assert doc["text"][s["start"] : s["end"]] == s["quote"]


def test_suggestions(client):
    tasks = {t["source"]["ref"]: t for t in client.get("/api/documents/1/tasks", headers=LEAD).json()}
    assert tasks["§2"]["suggested"]["id"] == "ayse"
    assert tasks["§3"]["suggested"]["id"] == "mert"
    assert tasks["§4"]["suggested"]["id"] == "selin"
    assert tasks["§5"]["suggested"]["id"] == "elif"
    assert tasks["§6"]["suggested"]["id"] == "can"
    assert tasks["§6"]["alternative"] is not None  # Can aşırı yüklü
    assert tasks["§7"]["confidence"] == 1 and tasks["§7"]["forcing"] is True


def test_non_lead_cannot_extract(client):
    assert client.post("/api/documents/1/extract", headers=AYSE).status_code == 403


def test_forcing_requires_lead_pick_first(client):
    tasks = {t["source"]["ref"]: t for t in client.get("/api/documents/1/tasks", headers=LEAD).json()}
    low = tasks["§7"]
    r = client.post(f"/api/tasks/{low['id']}/decision", json={"action": "accept"}, headers=LEAD)
    assert r.status_code == 409
    r = client.post(f"/api/tasks/{low['id']}/decision", json={"action": "pick", "assignee_id": "selin"}, headers=LEAD)
    assert r.json()["lead_picked_first"] is True
    r = client.post(f"/api/tasks/{low['id']}/decision", json={"action": "accept"}, headers=LEAD)
    assert r.json()["status"] == "accepted" and r.json()["assignee"]["id"] == "selin"


def test_accept_and_export(client):
    tasks = {t["source"]["ref"]: t for t in client.get("/api/documents/1/tasks", headers=LEAD).json()}
    client.post(f"/api/tasks/{tasks['§2']['id']}/decision", json={"action": "accept"}, headers=LEAD)
    client.post(f"/api/tasks/{tasks['§3']['id']}/decision", json={"action": "reject"}, headers=LEAD)
    out = client.post("/api/documents/1/export", headers=LEAD).json()["exported"]
    keys = sorted(e["key"] for e in out)
    assert keys == ["MB-419", "MB-420"]  # §2 ve §7 (onaylananlar)


def test_chat_my_tasks_and_shared(client):
    r = client.post(
        "/api/conversations",
        json={"text": "Bugün bana verilen görevler ne? Benimle paylaşılan bir şey var mı?"},
        headers=AYSE,
    ).json()
    bot = r["messages"][1]
    kinds = [b["type"] for b in bot["blocks"]]
    assert kinds == ["tasks", "documents"]
    task_keys = {i["key"] for i in bot["blocks"][0]["items"]}
    assert {"MB-412", "MB-418"} <= task_keys
    titles = {i["title"] for i in bot["blocks"][1]["items"]}
    # elle paylaşılan taslak + aktarılan görevin kaynak dokümanı otomatik paylaşılır
    assert {"Limit Servisi — Mimari Taslak v2", "Sprint 14 Planlama Notu"} <= titles


def test_chat_fallback_is_honest(client):
    r = client.post("/api/conversations", json={"text": "Mikroservis mimarisi nedir?"}, headers=AYSE).json()
    assert "henüz bağlanmadı" in r["messages"][1]["text"]


def test_team_load_and_stats(client):
    load = client.get("/api/team/load", headers=LEAD).json()
    can = next(m for m in load["members"] if m["id"] == "can")
    assert can["after"] >= 90
    acc = client.get("/api/stats/accuracy", headers=LEAD).json()
    assert [a["level"] for a in acc] == [3, 2, 1]


def test_reextract_does_not_duplicate_decided(client):
    before = client.get("/api/documents/1/tasks", headers=LEAD).json()
    decided = [t for t in before if t["status"] != "suggested"]
    after = client.post("/api/documents/1/extract", headers=LEAD).json()
    spans = [(t["source"]["start"], t["source"]["end"]) for t in after]
    assert len(spans) == len(set(spans))  # aynı cümle iki kez yok
    assert len([t for t in after if t["status"] != "suggested"]) == len(decided)
