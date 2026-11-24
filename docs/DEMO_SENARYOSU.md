# 90 saniyelik demo videosu

Hazırlık: `python scripts/demo_data.py` → backend + frontend açık → Ollama açık (decoder için).
Herkese açık videoda kurum logosu yerine nötr marka kullanın (`.env`: `GA_ORG_NAME`, `GA_ORG_LOGO_URL`).

| Süre | Ekran | Ne gösterilir | Söylenecek (alt yazı) |
|---|---|---|---|
| 0–8 sn | Ekip panosu (Burak) | Açık iş, geciken, aşırı yüklü kişi | "Kurumlar dokümanlarını dış modellere veremiyor. Bu asistan tamamen kurum içinde, CPU'da çalışıyor." |
| 8–30 sn | Doküman yükle → `samples/demo/canli_demo_notu.txt` yapıştır → Görevleri çıkar | Cümleler vurgulanıyor, kişi + **neden** | "Notu yapıştırıyorum; görev cümlelerini buluyor, kime verileceğini ve nedenini gösteriyor." |
| 30–40 sn | "Deniz Aksoy ekipte kayıtlı değil" → Ekibe ekle | Öneri Deniz'e dönüyor | "Dokümanda geçen yeni kişiyi tanıyor, tek tıkla ekleniyor." |
| 40–50 sn | Düşük güvenli görev → lider önce kendi seçimini yapıyor → Onayla → Aktar | Bilişsel zorlama kutusu | "Emin olmadığında lideri yönlendirmiyor; önce liderin kararını istiyor." |
| 50–65 sn | Toplantılar → Sprint 19 Planlama → Rapor | Özet, görev önerileri, "kendisi üstlendi" | "Toplantıda 'ben bakarım' diyen kişiye görev öneriliyor; rapor dökümle karşılaştırılıyor." |
| 65–85 sn | Ayşe'ye geç → "Bugün bana verilen görevler ne?" → Görevi aç | Kart, dokümanda vurgulu cümle | "Personel görevini, dokümandaki cümlesiyle ve neden kendisine verildiğiyle görüyor." |
| 85–90 sn | Kapanış | Mimari şeması (README) | "Encoder anlar, decoder yalnızca kaynaklı yazar. Kör test sonucu: …" |

Çekmeden önce kontrol: geciken iş 1 tane mi, bozuk/uyduran rapor satırı var mı, ekranda gerçek kişi verisi var mı.
