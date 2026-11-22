"""Demo verisi. Tüm kişi ve görevler kurgusaldır."""
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Document, Group, Task, Team, User
from .timeutil import utcnow

SPRINT_NOTE = """Mobil Bankacılık v3.2 — Sprint 14 Planlama Notu
§1 Hedef. Bu sprintin ana hedefi, transfer akışındaki müşteri şikayetlerini azaltmak ve denetim bulgularını kapatmak.
§2 Limit kontrolü. Günlük transfer limiti kontrolü şu an üç farklı serviste yapılıyor. Limit kontrolü tek bir servise taşınmalı ve API yeniden yazılmalı. Eski uç nokta geçiş süresince paralel çalışacak.
§3 Giriş sorunu. Müşteri hizmetleri kayıtlarına göre iOS uygulamasında Face ID ile girişten birkaç dakika sonra oturum düşüyor. Android tarafında sorun görülmedi.
§4 Test. Bu değişiklikler canlıya çıkmadan önce transfer akışı uçtan uca regresyon testinden geçmeli.
§5 Denetim notu. İç denetim ekibine göre işlem loglarında TCKN ve IBAN açık metin tutuluyor, loglar maskelenmeli.
§6 Kampanya yükü. Yılbaşı kampanyası öncesinde staging ortamına otomatik ölçekleme kuralı eklenmeli. Kural daha sonra canlıya taşınacak.
§7 Bilgilendirme. Müşteri hizmetleri ekibi için yeni transfer kurallarını anlatan kısa bir bilgilendirme metni hazırlanmalı.
"""

Q1 = "Limit kontrolü tek servise taşınmalı ve API yeniden yazılmalı"
Q2 = "Staging ortamı için otomatik ölçekleme kuralı yazılmalı"
PRE_NOTE = f"""Sprint 14 Ön Planlama Notu
§1 Limit servisi. {Q1}; ayrıntılı mimari taslağı Elif paylaşacak.
§2 Altyapı. {Q2}; kampanya öncesi denenmesi gerekiyor.
"""


