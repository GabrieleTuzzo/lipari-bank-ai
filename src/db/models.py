# src/db/models.py — le tabelle, dichiarate come classi
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String, comment="'system' | 'user' | 'assistant' | 'tool'")
    content: Mapped[str] = mapped_column(Text)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_eur: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    model_used: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # il codice cliente
    full_name: Mapped[str] = mapped_column(String(120))
    operator: Mapped[str] = mapped_column(String(64), index=True)  # chi lo ha in portafoglio

    beneficiaries: Mapped[list["Beneficiary"]] = relationship(back_populates="customer")


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(34), primary_key=True)  # l'IBAN
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    label: Mapped[str] = mapped_column(String(64))  # "principale", "risparmio"
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    mandates: Mapped[list["Mandate"]] = relationship(back_populates="account")
    cards: Mapped[list["Card"]] = relationship(back_populates="account")


class Movement(Base):
    __tablename__ = "movements"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    booking_date: Mapped[date] = mapped_column(Date)  # la data contabile
    description: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # negativo = uscita


class Beneficiary(Base):
    __tablename__ = "beneficiaries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    iban: Mapped[str] = mapped_column(String(34))

    customer: Mapped["Customer"] = relationship(back_populates="beneficiaries")
    mandates: Mapped[list["Mandate"]] = relationship(
        back_populates="beneficiary",
        passive_deletes="all",
    )


class Mandate(Base):
    __tablename__ = "mandates"
    __table_args__ = (UniqueConstraint("reference", name="uq_mandates_reference"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    beneficiary_id: Mapped[str] = mapped_column(
        ForeignKey("beneficiaries.id", ondelete="RESTRICT"),
        index=True,
    )
    reference: Mapped[str] = mapped_column(String(35))

    account: Mapped["Account"] = relationship(back_populates="mandates")
    beneficiary: Mapped["Beneficiary"] = relationship(back_populates="mandates")


class Card(Base):
    __tablename__ = "cards"
    __table_args__ = (CheckConstraint("plafond >= 0", name="ck_cards_plafond_nonnegative"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    plafond: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    account: Mapped["Account"] = relationship(back_populates="cards")

class AppUser(Base):
    __tablename__ = "app_users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="operator")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index(
            "ix_document_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    document_id: Mapped[str] = mapped_column(String, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    chunk_metadata: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    visibility: Mapped[str] = mapped_column(
        String(32), default="public", server_default="public", index=True
    )
