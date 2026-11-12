# src/db/repos.py — l'unico posto che sa che esiste un database
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Account, Card, ChatMessage, ChatSession, Customer, Movement


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_session(self, user_id: str) -> ChatSession:
        chat = ChatSession(user_id=user_id)
        self.session.add(chat)
        await self.session.flush()
        return chat

    async def find_session(self, session_id: str, user_id: str) -> ChatSession | None:
        stmt = (
            select(ChatSession)
            .where(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .options(selectinload(ChatSession.messages))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tokens: int = 0,
        cost_eur: Decimal = Decimal("0"),
        model_used: str | None = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            tokens=tokens,
            cost_eur=cost_eur,
            model_used=model_used,
        )
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def list_messages(self, session_id: str) -> list[ChatMessage]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def cost_between(self, inizio: datetime, fine: datetime) -> Decimal:
        """Quanto sono costati i messaggi scritti in un intervallo: la somma, o zero."""
        speso = await self.session.scalar(
            select(func.coalesce(func.sum(ChatMessage.cost_eur), 0)).where(
                ChatMessage.created_at >= inizio, ChatMessage.created_at < fine
            )
        )
        return Decimal(str(speso)) if speso is not None else Decimal("0")

# src/db/repos.py — estratto: i tre metodi che i tool usano, dal Giorno 3
class AccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def of_user(self, username: str, account_id: str) -> Account | None:
        """Il conto, solo se è di un cliente nel portafoglio di questo operatore."""
        return await self.session.scalar(
            select(Account)
            .join(Customer, Customer.id == Account.customer_id)
            .where(Account.id == account_id, Customer.operator == username)
        )

    async def of_customer(self, username: str, customer_id: str) -> list[Account]:
        """I conti di un cliente, solo se il cliente è nel portafoglio di questo operatore."""
        stmt = (
            select(Account)
            .join(Customer, Customer.id == Account.customer_id)
            .where(Customer.id == customer_id, Customer.operator == username)
            .order_by(Account.label)
        )
        return list((await self.session.scalars(stmt)).all())

    async def ids_in_portfolio(self, username: str) -> set[str]:
        """Gli IBAN dei conti dei clienti nel portafoglio di questo operatore."""
        stmt = (
            select(Account.id)
            .join(Customer, Customer.id == Account.customer_id)
            .where(Customer.operator == username)
        )
        return set((await self.session.scalars(stmt)).all())


class MovementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def recent(self, username: str, account_id: str, limite: int) -> list[Movement]:
        """Gli ultimi movimenti di un conto del portafoglio, dal più recente."""
        stmt = (
            select(Movement)
            .join(Account, Account.id == Movement.account_id)
            .join(Customer, Customer.id == Account.customer_id)
            .where(Account.id == account_id, Customer.operator == username)
            .order_by(Movement.booking_date.desc())
            .limit(limite)
        )
        return list((await self.session.scalars(stmt)).all())

    async def recorded_transfers(
        self, username: str, account_id: str, descrizione: str, limite: int = 5
    ) -> list[Movement]:
        """Bonifici contabilizzati corrispondenti alla descrizione, solo nel portafoglio."""
        stmt = (
            select(Movement)
            .join(Account, Account.id == Movement.account_id)
            .join(Customer, Customer.id == Account.customer_id)
            .where(
                Account.id == account_id,
                Customer.operator == username,
                func.lower(Movement.description).contains(descrizione.lower(), autoescape=True),
                func.lower(Movement.description).contains("bonific", autoescape=True),
            )
            .order_by(Movement.booking_date.desc(), Movement.id)
            .limit(limite)
        )
        return list((await self.session.scalars(stmt)).all())

    async def with_owner(
        self, username: str, account_id: str, dal: date, al: date
    ) -> list[tuple[Movement, str]]:
        """I movimenti di un conto nel periodo, con il nome dell'intestatario."""
        stmt = (
            select(Movement, Customer.full_name)
            .join(Account, Account.id == Movement.account_id)
            .join(Customer, Customer.id == Account.customer_id)
            .where(
                Account.id == account_id,
                Customer.operator == username,
                Movement.booking_date.between(dal, al),
            )
            .order_by(Movement.booking_date, Movement.id)
        )
        return list((await self.session.execute(stmt)).all())


class CardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def for_account(self, username: str, account_id: str) -> list[Card]:
        """Le carte registrate su un conto del portafoglio dell'operatore."""
        stmt = (
            select(Card)
            .join(Account, Account.id == Card.account_id)
            .join(Customer, Customer.id == Account.customer_id)
            .where(Account.id == account_id, Customer.operator == username)
            .order_by(Card.id)
        )
        return list((await self.session.scalars(stmt)).all())

    async def spent_by_month(
        self, username: str, account_id: str, dal: date, al: date
    ) -> list[tuple[str, Decimal]]:
        """La somma delle uscite del conto, raggruppata per mese."""
        mese = func.to_char(Movement.booking_date, "YYYY-MM")
        stmt = (
            select(mese, func.sum(-Movement.amount))
            .join(Account, Account.id == Movement.account_id)
            .join(Customer, Customer.id == Account.customer_id)
            .where(
                Account.id == account_id,
                Customer.operator == username,
                Movement.booking_date.between(dal, al),
                Movement.amount < 0,
            )
            .group_by(mese)
            .order_by(mese)
        )
        return list((await self.session.execute(stmt)).all())
