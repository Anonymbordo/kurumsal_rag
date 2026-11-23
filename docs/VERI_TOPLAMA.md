# Veri toplama ve modeli iyileştirme rehberi

Görev tespiti modeli (e5 + lineer probe) veriyle iyileşir. Bu rehber üç kaynağı ve
modelin kendini iyileştirme döngüsünü anlatır.

**Altın kural:** Test verisi eğitime ve ayar seçimine **asla** girmez. Test dokümanını
etiketlerken modelin tahminine bakma (etiketleme ekranı test için tahmini zaten gizler).

| Klasör | Ne | Kim kullanır |
|---|---|---|
| `samples/train/*.tsv` | Etiketli cümleler (`etiket<TAB>cümle`) | `train_probe.py` (eğitim) |
| `samples/eval/` | Doğrulama dokümanları | `train_probe.py` (çapraz doğrulama) |
| `samples/test/` + `gold.json` | Test dokümanları | yalnızca `evaluate.py` (ölçüm) |
| `backend/gorev_asistani.db` | Liderin onay/ret kararları | `train_probe.py` (aktif öğrenme) |

---

## 1. Kısa vade: Gemini / ChatGPT ile veri

### a) Eğitim cümleleri → `samples/train/gemini.tsv`

Aşağıdaki promptu ver, çıktıyı **olduğu gibi** `samples/train/gemini.tsv` dosyasına kaydet
(UTF-8). Dosya adı `.tsv` ile bittiği sürece eğitim betiği otomatik okur.

```
Bir yazılım şirketinin iç yazışmalarından (toplantı notu, e-posta, Slack mesajı, şartname,
durum raporu, daily notu) Türkçe 250 cümle üret. Her satır şu biçimde olsun:
etiket<TAB>cümle
Etiket 1: cümle birinin yapması gereken bir işi ifade ediyor (açık emir, rica, "-meli",
"X bakacak", "→ isim", şartname yükümlülüğü).
Etiket 0: görev değil (tamamlanmış iş, süren durum, bilgi notu, toplantı tarihi, genel
tavsiye, kapsam dışı ifadesi, teşekkür, talep içermeyen problem tespiti).
Yaklaşık yarısı 1, yarısı 0 olsun. Zor örnekler ekle: "-meli" ile biten ama görev olmayan
genel öğütler, "-acak" ile biten bilgi cümleleri, "Not:" / "Genel hatırlatma:" ile başlayan
bilgilendirmeler, uzun cümlenin sonuna saklanmış görevler ve dolaylı görevler. Farklı
sektörler ve kişi isimleri kullan. Sadece liste ver, açıklama yazma.
```

Kaydettikten sonra 20–30 satırı rastgele kontrol et; yanlış etiketleri düzelt.

### b) Temiz test dokümanları → etiketleme ekranı (Test, kör)

Bu dokümanları **eğitim cümleleri istediğin sohbetten farklı bir sohbette** üret.

```
Bir şirketin yazılım ekibi için Türkçe, gerçekçi 3 ayrı doküman yaz: (1) dağınık, madde
işaretli bir toplantı notu, (2) bir yöneticinin ekibe e-postası, (3) kısa bir teknik
şartname. Ekipte 5-6 kişi olsun (isim ve rolleriyle). Her dokümanda yapılması gereken
işlerle görev olmayan cümleler (durum bilgisi, tamamlanmış işler, genel tavsiyeler,
toplantı bilgisi) karışık olsun; görevlerin bir kısmı açık, bir kısmı dolaylı olsun.
Hangi cümlelerin görev olduğunu belirtme.
```

Uygulamada **Veri etiketleme → Test verisi (kör)** ile yükle, her cümleyi işaretle, kaydet.

---

## 2. Orta vade: gerçek dokümanlar

### a) Kendi çevrendeki toplantı notları
Gönüllü olduğun dernekler, MedaTech müşteri görüşmeleri, staj yerleri (izin alarak).
**Veri etiketleme** ekranında:
1. "Maskelenecek kişi adları" kutusuna dokümandaki tüm isimleri yaz (her satıra bir ad).
2. E-posta / telefon / TCKN / IBAN maskeleme açık kalsın.
3. "Cümlelere ayır"dan sonra metni gözle kontrol et — maskeleme kural tabanlıdır.

Gerçek dokümanları **önce test setine** koy: raporlayacağın sayı ancak o zaman inandırıcı olur.

### b) Kamu ihale şartnameleri (EKAP)
Kamu kurumlarının yazılım/hizmet alımı teknik şartnameleri herkese açık ve gerçek
"Yüklenici … sağlayacaktır" dilindedir. Kurum sitelerinde ya da EKAP'ta "teknik şartname
yazılım hizmet alımı" araması yap, birkaç PDF indir, etiketleme ekranıyla yükle.
Dikkat: şartnamelerde "-meli/-malıdır" ile biten ama atanacak iş olmayan genel kurallar
çoktur (ör. "istekli dokümanı dikkatle incelemelidir") — bunlar değerli zor negatiflerdir.

---

## 3. Ürünleşince: aktif öğrenme döngüsü

Uygulama kendi verisini üretir:

- **Onay** → `1` (görev). **Reddet → "Görev değil"** → `0`.
  **Reddet → "Görev ama şimdi değil"** etiket sayılmaz (cümle görevdi, sadece atanmadı).
- **"Model emin olamadı" paneli:** eşiğin biraz altında kalan cümleler (`GA_CANDIDATE_MARGIN`)
  lidere sorulur. Modelin en kararsız olduğu örnekler, ona en çok şey öğreten etiketlerdir.
- Eğitim betiği veritabanındaki bu kararları okur; test dokümanlarına ait kararları
  otomatik dışarıda bırakır (sızıntı koruması).

### Yeniden eğitim
```powershell
cd backend
python scripts/train_probe.py --out ..\sonuc_probe.txt        # veritabanı kararları dahil
python scripts/evaluate.py --verbose --out ..\sonuc_test.txt   # test setinde ölç
```
Backend'i yeniden başlatınca yeni model kullanılır.

Öneri: Her 50–100 yeni kararda bir yeniden eğit ve test skorunu bir tabloya not et;
skor düşüyorsa son eklenen verileri kontrol et (yanlış etiket olabilir).
