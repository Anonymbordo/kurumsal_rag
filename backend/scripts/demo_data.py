"""Video / sunum için temiz demo verisi.

    python scripts/demo_data.py            # mevcut veritabanını yedekler, sıfırdan kurar
    python scripts/demo_data.py --no-backup

Ne kurar:
  - Ekip ve geçmiş işler (seed)
  - "Sprint 18 Planlama" dokümanı: lider kararları verilmiş, iş takibine aktarılmış görevler
    (teslimler önümüzdeki iki haftaya yayılmış; 1 gecikmiş; liderin kişi değiştirdiği 3 karar).
    Bu görevler elle yazılmıştır: geçmişi temsil eder, modelin çıktısı değildir.
  - "Sprint 19 Planlama" toplantısı: dökümü hazır, modelin görev önerileri lider kararı bekliyor.
    Döküm gerçek görev çıkarma hattından geçer (canlı demo: lider onayı burada gösterilir).

Videoda canlı yapıştırılacak doküman: samples/demo/canli_demo_notu.txt

UYARI: Panodaki "öneri isabeti" bu betikle kurulan kurgusal kararlardan hesaplanır.
Modelin gerçek başarısı olarak SUNMAYIN; gerçek sayı kör test setinden gelir (scripts/evaluate.py).
"""
import argparse
import os
import shutil
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import get_settings  # noqa: E402

HISTORY_DOC = """Sprint 18 Planlama Toplantısı
Katılımcılar: Burak Şen (Takım lideri), Ayşe Kaya (Backend), Mert Demir (Mobil iOS), Selin Arslan (QA), Can Yıldız (DevOps), Elif Tunç (Backend · Güvenlik)
Geçen sprintte kart ekleme akışı sorunsuz canlıya çıktı.
Hesap özeti servisinin yanıt süresi ortalama 900 milisaniyeye çıktı, önbellek katmanı eklenmeli.
iOS uygulamasında Face ID ile girişte zaman zaman oturum düşüyor, bu hata düzeltilmeli.
Para transferi akışı için uçtan uca test senaryoları yazılmalı.
Staging ortamı için otomatik ölçekleme kuralları tanımlanmalı.
Denetim loglarında maskelenmemiş IBAN görünüyor, log maskeleme kuralı güncellenmeli.
Kampanya ekranının tasarımı onaylandı.
Mobil uygulamada sürüm notları ekranı yenilenmeli.
Ödeme servisi için hata durumunda tekrar deneme mekanizması eklenmeli.
Test ortamının veritabanı yedeklemesi otomatikleştirilmeli.
"""

# (cümle, kısa başlık, etiketler, öneri, atanan, güven, durum, teslim için bugünden gün)
HISTORY = [
    ("Hesap özeti servisinin yanıt süresi ortalama 900 milisaniyeye çıktı, önbellek katmanı eklenmeli.",
     "Hesap özeti servisine önbellek katmanı", ["backend"], "ayse", "ayse", 3, "exported", 3),
    ("iOS uygulamasında Face ID ile girişte zaman zaman oturum düşüyor, bu hata düzeltilmeli.",
     "iOS Face ID girişinde oturum düşmesi", ["mobile", "ios"], "mert", "mert", 3, "exported", 5),
    ("Para transferi akışı için uçtan uca test senaryoları yazılmalı.",
     "Para transferi uçtan uca test senaryoları", ["qa"], "selin", "selin", 3, "exported", 8),
    ("Staging ortamı için otomatik ölçekleme kuralları tanımlanmalı.",
     "Staging otomatik ölçekleme kuralları", ["devops"], "can", "can", 3, "exported", -1),
    ("Denetim loglarında maskelenmemiş IBAN görünüyor, log maskeleme kuralı güncellenmeli.",
     "Denetim loglarında IBAN maskeleme", ["security"], "ayse", "elif", 2, "exported", 6),
    ("Mobil uygulamada sürüm notları ekranı yenilenmeli.",
     "Sürüm notları ekranının yenilenmesi", ["mobile"], "mert", "mert", 2, "exported", 11),
    ("Ödeme servisi için hata durumunda tekrar deneme mekanizması eklenmeli.",
     "Ödeme servisine tekrar deneme mekanizması", ["backend"], "ayse", "elif", 2, "exported", 9),
    ("Test ortamının veritabanı yedeklemesi otomatikleştirilmeli.",
     "Test ortamı veritabanı yedeklemesinin otomasyonu", ["devops"], "can", "ayse", 1, "done", -3),
]

