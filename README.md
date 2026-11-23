# Görevlendirme Asistanı

Kurum içinde çalışan (on-prem) bir görevlendirme asistanı. Takım lideri bir toplantı notu, analiz dokümanı ya da şartname yükler; sistem görevleri çıkarır, her biri için kişi önerir, lider onaylar. Personel de sohbet ekranından "bugün bana ne verildi?", "benimle ne paylaşıldı?" gibi sorular sorar.

**Veri kurum dışına çıkmaz:** model, veritabanı ve arayüz kurumun kendi sunucusunda çalışır; dış API çağrısı yoktur.

> Durum: v0.2 — arayüz, API, öneri ve onay akışı çalışıyor. Görev çıkarma için iki sağlayıcı var: kural tabanlı `mock` ve eğitimsiz `encoder` (embedding + HDBSCAN). Metin üreten model (kısa başlık, sohbet) sonraki aşama.

## Ekranlar

| Ekran | Yol | Kimin için |
|---|---|---|
| Ana ekran (sohbet) | `/` | Herkes |
| Sohbet | `/c/:id` | Herkes |
| Doküman yükle | `/yukle` | Takım lideri |
| Görevleri incele ve onayla | `/dokuman/:id` | Lider karar verir, personel okur |
| Ekip yükü ve model isabeti | `/ekip` | Takım lideri |

Geliştirme aşamasında kullanıcı, kenar menünün altındaki listeden değiştirilir (`Ayşe Kaya` personel, `Burak Şen` takım lideri). Tüm demo kişi ve görevleri kurgusaldır.

## Arayüz kararları (araştırma dayanağı)

- **Öneri + onay, otomatik atama yok:** Amershi vd., *Guidelines for Human-AI Interaction* (CHI 2019).
- **Düşük güvenli görevlerde lider önce kendi seçimini yapar** (bilişsel zorlama): Buçinca vd., *To Trust or to Think* (CSCW 2021). Aşırı güveni azaltır; sadece düşük güvenli görevlere uygulanır ki akış yavaşlamasın.
- **Güven 3 kademeli sözel etiketle gösterilir**, yüzdeyle değil.
- **Her görev dokümandaki cümlesine bağlı** (kaynak gösterimi); "Kaynak §n" ile vurgulanır.
- **Model isabeti paneli**: liderin güvenini kalibre etmesi için geçmiş öneri isabeti gösterilir.

## Hızlı başlangıç

### Docker (kurum sunucusu)

```bash
cp .env.example .env      # kurum adı, renk, logo
docker compose up -d --build
# http://localhost:8000
```

### Geliştirme

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (ayrı terminal)
cd frontend
npm install
npm run dev               # http://localhost:5173  (/api istekleri 8000'e yönlenir)
```

Testler: `cd backend && pytest`

## Encoder modu (eğitimsiz, CPU)

Önceden eğitilmiş, **dondurulmuş** bir cümle-embedding modeli kullanılır; model eğitilmez.

1. **Görev tespiti:** her cümle, örnek görev / görev olmayan cümlelere (`app/ml/prototypes.py`) benzerlik farkıyla puanlanır → `detect_score` (0–1).
2. **Alan etiketi:** etiket açıklamalarına benzerlik (backend, mobil, güvenlik…).
3. **Kişi önerisi:** uzmanlık + geçmiş iş + **en benzer geçmiş işe anlamsal benzerlik** + yük.
4. **İş alanları:** yeni görevler ekibin geçmiş işleriyle birlikte **HDBSCAN** ile kümelenir, kümeler c-TF-IDF ile adlandırılır.
5. **Aykırılar:** hiçbir kümeye girmeyen görev "alışılmadık" sayılır, güveni bir kademe düşer → lider önce kendi seçimini yapar. Az veride HDBSCAN yalnız noktaları kümeye çekebildiği için en-yakın-komşu benzerliğine dayalı robust z-skorla tamamlanır.

```powershell
cd backend
pip install -r requirements-ml.txt        # sentence-transformers (ilk çalıştırmada model iner)
python scripts/evaluate.py --verbose      # mock ile encoder'ı karşılaştır
# .env: GA_LLM_PROVIDER=encoder
```

Model seçimi: `GA_EMBED_MODEL` ile değişir. `gte-small` gibi modeller ağırlıklı İngilizce eğitildiği için Türkçede çok dilli modellerle (ör. `intfloat/multilingual-e5-small`, `-base`) karşılaştırılmalı; `scripts/evaluate.py` bunun için. Değerlendirme seti şu an küçük ve örnek dokümanlardan oluşuyor; gerçek dokümanlar ve etiketler eklendikçe anlamlılaşır.

## Modeli iyileştirme

Veri toplama, etiketleme ve aktif öğrenme döngüsü: [`docs/VERI_TOPLAMA.md`](docs/VERI_TOPLAMA.md)

- **Veri etiketleme ekranı** (`/etiketle`, lider): doküman yükle → KVKK anonimleştirme → her cümleyi
  görev / değil / belirsiz işaretle → eğitim ya da (kör) test verisine kaydet.
- **"Model emin olamadı" paneli:** eşiğin biraz altındaki cümleler lidere sorulur.
- **Ret nedeni:** "görev değil" eğitim etiketi olur; "görev ama şimdi değil" olmaz.
- `scripts/train_probe.py` dosyadaki etiketleri ve uygulamadaki kararları birlikte kullanır;
  test dokümanlarına ait her şeyi otomatik dışarıda bırakır.

## Mimari

```
frontend/  React + TypeScript + Vite
backend/
  app/
    llm/            sağlayıcı arayüzü (base.py), mock, encoder
    ml/             embedding, prototipler, HDBSCAN kümeleme
    services/
      extraction.py   doküman → görev
      assignment.py   açıklanabilir kişi önerisi (uzmanlık, geçmiş iş, yük)
      assistant.py    sohbet: görev/doküman soruları veritabanından, kaynaklı
      load.py         ekip yükü
      documents.py    PDF/DOCX/TXT metin çıkarma (yerel)
    routers/        REST uçları
    deps.py         kimlik (şimdilik X-User-Id; kurumda LDAP/SSO)
  tests/
```

### LLM sağlayıcısı eklemek

1. `backend/app/llm/` altında `LLMProvider` arayüzünü (`extract_tasks`, `chat`) uygulayan bir sınıf yazın.
2. `backend/app/llm/__init__.py` içindeki `get_provider()` fonksiyonuna dal ekleyin.
3. `.env` içinde `GA_LLM_PROVIDER=<ad>` yapın.

Kişi önerisi bilinçli olarak LLM'den ayrı tutuldu: lider her önerinin gerekçesini görebilsin ve ağırlıklar kurum verisiyle ayarlanabilsin.

## Yol haritası

- [ ] LLM mimarisi ve yerel model sağlayıcısı
- [ ] Kurum kimlik doğrulaması (LDAP / Active Directory / OIDC)
- [ ] Jira / Azure DevOps entegrasyonu (şu an aktarma uygulama içinde)
- [ ] Rol bazlı yetki ve doküman erişim kuralları
- [ ] Önerinin yük bilgisini karar anında yeniden hesaplama
- [ ] PostgreSQL ve Alembic göçleri
