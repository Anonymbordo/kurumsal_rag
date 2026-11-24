"""Eğitimsiz sınıflandırma için örnek cümleler (prototipler).

Encoder bu örneklere benzerlikle karar verir. Kuruma özel örnek eklemek
modeli eğitmeden kaliteyi artırmanın en ucuz yoludur.
"""

TASK_EXAMPLES = [
    # Konuşma dili (toplantı dökümü): üstlenme ve rica
    "Ödeme servisindeki zaman aşımını ben yarın düzeltirim.",
    "Raporlama ekranına bu hafta ben bakacağım.",
    "Mert, bildirim akışına bir bakabilir misin?",
    "Limit kontrolü tek bir servise taşınmalı.",
    "Ödeme API'si yeniden yazılmalı.",
    "Giriş ekranındaki hata düzeltilmeli.",
    "Uygulama açılışta çöküyor, incelenmesi gerekiyor.",
    "Canlıya çıkmadan önce regresyon testleri yapılmalı.",
    "Loglardaki kişisel veriler maskelenmeli.",
    "Staging ortamına yeni bir ölçekleme kuralı eklenmeli.",
    "Müşteri ekibi için bilgilendirme dokümanı hazırlanmalı.",
    "Raporlama ekranına dışa aktarma butonu eklenecek.",
    "Veritabanı yedekleme süreci otomatikleştirilmeli.",
    "Oturum süresi on beş dakikaya indirilmeli.",
    "Yük testi yapılıp sonuçlar raporlanmalı.",
    "Bildirime tıklandığında uygulama kapanıyor.",
    "Eski uç noktalar kaldırılmadan önce kullanıcılar bilgilendirilmeli.",
    "Şifre politikası güncellenmeli.",
    "Fatura servisinde zaman aşımı sorunu çözülmeli.",
    "Yeni kampanya için arayüz tasarımı hazırlanacak.",
    "CI hattına güvenlik taraması eklenmeli.",
    "Mobil uygulamada karanlık tema desteği geliştirilecek.",
    "Sözleşme maddeleri hukuk ekibiyle gözden geçirilmeli.",
]

NON_TASK_EXAMPLES = [
    # Konuşma dili: durum anlatımı, onay, sohbet
    "Geçen hafta ödeme tarafında sorun yaşamadık.",
    "Evet, ben de aynı fikirdeyim.",
    "Herkese günaydın, başlayalım mı?",
    # Konuşma dili (toplantı dökümü): üstlenme ve rica
    "Ödeme servisindeki zaman aşımını ben yarın düzeltirim.",
    "Raporlama ekranına bu hafta ben bakacağım.",
    "Mert, bildirim akışına bir bakabilir misin?",
    "Bu sprintin ana hedefi müşteri şikayetlerini azaltmak.",
    "Toplantıya ekibin tamamı katıldı.",
    "Android tarafında sorun görülmedi.",
    "Geçen sprintte hedeflerin çoğu tamamlandı.",
    "Kampanya yılbaşında başlayacak.",
    "Kullanıcı sayısı geçen aya göre arttı.",
    "Eski uç nokta geçiş süresince paralel çalışacak.",
    "Mimari kurul önerilen yaklaşımı olumlu buldu.",
    "Müşteri memnuniyeti anket sonuçları paylaşıldı.",
    "Bir sonraki toplantı pazartesi günü yapılacak.",
    "Sistem şu an üç farklı serviste çalışıyor.",
    "Denetim raporu geçen hafta yayımlandı.",
    "Ekip bu konuda deneyimli.",
    "Performans metrikleri hedeflerin üzerinde.",
]

TAG_DESCRIPTIONS: dict[str, list[str]] = {
    "backend": ["API ve servis geliştirme", "sunucu tarafı iş mantığı", "veritabanı ve uç nokta değişikliği"],
    "mobile": ["mobil uygulama geliştirme", "iOS ve Android uygulaması"],
    "ios": ["iOS uygulaması", "iPhone ve Face ID"],
    "qa": ["test ve kalite güvencesi", "regresyon ve yük testi"],
    "security": ["güvenlik ve KVKK uyumu", "kişisel verilerin maskelenmesi", "oturum ve şifre güvenliği"],
    "devops": ["altyapı ve ortam yönetimi", "staging ve canlı ortam ölçekleme", "CI/CD ve dağıtım"],
    "frontend": ["web arayüzü geliştirme", "ekran ve kullanıcı arayüzü tasarımı"],
    "docs": ["dokümantasyon ve bilgilendirme metni", "eğitim ve kullanıcı rehberi"],
}

