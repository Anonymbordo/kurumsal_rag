"""Dokümandaki kişiler ve duyurular.

- `roster`: dokümanda "Ad Soyad (Rol)" ya da "Katılımcılar: ..." biçiminde geçen kişiler.
  Ekipte kayıtlı olmayanlar lidere gösterilir; tek tıkla ekibe eklenebilir.
- `unknown_mentioned`: cümlede adı geçen ama sistemde kayıtlı olmayan kişiler.
  Böyle bir görevde model başka birini "yüksek güvenle" önermemeli.
- `is_announcement`: tek kişiye değil tüm ekibe yönelik bilgilendirme ("Not: ... eğitim var").
"""
import re
from dataclasses import dataclass, field

from ..models import User

UP = "A-ZÇĞİÖŞÜ"
LO = "a-zçğıöşü"
NAME = rf"[{UP}][{LO}]+(?:[ \t]+[{UP}][{LO}]+){{1,2}}"
_B = rf"(?<![\w{UP}{LO}])"  # kelime başı (Türkçe harflerle)

ROLE_WORDS = (
    "geliştirici", "mühendis", "müdür", "uzman", "lider", "analist", "tasarım", "test", "qa", "devops",
    "yönetici", "sorumlu", "developer", "engineer", "manager", "designer", "architect", "mimar", "stajyer",
    "direktör", "koordinatör", "specialist", "owner", "scrum", "ürün", "product", "backend", "frontend",
    "mobil", "sre", "danışman", "şef", "başkan", "admin", "yazar",
)
ROLE_SKILLS = (
    ("backend", "backend"), ("frontend", "frontend"), ("arayüz", "frontend"), ("full", "backend"),
    ("full", "frontend"), ("mobil", "mobile"), ("mobile", "mobile"), ("ios", "ios"), ("ios", "mobile"),
    ("android", "mobile"), ("qa", "qa"), ("test", "qa"), ("kalite", "qa"), ("devops", "devops"),
    ("bulut", "devops"), ("cloud", "devops"), ("sre", "devops"), ("altyapı", "devops"), ("platform", "devops"),
    ("güvenlik", "security"), ("security", "security"), ("doküman", "docs"), ("yazar", "docs"),
)
LEAD_WORDS = ("müdür", "manager", "direktör", "yönetici", "takım lideri", "ekip lideri", "head of")
ROSTER_HEADS = ("katılımcılar", "katılanlar", "ekip", "kime", "alıcılar", "bilgi", "cc")

INFO_PREFIX = re.compile(
    r"^\s*(?:[-•*]\s*)?(not|nota|hatırlatma|genel hatırlatma|duyuru|bilgi|bilgilendirme|önemli|fyi)\s*:",
    re.IGNORECASE,
)
ALL_HANDS = (
    "herkes", "herkesin", "tüm ekip", "bütün ekip", "tüm çalışan", "şirket genelinde", "tüm arkadaşlar",
    "takvimlerinizi", "katılım zorunlu", "tüm birimler", "tüm katılımcılar",
)


def tr_lower(s: str) -> str:
    return s.replace("I", "ı").replace("İ", "i").lower()


@dataclass
class Person:
    name: str
    role: str = ""
    user_id: str | None = None  # ekipte kayıtlıysa
    skills: list[str] = field(default_factory=list)
    is_lead: bool = False

    @property
    def first(self) -> str:
        return self.name.split()[0]


def skills_for_role(role: str) -> list[str]:
    r = tr_lower(role)
    out: list[str] = []
    for word, tag in ROLE_SKILLS:
        if word in r and tag not in out:
            out.append(tag)
    return out


def is_lead_role(role: str) -> bool:
    r = tr_lower(role)
    return any(w in r for w in LEAD_WORDS)


def _looks_like_role(s: str) -> bool:
    r = tr_lower(s)
    return any(w in r for w in ROLE_WORDS)


def _match_member(name: str, members: list[User]) -> User | None:
    key = tr_lower(" ".join(name.split()))
    for u in members:
        if tr_lower(" ".join(u.name.split())) == key:
            return u
    return None


def roster(text: str, members: list[User]) -> list[Person]:
    """Dokümanda rolüyle ya da katılımcı listesinde geçen kişiler (geçiş sırasıyla)."""
    found: dict[str, Person] = {}

    def add(name: str, role: str) -> None:
        name = " ".join(name.split())
        role = " ".join(role.split())
        key = tr_lower(name)
        if key in found:
            if role and not found[key].role:
                found[key].role = role
            return
        u = _match_member(name, members)
        found[key] = Person(
            name=name, role=role, user_id=u.id if u else None,
            skills=skills_for_role(role), is_lead=is_lead_role(role),
        )

    # 1) Ad Soyad (Rol)
    for m in re.finditer(rf"{_B}({NAME})\s*\(([^()]{{2,60}})\)", text):
        if _looks_like_role(m.group(2)):
            add(m.group(1), m.group(2))

    # 2) Katılımcılar: Ad Soyad, Ad Soyad – Rol, ...
    for line in text.splitlines():
        head, sep, rest = line.partition(":")
        if not sep or tr_lower(head.strip(" -•*\t")) not in ROSTER_HEADS:
            continue
        for piece in re.split(r"[,;]", rest):
            m = re.match(rf"\s*({NAME})(?:\s*[-–—/]\s*([^()]+)|\s*\(([^()]+)\))?\s*$", piece)
            if m:
                role = (m.group(2) or m.group(3) or "").strip()
                add(m.group(1), role if _looks_like_role(role) else "")
    return list(found.values())


def _mentions(first: str, text: str) -> bool:
    return re.search(rf"{_B}{re.escape(first)}(?=$|[\s,.;:!?&)'’→-])", text) is not None


def unknown_mentioned(text: str, people: list[Person], members: list[User]) -> list[Person]:
    """Cümlede adı geçen ama ekipte kayıtlı olmayan kişiler."""
    member_firsts = {u.name.split()[0] for u in members}
    out = []
    for p in people:
        if p.user_id is None and p.first not in member_firsts and _mentions(p.first, text):
            out.append(p)
    return out


def any_person_mentioned(text: str, people: list[Person], members: list[User]) -> bool:
    firsts = {u.name.split()[0] for u in members} | {p.first for p in people}
    return any(_mentions(f, text) for f in firsts)


def is_announcement(text: str, people: list[Person], members: list[User]) -> bool:
    """Tüm ekibe yönelik bilgilendirme mi? Belirli bir kişi anılıyorsa görevdir."""
    if any_person_mentioned(text, people, members):
        return False
    low = tr_lower(text)
    return bool(INFO_PREFIX.match(text)) or any(w in low for w in ALL_HANDS)
