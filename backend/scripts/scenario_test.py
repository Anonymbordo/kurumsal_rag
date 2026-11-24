"""Senaryo testi: dokümandan ve toplantıdan görevlendirme, uçtan uca.

    python scripts/scenario_test.py

Kör test DEĞİLDİR: senaryoyu sistemi geliştiren yazdı. Amacı her davranışı tek tek
kontrol etmek (regresyon testi) ve kör testte ölçülmeyen bir şeyi ölçmek:
görev DOĞRU KİŞİYE gidiyor mu?

Geçici bir veritabanında demo ekibiyle (seed) çalışır; gerçek veritabanına dokunmaz.
Ekip: Ayşe (backend), Mert (iOS), Selin (QA), Can (DevOps, sprinti %95 dolu), Elif (backend · güvenlik).
"""
import os
import sys
import tempfile
import time

_tmp = tempfile.mkdtemp()
os.environ["GA_DATABASE_URL"] = f"sqlite:///{_tmp}/senaryo.db"
os.environ["GA_DATA_DIR"] = f"{_tmp}/data"
os.environ.setdefault("GA_DECODER", "none")  # rapor/başlık üretimi bu testin konusu değil
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TASK, NOT, ANN = "görev", "değil", "duyuru"

# (cümle, beklenen tür, kabul edilen kişiler, kontrol edilen davranış)
DOC_TITLE = "Sprint 20 Planlama Notu"
DOC = [
    ("Katılımcılar: Burak Şen (Takım lideri), Ayşe Kaya (Backend), Mert Demir (Mobil iOS), Selin Arslan (QA), "
     "Can Yıldız (DevOps), Elif Tunç (Backend · Güvenlik), Deniz Aksoy (Frontend Geliştirici)", NOT, None, "katılımcı satırı"),
    ("Geçen sprintte hesap özeti servisine önbellek eklendi ve yanıt süresi yarıya indi.", NOT, None, "bitmiş iş"),
    ("Ayşe, fatura dışa aktarma kuyruğuna sayfalama eklemeli.", TASK, {"ayse"}, "adı geçen kişi"),
    ("iOS uygulamasında bildirim izni reddedildiğinde ekran donuyor, bu akışın düzeltilmesi gerekiyor.", TASK, {"mert"}, "uzmanlık: iOS"),
    ("Yeni sürüm için regresyon testlerinin güncellenmesi lazım.", TASK, {"selin"}, "uzmanlık: QA"),
    ("Ödeme servisinin loglarında maskelenmemiş kart numaraları görünüyor, log maskeleme kuralı güncellenmeli.", TASK, {"elif"}, "uzmanlık: güvenlik"),
    ("Staging ortamındaki disk doluluğu yüzde doksanı geçti, temizlik ve alarm kuralı gerekiyor.", TASK, {"can", "elif", "ayse"}, "uzmanlık: DevOps, kişi aşırı yüklü"),
    ("Deniz, sepet ekranındaki kupon alanı hizalamasına bir bakabilirse iyi olur.", TASK, "kayıtsız:Deniz Aksoy", "kayıtsız kişi + dolaylı istek"),
    ("Not: Cuma günü saat 14:00'te bilgi güvenliği eğitimi var.", ANN, None, "Not: bilgilendirmesi"),
    ("Müşteri şikayetleri bu hafta yüzde on beş azaldı.", NOT, None, "metrik"),
    ("Mert iOS oturum yenileme hatasını dün kapattı.", NOT, None, "bitmiş iş (kişi adıyla)"),
    ("API dokümantasyonunun yeni uç noktalarla güncellenmesi gerekiyor.", TASK, {"ayse", "elif"}, "uzmanlık: backend"),
    ("Selin, yük testi sonuçlarını perşembeye kadar paylaşabilir misin?", TASK, {"selin"}, "soru biçiminde istek"),
    ("Bir sonraki planlama toplantısı 9 Aralık Salı saat 10:30'da.", NOT, None, "toplantı tarihi"),
    ("Kart ekleme ekranındaki Face ID akışı iOS 18'de iki kez tetikleniyor, incelenmesi lazım.", TASK, {"mert"}, "uzmanlık: iOS, dolaylı"),
]

MEETING_TITLE = "İade Süreci Toplantısı (toplantı dökümü)"
MEETING = [
    ("Burak Şen", "Bugünkü konumuz iade süreci, kısaca durumu konuşalım.", NOT, None, "açılış"),
    ("Ayşe Kaya", "İade servisinde zaman aşımı oluyor, bunu ben bu hafta düzeltirim.", TASK, {"ayse"}, "konuşan üstlendi"),
    ("Can Yıldız", "Yeni worker için staging'de kaynak ayırmamız gerekecek, onu ben ayarlarım.", TASK, {"can"}, "konuşan üstlendi (yüklü kişi)"),
    ("Mert Demir", "iOS'ta iade ekranının tasarımı onaylandı.", NOT, None, "durum"),
    ("Burak Şen", "Elif, iade dekontlarında kimlik numaraları maskelenmeli.", TASK, {"elif"}, "lider birine iş veriyor"),
    ("Selin Arslan", "Mevcut testlerin hepsi geçti, sorun görmedik.", NOT, None, "durum"),
    ("Selin Arslan", "İade akışının uçtan uca test senaryolarını ben hazırlarım.", TASK, {"selin"}, "konuşan üstlendi"),
    ("Mert Demir", "Oturum hatası iOS sürüm notlarına eklendi.", NOT, None, "bitmiş iş ('sürüm' ismi fiil sanılmamalı)"),
]


