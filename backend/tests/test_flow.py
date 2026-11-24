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


def test_reject_reason_and_candidates(client):
    tasks = client.get("/api/documents/1/tasks", headers=LEAD).json()
    open_ = [t for t in tasks if t["status"] == "suggested"]
    r = client.post(f"/api/tasks/{open_[0]['id']}/decision", json={"action": "reject", "reason": "not_now"}, headers=LEAD).json()
    assert r["status"] == "rejected" and r["reject_reason"] == "not_now"


def test_labeling_preview_is_blind_for_test(client, tmp_path, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "samples_dir", str(tmp_path))
    data = {"text": "Ali bu hafta raporu hazırlamalı. Toplantı iyi geçti.", "split": "test", "names": "Ali"}
    r = client.post("/api/labeling/preview", data=data, headers=LEAD).json()
    assert r["suggestions"] is None  # test için kör
    assert "Ali" not in r["text"]  # anonimleştirildi
    body = {"title": "deneme", "split": "test", "text": r["text"], "sentences": r["sentences"], "labels": ["task", "not_task"]}
    saved = client.post("/api/labeling/save", json=body, headers=LEAD).json()
    assert saved["tasks"] == 1 and (tmp_path / "test" / "gold.json").exists()


DOC = """Haftalık Notlar
Katılımcılar: Zehra Ak (Backend Geliştirici), Tuna Er (QA Mühendisi), Ayşe Kaya (Backend)
Zehra rapor servisindeki zaman aşımını bu hafta çözmeli.
Not: Cuma günü herkes güvenlik eğitimine katılmalı.
Tuna yeni sürüm için regresyon testlerini hazırlamalı.
"""


def test_people_announcement_and_import(client):
    doc = client.post("/api/documents", data={"text": DOC, "title": "Notlar"}, headers=LEAD).json()
    people = client.get(f"/api/documents/{doc['id']}/people", headers=LEAD).json()
    byname = {p["name"]: p for p in people}
    assert byname["Ayşe Kaya"]["user_id"] == "ayse"
    assert byname["Zehra Ak"]["user_id"] is None and byname["Zehra Ak"]["skills"] == ["backend"]
    assert byname["Tuna Er"]["skills"] == ["qa"]

    tasks = client.post(f"/api/documents/{doc['id']}/extract", headers=LEAD).json()
    ann = [t for t in tasks if t["kind"] == "announcement"]
    assert len(ann) == 1 and ann[0]["status"] == "announcement" and ann[0]["suggested"] is None
    zehra = next(t for t in tasks if "Zehra" in t["source"]["quote"])
    assert zehra["unknown_mentions"] == ["Zehra Ak"] and zehra["confidence"] == 1

    r = client.post(f"/api/tasks/{ann[0]['id']}/decision", json={"action": "share"}, headers=LEAD)
    assert r.json()["status"] == "announced"

    added = client.post(f"/api/documents/{doc['id']}/people/import", json={"names": ["Zehra Ak", "Tuna Er"]}, headers=LEAD).json()
    assert len(added["added"]) == 2
    tasks = client.post(f"/api/documents/{doc['id']}/extract", headers=LEAD).json()
    zehra = next(t for t in tasks if "Zehra" in t["source"]["quote"])
    assert zehra["suggested"]["name"] == "Zehra Ak" and zehra["unknown_mentions"] == []
    assert any(t["status"] == "announced" for t in tasks)  # karar verilen duyuru korunur

    client.post(f"/api/documents/{doc['id']}/export", headers=LEAD)
    shared = client.get("/api/documents/shared", headers=AYSE).json()
    assert any(d["id"] == doc["id"] for d in shared)  # duyuru tüm ekiple paylaşıldı


def test_team_member_crud(client):
    u = client.post("/api/team/members", json={"name": "Deniz Mobil", "role": "iOS Geliştirici"}, headers=LEAD).json()
    assert set(u["skills"]) == {"ios", "mobile"}
    assert client.post("/api/team/members", json={"name": "X Y"}, headers=AYSE).status_code == 403
    u2 = client.patch(f"/api/team/members/{u['id']}", json={"skills": ["qa"]}, headers=LEAD).json()
    assert u2["skills"] == ["qa"]
    assert client.delete(f"/api/team/members/{u['id']}", headers=LEAD).status_code == 200
    assert client.delete("/api/team/members/ayse", headers=LEAD).status_code == 409


def test_list_and_delete_document(client):
    doc = client.post("/api/documents", data={"text": "Ayşe rapor servisini güncellemeli.", "title": "Silinecek"}, headers=LEAD).json()
    client.post(f"/api/documents/{doc['id']}/extract", headers=LEAD)
    docs = client.get("/api/documents", headers=LEAD).json()
    row = next(d for d in docs if d["id"] == doc["id"])
    assert row["counts"]["pending"] >= 1
    assert client.delete(f"/api/documents/{doc['id']}", headers=AYSE).status_code == 403
    r = client.delete(f"/api/documents/{doc['id']}", headers=LEAD).json()
    assert r["removed_tasks"] >= 1 and r["kept_tasks"] == 0
    assert client.get(f"/api/documents/{doc['id']}", headers=LEAD).status_code == 404
    # aktarılmış görevleri olan doküman silinince görevler kişide kalır
    mine_before = client.get("/api/tasks/mine", headers=AYSE).json()
    first = client.get("/api/documents", headers=LEAD).json()[-1]
    client.delete(f"/api/documents/{first['id']}", headers=LEAD)
    assert len(client.get("/api/tasks/mine", headers=AYSE).json()) == len(mine_before)


def test_task_source_view_and_titles(client):
    from app.services.titles import acceptable, rule_title

    assert rule_title("Emre, kredi kartı taksitlendirme servisindeki yanıt sürelerini düşürmek için önbellek katmanını devreye almalı.").startswith("Kredi kartı")
    assert acceptable("Taksitlendirme servisinde önbellek katmanı", "Emre, kredi kartı taksitlendirme servisindeki yanıt sürelerini düşürmek için önbellek katmanını devreye almalı.")
    assert not acceptable("Yeni mikroservis mimarisi kurulumu", "Önbellek katmanı devreye alınmalı.")

    mine = client.get("/api/tasks/mine", headers=AYSE).json()
    tid = mine[0]["id"]
    src = client.get(f"/api/tasks/{tid}/source", headers=AYSE).json()
    assert src["is_mine"] and src["sentence"] and src["title"]
    if src["document"]:
        assert src["document"]["text"][src["start"]:src["end"]].strip()
    other = {"X-User-Id": "can"}
    r = client.get(f"/api/tasks/{tid}/source", headers=other)
    assert r.status_code in (200, 403)  # paylaşılan dokümansa görebilir, değilse 403
