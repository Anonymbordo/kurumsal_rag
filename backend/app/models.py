"""Veri modeli.

Görev durumları:
  suggested  -> model önerdi, liderin kararı bekleniyor
  accepted   -> lider onayladı (aktarılmayı bekliyor)
  rejected   -> lider reddetti
  exported   -> iş takip sistemine (Jira vb.) aktarıldı / aktif
  done       -> tamamlandı
  candidate  -> model eşiğin biraz altında buldu; lidere "görev mi?" diye soruluyor (aktif öğrenme)
  dismissed  -> lider aday cümleye / duyuruya "görev değil" dedi
  announcement -> tüm ekibe yönelik bilgilendirme gibi görünüyor; kişiye atanmaz
  announced  -> lider duyuruyu ekiple paylaşmayı onayladı (aktarımda tüm ekiple paylaşılır)
"""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .timeutil import utcnow


def _now() -> datetime:
    return utcnow()


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    key_prefix: Mapped[str] = mapped_column(String(10), default="TSK")


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(120))
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))
    is_lead: Mapped[bool] = mapped_column(Boolean, default=False)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    base_load_days: Mapped[float] = mapped_column(Float, default=0.0)

    team: Mapped[Team] = relationship()

    @property
    def initials(self) -> str:
        parts = self.name.split()
        return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


class Group(Base):
    __tablename__ = "groups"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    short: Mapped[str] = mapped_column(String(4))
    color: Mapped[str] = mapped_column(String(9), default="#DCE3F0")
    member_ids: Mapped[list] = mapped_column(JSON, default=list)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    doc_type: Mapped[str] = mapped_column(String(30), default="meeting")
    sprint: Mapped[str] = mapped_column(String(60), default="")
    text: Mapped[str] = mapped_column(Text)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))
    shared_with: Mapped[list] = mapped_column(JSON, default=list)
    related_task_key: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    uploader: Mapped[User] = relationship()


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str | None] = mapped_column(String(30), nullable=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))
    order_no: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    est_days: Mapped[float] = mapped_column(Float, default=1.0)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Kaynak bağlantısı: görevin dokümandaki yeri
    source_ref: Mapped[str] = mapped_column(String(30), default="")
    source_quote: Mapped[str] = mapped_column(Text, default="")
    source_start: Mapped[int] = mapped_column(Integer, default=-1)
    source_end: Mapped[int] = mapped_column(Integer, default=-1)

    # Öneri
    suggested_assignee_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    alt_assignee_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    confidence: Mapped[int] = mapped_column(Integer, default=2)  # 1 düşük, 2 orta, 3 yüksek
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    detect_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # "görev mi" olasılığı
    workstream: Mapped[str | None] = mapped_column(String(120), nullable=True)  # HDBSCAN küme adı
    is_outlier: Mapped[bool] = mapped_column(Boolean, default=False)  # hiçbir kümeye girmedi
    kind: Mapped[str] = mapped_column(String(20), default="task")  # task | announcement
    # Cümlede adı geçen ama ekipte kayıtlı olmayan kişiler
    unknown_mentions: Mapped[list] = mapped_column(JSON, default=list)

    # Karar
    status: Mapped[str] = mapped_column(String(20), default="suggested")
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    lead_picked_first: Mapped[bool] = mapped_column(Boolean, default=False)
    # Reddedilme nedeni: not_task (cümle görev değil) | not_now (görev ama bu dokümandan atanmayacak)
    reject_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    assigned_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    @property
    def is_forcing(self) -> bool:
        """Düşük güvenli görevlerde lider önce kendi seçimini yapar (bilişsel zorlama)."""
        return self.confidence == 1


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    text: Mapped[str] = mapped_column(Text)
    blocks: Mapped[list] = mapped_column(JSON, default=list)  # yapılandırılmış içerik (görev kartları vb.)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AuditLog(Base):
    """Kurumsal denetim için: kim, neyi, ne zaman yaptı."""

    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(60))
    target: Mapped[str] = mapped_column(String(120))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime, default=_now)
