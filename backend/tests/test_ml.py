"""Encoder ve kümeleme birimleri. İndirme gerektirmeyen yedek embedder ile çalışır;
gerçek modelin kalitesini değil, boru hattının doğruluğunu sınar."""
from app.llm.encoder import EncoderProvider
from app.ml.clustering import cluster
from app.ml.embedder import HashingEmbedder
from app.seed import SPRINT_NOTE


def test_encoder_extracts_with_aligned_sources_and_scores():
    prov = EncoderProvider(HashingEmbedder())
    tasks = prov.extract_tasks(SPRINT_NOTE, "meeting")
    assert tasks
    for t in tasks:
        assert SPRINT_NOTE[t.source_start : t.source_end] == t.source_quote
        assert 0.5 <= t.detect_score <= 1.0
        assert t.tags


def test_hdbscan_groups_similar_and_flags_outlier():
    texts = [
        "Staging ortamı için ölçekleme kuralı",
        "Staging ortamına otomatik ölçekleme kuralı eklenmeli",
        "Canlı ortam için ölçekleme kuralı yazılmalı",
        "iOS Face ID girişinde oturum düşüyor",
        "iOS Face ID ile girişte oturum kapanıyor",
        "iOS uygulamasında Face ID oturum hatası",
        "Yılbaşı yemeği için restoran rezervasyonu",
    ]
    emb = HashingEmbedder()
    res = cluster(texts, emb.encode(texts), min_cluster_size=2)
    labels = list(res.labels)
    assert labels[0] == labels[1] == labels[2] != -1
    assert labels[3] == labels[4] == labels[5] != -1
    assert labels[0] != labels[3]
    assert labels[6] == -1 and res.outliers[6]  # alışılmadık görev
    assert not res.outliers[:6].any()
    assert all(res.names.get(l) for l in set(labels) if l != -1)


def test_too_few_items_are_not_clustered():
    texts = ["a görev", "b görev"]
    res = cluster(texts, HashingEmbedder().encode(texts))
    assert list(res.labels) == [-1, -1] and res.names == {} and not res.outliers.any()


def test_mentioned_members_handles_turkish_suffixes():
    from types import SimpleNamespace as U

    from app.services.assignment import mentioned_members

    team = [U(id=i, name=n) for i, n in [("a", "Ayşe Kaya"), ("c", "Can Yıldız"), ("e", "Elif Tunç"), ("s", "Selin Arslan")]]
    names = lambda t: [u.id for u in mentioned_members(t, team)]
    assert names("Selin, smoke test paketini küçültmeli.") == ["s"]
    assert names("Ayşe'den zaman aşımını gözden geçirmesini rica ediyorum.") == ["a"]
    assert names("Kısıt eklenmeli (Elif & Can beraber ilerleyebilir).") == ["e", "c"]
    assert names("Bu iş can sıkıcı ama yapılmalı.") == []  # küçük harf "can" isim değil