def seed(db: Session) -> None:
    if db.scalar(select(User).limit(1)) is not None:
        return
    now = utcnow()
    today = date.today()

    db.add(Team(id="mb", name="Mobil Bankacılık", key_prefix="MB"))
    people = [
        User(id="burak", name="Burak Şen", role="Takım lideri", team_id="mb", is_lead=True, skills=[], base_load_days=0),
        User(id="ayse", name="Ayşe Kaya", role="Backend", team_id="mb", skills=["backend"], base_load_days=2.0),
        User(id="mert", name="Mert Demir", role="Mobil (iOS)", team_id="mb", skills=["mobile", "ios"], base_load_days=4.5),
        User(id="selin", name="Selin Arslan", role="QA", team_id="mb", skills=["qa"], base_load_days=7.0),
        User(id="can", name="Can Yıldız", role="DevOps", team_id="mb", skills=["devops"], base_load_days=9.5),
        User(id="elif", name="Elif Tunç", role="Backend · Güvenlik", team_id="mb", skills=["backend", "security"], base_load_days=4.0),
    ]
    db.add_all(people)
    db.flush()

    others = [f"ext-{i}" for i in range(30)]
    db.add_all(
        [
            Group(id="g-mb", name="Mobil Bankacılık", short="MB", color="#DCE3F0", member_ids=[p.id for p in people]),
            Group(id="g-bt", name="Backend Topluluğu", short="BT", color="#E2EFE7", member_ids=["ayse", "elif", *others[:21]]),
            Group(id="g-mk", name="Mimari Kurul", short="MK", color="#F3E8D9", member_ids=["ayse", "burak", *others[21:28]]),
        ]
    )

    # Geçmiş (tamamlanmış) görevler: kişi önerisi "benzer iş" sinyalini buradan alır.
    def done(key, title, tags, who, suggested, conf, days_ago):
        return Task(
            key=key, team_id="mb", title=title, tags=tags, est_days=2, status="done",
            assignee_id=who, suggested_assignee_id=suggested, confidence=conf,
            decided_by="burak", decided_at=now - timedelta(days=days_ago + 2),
            assigned_by="burak", assigned_at=now - timedelta(days=days_ago + 2),
            due_date=today - timedelta(days=days_ago),
        )

    db.add_all(
        [
            done("MB-377", "Kart ekleme hatası", ["backend"], "ayse", "ayse", 3, 40),
            done("MB-381", "Hesap özeti API’si", ["backend"], "ayse", "ayse", 3, 34),
            done("MB-390", "Fatura ödeme servisi", ["backend"], "ayse", "ayse", 3, 26),
            done("MB-398", "Ödeme bildirimi servisi", ["backend"], "ayse", "ayse", 3, 12),
            done("MB-383", "iOS bildirim izinleri", ["mobile", "ios"], "mert", "mert", 3, 30),
            done("MB-392", "iOS oturum yenileme hatası", ["mobile", "ios"], "mert", "mert", 3, 15),
            done("MB-385", "Kart akışı test seti", ["qa"], "selin", "selin", 2, 28),
            done("MB-394", "Transfer akışı ilk test seti", ["qa"], "selin", "selin", 2, 18),
            done("MB-388", "Log saklama politikası", ["security"], "elif", "ayse", 1, 25),
            done("MB-396", "Şifre politikası güncellemesi", ["security"], "elif", "can", 1, 14),
            done("MB-389", "CI hattı hızlandırma", ["devops"], "can", "can", 2, 22),
            done("MB-391", "Test ortamı yedekleme", ["devops"], "ayse", "can", 2, 20),
        ]
    )

    pre = Document(
        title="Sprint 14 Ön Planlama Notu", doc_type="meeting", sprint="Sprint 14", text=PRE_NOTE,
        uploaded_by="burak", team_id="mb", shared_with=["ayse"], created_at=now - timedelta(days=5),
    )
    db.add_all(
        [
            Document(
                title="Sprint 14 Planlama Notu", doc_type="meeting", sprint="Sprint 14", text=SPRINT_NOTE,
                uploaded_by="burak", team_id="mb", shared_with=[], created_at=now - timedelta(hours=3),
            ),
            pre,
            Document(
                title="Limit Servisi — Mimari Taslak v2", doc_type="analysis", sprint="Sprint 14",
                text="Limit servisi için önerilen mimari: tek servis, olay tabanlı limit güncellemesi, eski uç nokta için geçiş katmanı.",
                uploaded_by="elif", team_id="mb", shared_with=["ayse"], related_task_key="MB-412",
                created_at=now - timedelta(hours=18),
            ),
        ]
    )
    db.flush()

    # Ayşe'nin aktif görevleri (sohbet ekranındaki örnek)
    db.add_all(
        [
            Task(
                key="MB-412", team_id="mb", title="Limit kontrolünü tek servise taşı, API’yi yeniden yaz",
                tags=["backend"], est_days=3, status="exported", assignee_id="ayse",
                suggested_assignee_id="ayse", confidence=3, decided_by="burak",
                decided_at=now - timedelta(days=5), assigned_by="burak", assigned_at=now - timedelta(days=5),
                due_date=today + timedelta(days=13), source_ref="§1", document_id=pre.id,
                source_quote=Q1, source_start=PRE_NOTE.index(Q1), source_end=PRE_NOTE.index(Q1) + len(Q1),
                reasons=["Uzmanlık alanı eşleşiyor: backend", "Bu alanda 4 benzer görevi tamamladı"],
            ),
            Task(
                key="MB-418", team_id="mb", title="Staging için otomatik ölçekleme kuralı",
                tags=["devops"], est_days=1, status="exported", assignee_id="ayse",
                suggested_assignee_id="can", confidence=2, decided_by="burak",
                decided_at=now - timedelta(hours=20), assigned_by="burak", assigned_at=now - timedelta(hours=20),
                due_date=today + timedelta(days=4), source_ref="§2", document_id=pre.id,
                source_quote=Q2, source_start=PRE_NOTE.index(Q2), source_end=PRE_NOTE.index(Q2) + len(Q2),
                reasons=["Uzmanlık alanı eşleşiyor: DevOps", "Bu alanda 1 benzer görevi tamamladı"],
            ),
        ]
    )

    db.commit()
