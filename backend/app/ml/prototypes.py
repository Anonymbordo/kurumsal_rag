"""Eğitimsiz sınıflandırma için örnek cümleler (prototipler).

Encoder bu örneklere benzerlikle karar verir. Kuruma özel örnek eklemek
modeli eğitmeden kaliteyi artırmanın en ucuz yoludur.
"""

TASK_EXAMPLES = [
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
