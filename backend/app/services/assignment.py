"""Kişi önerisi.

Bilinçli olarak LLM'den ayrı, açıklanabilir bir puanlama: her öneri, liderin
görebileceği gerekçelere (uzmanlık eşleşmesi, geçmiş benzer işler, iş yükü)
dayanır. Ağırlıklar ve eşikler kurum verisiyle ayarlanmalıdır.
"""
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Task, User
from .load import load_pct

TAG_LABELS = {
    "backend": "backend",
    "mobile": "mobil",
    "ios": "iOS",
    "qa": "test/QA",
    "security": "güvenlik",
    "devops": "DevOps",
    "frontend": "arayüz",
    "docs": "dokümantasyon",
    "general": "genel",
}

W_SKILL, W_HISTORY, W_LOAD = 0.5, 0.3, 0.2
# Anlamsal benzerlik varken (encoder sağlayıcısı) ağırlıklar
W_SKILL_S, W_HISTORY_S, W_SEM_S, W_LOAD_S = 0.35, 0.15, 0.3, 0.2
OVERLOAD_PCT = 90
CAPACITY_LIMIT_PCT = 85


@dataclass
class Candidate:
    user: User
    score: float
    skill: float
    history_count: int
    load: int
    matched: list[str]
    sem_sim: float | None = None  # en benzer geçmiş işine kosinüs benzerliği
    sem_example: str | None = None  # o işin kısa adı


@dataclass
class Suggestion:
    assignee_id: str | None
    alt_assignee_id: str | None
    confidence: int  # 1 düşük, 2 orta, 3 yüksek
    reasons: list[str]


def _history_count(db: Session, user_id: str, tags: list[str]) -> int:
    done = db.scalars(select(Task).where(Task.assignee_id == user_id, Task.status == "done"))
    return sum(1 for t in done if set(t.tags) & set(tags))


SemanticMap = dict[str, tuple[float, str]]  # user_id -> (en yüksek benzerlik, o işin adı)


def mentioned_members(text: str, members: list[User]) -> list[User]:
    """Cümlede adı geçen ekip üyeleri, geçiş sırasına göre.

    Türkçe ekleri tolere eder: "Selin," "Ayşe'den" "Elif & Can". Büyük harf duyarlıdır
    ("can" kelimesi ile "Can" ismi karışmasın diye).
    """
    found: list[tuple[int, User]] = []
    for u in members:
        first = u.name.split()[0]
        m = re.search(rf"(?<![\wçğıöşüÇĞİÖŞÜ]){re.escape(first)}(?=$|[\s,.;:!?&)'’→-])", text)
        if m:
            found.append((m.start(), u))
    return [u for _, u in sorted(found, key=lambda x: x[0])]


def rank_candidates(
    db: Session,
    team_id: str,
    tags: list[str],
    semantic: SemanticMap | None = None,
    pending_days: dict[str, float] | None = None,
) -> list[Candidate]:
    members = db.scalars(select(User).where(User.team_id == team_id, User.is_lead.is_(False))).all()
    tagset = set(tags) - {"general"}
    sims = {u.id: (semantic or {}).get(u.id, (0.0, ""))[0] for u in members}
    lo, hi = (min(sims.values()), max(sims.values())) if sims else (0.0, 0.0)
    out: list[Candidate] = []
    for u in members:
        matched = sorted(tagset & set(u.skills))
        skill = len(matched) / len(tagset) if tagset else 0.0
        hist = _history_count(db, u.id, list(tagset))
        load = load_pct(db, u) + round((pending_days or {}).get(u.id, 0.0) / get_settings().sprint_capacity_days * 100)
        free = max(0.0, 1 - load / 100)
        if semantic:
            sem = (sims[u.id] - lo) / (hi - lo) if hi > lo else 0.0  # adaylar arasında 0–1'e ölçekle
            score = W_SKILL_S * skill + W_HISTORY_S * min(hist, 4) / 4 + W_SEM_S * sem + W_LOAD_S * free
            sim, example = semantic.get(u.id, (None, None))
        else:
            score = W_SKILL * skill + W_HISTORY * min(hist, 4) / 4 + W_LOAD * free
            sim, example = None, None
        out.append(Candidate(u, round(score, 4), skill, hist, load, matched, sim, example or None))
    out.sort(key=lambda c: c.score, reverse=True)
    return out


def _confidence(ranked: list[Candidate]) -> int:
    if not ranked:
        return 1
    top = ranked[0]
    margin = top.score - (ranked[1].score if len(ranked) > 1 else 0.0)
    if top.skill == 0 or top.score < 0.35 or margin < 0.05:
        return 1
    if top.score >= 0.6 and margin >= 0.15:
        return 3
    return 2


def _reasons(c: Candidate) -> list[str]:
    reasons: list[str] = []
    if c.matched:
        reasons.append("Uzmanlık alanı eşleşiyor: " + ", ".join(TAG_LABELS.get(t, t) for t in c.matched))
    else:
        reasons.append("Uzmanlık alanı doğrudan eşleşmiyor")
    if c.history_count:
        reasons.append(f"Bu alanda {c.history_count} benzer görevi tamamladı")
    else:
        reasons.append("Bu alanda geçmiş işi az")
    if c.sem_sim is not None and c.sem_example:
        reasons.append(f"En benzer geçmiş işi: {c.sem_example} (benzerlik %{round(c.sem_sim * 100)})")
    reasons.append(f"Sprint yükü %{c.load}")
    return reasons


def suggest(
    db: Session,
    team_id: str,
    tags: list[str],
    semantic: SemanticMap | None = None,
    text: str = "",
    pending_days: dict[str, float] | None = None,
) -> Suggestion:
    ranked = rank_candidates(db, team_id, tags, semantic, pending_days)
    if not ranked:
        return Suggestion(None, None, 1, ["Ekipte uygun kişi bulunamadı"])

    # Dokümanda adı açıkça geçen ekip üyesi en güçlü sinyaldir.
    named = mentioned_members(text, [c.user for c in ranked]) if text else []
    if named:
        by_id = {c.user.id: c for c in ranked}
        first = by_id[named[0].id]
        reasons = [f"Dokümanda adı geçiyor: {first.user.name}"] + _reasons(first)[1:]
        alt = by_id[named[1].id] if len(named) > 1 else None
        if alt:
            reasons.insert(1, f"{alt.user.name} da aynı görevde anılıyor")
        elif first.load >= OVERLOAD_PCT:
            free = [c for c in ranked if c.user.id != first.user.id and c.load < CAPACITY_LIMIT_PCT]
            alt = free[0] if free else None
        return Suggestion(first.user.id, alt.user.id if alt else None, 3, reasons)

    top = ranked[0]
    alt = None
    if top.load >= OVERLOAD_PCT:
        free = [c for c in ranked[1:] if c.load < CAPACITY_LIMIT_PCT]
        alt = next((c for c in free if c.skill > 0), free[0] if free else None)
    return Suggestion(top.user.id, alt.user.id if alt else None, _confidence(ranked), _reasons(top))