MEETING_TITLE = "Sprint 19 Planlama"
# (konuşmacı id, toplantı başından saniye, söz)
TRANSCRIPT = [
    ("burak", 5, "Herkese günaydın, sprint 19 planlamasına başlayalım. Önce geçen sprintin kısa bir özetini geçelim."),
    ("ayse", 22, "Hesap özeti servisine önbellek eklendi, yanıt süresi 200 milisaniyenin altına indi."),
    ("mert", 41, "iOS tarafında Face ID oturum hatası kapandı, mağaza incelemesinden de geçtik."),
    ("burak", 63, "Güzel. Bu sprintin ana konusu fatura dışa aktarma ekranındaki zaman aşımı. Müşteri şikayetleri arttı."),
    ("ayse", 84, "Büyük raporlarda sorgu çok uzun sürüyor. Dışa aktarmayı asenkron kuyruğa taşımayı ben üstleniyorum, perşembeye kadar ilk sürümü çıkarırım."),
    ("burak", 112, "Tamam. Selin, kuyruk yapısı gelince yük testini sen hazırlayabilir misin?"),
    ("selin", 124, "Olur, on bin satırlık örnek veriyle yük testi senaryosunu ben hazırlarım."),
    ("can", 140, "Kuyruk için staging ortamında yeni bir worker servisi açmamız gerekecek, onu ben ayarlarım."),
    ("burak", 161, "Elif, dışa aktarılan dosyalarda kişisel veri var mı, kontrol etmemiz lazım."),
    ("elif", 175, "Var, kimlik numaraları maskelenmeden çıkıyor. Dışa aktarma dosyalarında kimlik numaralarını maskeleyen filtreyi ben yazacağım."),
    ("mert", 203, "Bir de iOS'ta bildirim izni reddedildiğinde kullanıcı ayarlara yönlenmiyor, bazı cihazlarda ekran takılıyor."),
    ("burak", 221, "Mert, o akışı bu sprintte düzeltebilir misin?"),
    ("mert", 229, "Evet, bildirim izni akışına bu hafta bakarım."),
    ("burak", 246, "Not olarak geçelim: cuma günü şirket genelinde bilgi güvenliği eğitimi var, takvimlerinizi ona göre ayarlayın."),
    ("selin", 268, "Regresyon testleri şu an yaklaşık iki saat sürüyor, sürüm öncesi sıkıntı yaratıyor."),
    ("can", 285, "Testleri paralel çalıştırırsak süre yarıya iner, CI hattında paralel çalıştırmayı ben açarım."),
    ("burak", 306, "Tamam, teşekkürler. Sprint sonunda demo toplantısı yapacağız, tarihi ayrıca paylaşırım."),
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    url = get_settings().database_url
    if not url.startswith("sqlite:///"):
        sys.exit("Bu betik yalnızca SQLite geliştirme veritabanında çalışır.")
    path = url.removeprefix("sqlite:///")
    if os.path.exists(path):
        if not args.no_backup:
            bak = f"{path}.yedek-{date.today():%Y%m%d}"
            shutil.copy(path, bak)
            print(f"Yedek: {bak}")
        for ext in ("", "-wal", "-shm"):
            if os.path.exists(path + ext):
                os.remove(path + ext)

    from sqlalchemy import select

    from app.db import Base, SessionLocal, add_missing_columns, engine
    from app.models import Document, Meeting, Task, User
    from app.seed import seed
    from app.services.meetings import finalize, merge_segments
    from app.services.titles import fill_short_titles, rule_title
    from app.timeutil import utcnow

    Base.metadata.create_all(engine)
    add_missing_columns(engine)
    now, today = utcnow(), date.today()
    with SessionLocal() as db:
        seed(db)
        users = {u.id: u for u in db.scalars(select(User))}

        # 1) Geçmiş: kararları verilmiş, aktarılmış görevler
        doc = Document(title="Sprint 18 Planlama Toplantısı", doc_type="meeting", sprint="Sprint 18", text=HISTORY_DOC,
                       uploaded_by="burak", team_id="mb", shared_with=sorted({h[4] for h in HISTORY}),
                       created_at=now - timedelta(days=6))
        db.add(doc)
        db.flush()
        last_no = 432
        for i, (q, short, tags, sug, who, conf, status, due) in enumerate(HISTORY, 1):
            start = HISTORY_DOC.index(q)
            reasons = [f"Uzmanlık alanı eşleşiyor: {', '.join(tags)}"]
            if sug != who:
                reasons.append(f"Model {users[sug].name} önermişti; lider {users[who].name} olarak değiştirdi")
            db.add(Task(
                key=f"MB-{last_no + i}", document_id=doc.id, team_id="mb", order_no=i,
                title=rule_title(q), short_title=short, tags=tags, est_days=2, source_ref=f"¶{HISTORY_DOC[:start].count(chr(10)) + 1}",
                source_quote=q, source_start=start, source_end=start + len(q),
                suggested_assignee_id=sug, assignee_id=who, confidence=conf, reasons=reasons,
                status=status, decided_by="burak", decided_at=now - timedelta(days=6),
                assigned_by="burak", assigned_at=now - timedelta(days=6) if due > 0 else now - timedelta(days=9),
                due_date=today + timedelta(days=due),
            ))
        db.commit()

        # 2) Bitmiş toplantı: döküm hazır, görev önerileri lider kararı bekliyor
        started = now - timedelta(days=1, hours=2)
        m = Meeting(team_id="mb", title=MEETING_TITLE, room="ga-demo-sprint19", created_by="burak",
                    participants=["burak", "ayse", "mert", "selin", "can", "elif"], status="processing",
                    started_at=started, ended_at=started + timedelta(minutes=18))
        db.add(m)
        db.flush()
        segs = []
        for uid, t, text in TRANSCRIPT:
            segs.append({"user_id": uid, "speaker": users[uid].name, "start": float(t),
                         "end": float(t) + max(4.0, len(text.split()) * 0.45), "text": text})
        m.transcript = merge_segments(segs)
        db.commit()
        print("Toplantı dökümü işleniyor (görev çıkarma + rapor; decoder açıksa 1-2 dk sürebilir)…")
        tasks = finalize(db, m)
        print(f"  {len(tasks)} öneri lider kararı bekliyor.")

    n = fill_short_titles()
    print(f"Kısa başlık: {n} görev" if n else "Kısa başlık: decoder kapalı, kural başlıkları kullanılacak")
    print("\nHazır. Backend'i başlatın; Burak Şen (lider) ve Ayşe Kaya (personel) ile gezin.")
    print("Canlı demo için yapıştırılacak metin: samples/demo/canli_demo_notu.txt")


if __name__ == "__main__":
    main()