# Konu aynı, kip farklı cümle çiftleri: (görev, durum/bilgi).
# Farklarının ortalaması embedding uzayında "yapılacak ↔ yapıldı/bilgi" yönünü verir;
# konu bilgisi çiftin iki tarafında ortak olduğu için çıkarmada birbirini götürür.
# Değerlendirme dokümanlarındaki cümleler buraya KOPYALANMAMALI (sızıntı olur).
MODALITY_PAIRS: list[tuple[str, str]] = [
    ("Fatura servisine yeniden deneme mekanizması eklenmeli.", "Fatura servisine yeniden deneme mekanizması eklendi."),
    ("Rapor ekranındaki filtre hatası düzeltilmeli.", "Rapor ekranındaki filtre hatası düzeltildi."),
    ("Kampanya sayfasının tasarımı hazırlanacak.", "Kampanya sayfasının tasarımı hazırlandı."),
    ("Kredi başvuru formu için doğrulama kuralları yazılsın.", "Kredi başvuru formu için doğrulama kuralları yazıldı."),
    ("Ahmet, müşteri anketinin sonuçlarını derleyebilir misin?", "Ahmet müşteri anketinin sonuçlarını derledi."),
    ("Sözleşme taslağını hukuk ekibine iletmemiz lazım.", "Sözleşme taslağı hukuk ekibine iletildi."),
    ("Bildirim servisinin loglarına birinin bakması gerekiyor.", "Bildirim servisinin loglarına bakıldı, sorun yok."),
    ("Veri ambarı için gece yedeklemesi kurulsun.", "Veri ambarı için gece yedeklemesi kuruldu."),
    ("Arama sonuçları yavaş, hızlandırmak için bir el atılsa iyi olur.", "Arama sonuçları önceki sürüme göre daha hızlı."),
    ("Zeynep cumaya kadar entegrasyon testlerini bitirecek.", "Zeynep entegrasyon testlerini geçen hafta bitirdi."),
    ("Ödeme sayfasındaki çökme → Kerem", "Ödeme sayfasındaki çökme Kerem tarafından giderildi."),
    ("Yüklenici kullanıcı verilerini şifreli saklayacaktır.", "Kullanıcı verileri şu anda şifreli saklanıyor."),
    ("Uygulama erişilebilirlik standartlarına uygun hâle getirilecektir.", "Uygulama erişilebilirlik standartlarına uygun durumda."),
    ("Teslimattan önce kullanım kılavuzu sunulacaktır.", "Kullanım kılavuzu teslimatla birlikte sunuldu."),
    ("Eski raporlama modülünün kaldırılma tarihi netleştirilmeli.", "Eski raporlama modülü geçen ay kaldırıldı."),
    ("Test ortamı için yeni bir sunucu talebi açılmalı.", "Test ortamı için yeni sunucu teslim edildi."),
    ("Kod incelemesi için bir gönüllü lazım.", "Kod incelemesi Deniz tarafından tamamlandı."),
    ("CI hattı kırık, Burcu bakacak.", "CI hattı dün akşamdan beri sorunsuz çalışıyor."),
    ("Mobil uygulamanın karanlık tema desteği geliştirilmeli.", "Mobil uygulamanın karanlık tema desteği yayında."),
    ("Kur hesaplama servisindeki yuvarlama hatası incelensin.", "Kur hesaplama servisindeki yuvarlama hatası çözüldü."),
    ("Yeni çalışanlar için erişim süreci dokümante edilmeli.", "Yeni çalışanlar için erişim süreci dokümante edildi."),
    ("Önbellek süresi beş dakikaya düşürülmeli.", "Önbellek süresi beş dakikaya düşürüldü."),
    ("Şifre sıfırlama e-postasının metni güncellensin.", "Şifre sıfırlama e-postasının metni güncellendi."),
    ("Performans panosuna hata oranı grafiği eklenecek.", "Performans panosunda hata oranı grafiği zaten var."),
]
