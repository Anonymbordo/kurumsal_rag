"""Uygulama ayarları. Tüm değerler ortam değişkenleriyle (.env) değiştirilebilir."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # .env hem proje kökünde hem backend/ içinde aranır; backend/.env kökteki değerleri ezer.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), env_prefix="GA_", extra="ignore")

    # Veritabanı: geliştirmede SQLite, kurulumda PostgreSQL URL'si verilebilir.
    database_url: str = "sqlite:///./gorev_asistani.db"

    # Kurum kimliği (beyaz etiket): arayüz bu değerleri /api/org üzerinden okur.
    org_name: str = "Kurum Adı"
    org_primary: str = ""  # butonlar; boşsa vurgu rengi kullanılır
    org_accent: str = "#1F4FD1"  # küçük vurgu detayları
    org_logo_url: str = ""  # boşsa arayüz logo yer tutucusunu gösterir

    # LLM katmanı. Mimari netleşene kadar "mock" sağlayıcı kullanılıyor.
    llm_provider: str = "mock"  # mock | encoder
    # encoder sağlayıcısının embedding modeli (Hugging Face adı) ya da "hashing" (indirme yok)
    embed_model: str = "intfloat/multilingual-e5-small"
    # Etiketleme aracının yazdığı veri klasörü (samples/train, samples/test)
    samples_dir: str = "../samples"
    # Aktif öğrenme: eşiğin bu kadar altına kadar olan cümleler "emin olamadı" panelinde gösterilir
    candidate_margin: float = 0.25
    # Eğitilmiş görev sınıflandırıcısı (scripts/train_probe.py üretir). Yoksa prototip yöntemi kullanılır.
    probe_path: str = "models/task_probe.joblib"
    # Kümeleme: bir iş alanı en az kaç görevden oluşsun
    cluster_min_size: int = 2
    # HDBSCAN iş alanı adlarını arayüzde göster (küçük encoder'larda adlar anlamsız olabiliyor)
    show_workstreams: bool = False
    llm_model_label: str = "Yerel model (mock)"

    # Decoder (üretken model): sohbette serbest sorular ve "görevimi açıkla".
    # none -> şablon cevaplar; ollama -> yerel Ollama sunucusu (CPU, 4-bit)
    decoder: str = "none"
    decoder_url: str = "http://localhost:11434"
    decoder_model: str = "qwen2.5:3b"
    decoder_timeout: float = 120.0
    decoder_logprobs: bool = True  # token olasılıklarını iste (destekleyen Ollama sürümlerinde)
    decoder_keep_alive: str = "30m"  # model bu süre boşta kalsa da bellekte tutulur (yeniden yükleme yok)
    decoder_num_ctx: int = 2048  # bağlam penceresi; küçük pencere = daha az bellek, daha hızlı
    decoder_max_tokens: int = 256  # cevap uzunluk sınırı
    decoder_warmup: bool = True  # uygulama açılırken modeli belleğe yükle
    rag_top_k: int = 4  # decoder'a verilecek en fazla kayıt (prompt kısa = prefill hızlı)

    # Toplantılar
    data_dir: str = "./data"  # ses kayıtları burada tutulur
    jitsi_domain: str = ""  # kurum içi Jitsi sunucusu, ör. meet.kurum.local (boşsa yalnızca ses kaydı)
    whisper_model: str = "small"  # faster-whisper: tiny | base | small | medium | large-v3
    whisper_compute: str = "int8"  # CPU için 8-bit kuantizasyon
    whisper_language: str = "tr"
    keep_audio: bool = False  # transkript sonrası ses dosyaları silinsin (KVKK: veri minimizasyonu)

    # Sprint kapasitesi (kişi başı iş günü) — yük yüzdesi bunun üzerinden hesaplanır.
    sprint_capacity_days: float = 10.0

    # Geliştirme: frontend ayrı portta çalışırken CORS izni.
    cors_origins: str = "http://localhost:5173"

    # Üretimde derlenmiş frontend'in yolu (Docker imajında doldurulur).
    frontend_dist: str = "../frontend/dist"

    seed_demo_data: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