def main() -> None:
    from sqlalchemy import select

    from app.config import get_settings
    from app.db import Base, SessionLocal, add_missing_columns, engine
    from app.llm import get_provider
    from app.models import Document, Task, User
    from app.seed import seed
    from app.services.extraction import extract_for_document
    from app.services.people import strip_speaker

    Base.metadata.create_all(engine)
    add_missing_columns(engine)
    s = get_settings()
    print(f"Sağlayıcı: {s.llm_provider} · embedding: {s.embed_model}")
    print("Senaryo testi (kör test değildir) — geçici veritabanı, demo ekibi\n")

    cases = [("doküman", q, kind, who, why) for q, kind, who, why in DOC]
    cases += [("toplantı", f"{sp}: {q}", kind, who, why) for sp, q, kind, who, why in MEETING]

    with SessionLocal() as db:
        seed(db)
        names = {u.id: u.name for u in db.scalars(select(User))}
        get_provider()  # model yükleme süresini ölçüme katma
        t0 = time.time()
        d1 = Document(title=DOC_TITLE, doc_type="meeting", text=DOC_TITLE + "\n" + "\n".join(c[0] for c in DOC),
                      uploaded_by="burak", team_id="mb")
        d2 = Document(title=MEETING_TITLE, doc_type="meeting",
                      text=MEETING_TITLE + "\n" + "\n".join(f"{sp}: {q}" for sp, q, *_ in MEETING),
                      uploaded_by="burak", team_id="mb")
        db.add_all([d1, d2])
        db.flush()
        tasks = extract_for_document(db, d1) + extract_for_document(db, d2)
        db.commit()
        took = time.time() - t0

        def find(sentence: str) -> Task | None:
            core = strip_speaker(sentence).rstrip(".?!")[:60]
            for t in tasks:
                if core and core in (t.source_quote or ""):
                    return t
            return None

        tp = fp = fn = 0
        assign_ok = assign_n = 0
        rows = []
        for src, sentence, kind, who, why in cases:
            t = find(sentence)
            if t is None or t.status == "dismissed":
                got = NOT
            elif t.kind == "announcement":
                got = ANN
            else:
                got = TASK  # aday (emin değil) da lidere gösterildiği için görev sayılır
            ok_kind = got == kind or (kind == ANN and got == NOT) or (kind == NOT and got == ANN)
            note = ""
            if kind == TASK and got == TASK:
                tp += 1
            elif kind == TASK:
                fn += 1
            elif got == TASK:
                fp += 1

            ok_who = None
            if kind == TASK and got == TASK and t is not None:
                sug = t.suggested_assignee_id
                if isinstance(who, str) and who.startswith("kayıtsız:"):
                    person = who.split(":", 1)[1]
                    ok_who = person in (t.unknown_mentions or []) and t.confidence == 1
                    note = f"uyarı: {', '.join(t.unknown_mentions or []) or 'YOK'} · güven {t.confidence}"
                else:
                    ok_who = sug in who
                    alt = names.get(t.alt_assignee_id or "", "")
                    note = f"önerilen: {names.get(sug or '', '—')}" + (f" (alternatif: {alt})" if alt else "")
                    if t.status == "candidate":
                        note += " · aday"
                assign_n += 1
                assign_ok += bool(ok_who)
            elif got == TASK and t is not None:
                note = f"önerilen: {names.get(t.suggested_assignee_id or '', '—')}"

            mark = "✔" if ok_kind and ok_who is not False else "✘"
            rows.append((mark, src, why, f"beklenen {kind} / bulunan {got}", note, sentence))

    for mark, src, why, kinds, note, sentence in rows:
        print(f" {mark} [{src:8}] {why:42} {kinds:30} {note}")
        if mark == "✘":
            print(f"      ↳ {strip_speaker(sentence)[:110]}")

    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    passed = sum(1 for r_ in rows if r_[0] == "✔")
    print("\n== Özet")
    print(f"  Görev tespiti     : kesinlik {p:.2f} · duyarlılık {r:.2f} · F1 {f1:.2f}  ({tp + fn} görev)")
    print(f"  Kişi önerisi      : {assign_ok}/{assign_n} doğru (tespit edilen görevlerde)")
    print(f"  Davranış kontrolü : {passed}/{len(rows)} geçti")
    print(f"  Süre              : {took:.1f} sn (2 doküman, model yükleme hariç)")


if __name__ == "__main__":
    main()
