from datetime import date, datetime, timedelta
from typing import List, Optional

from pytz import timezone
from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from stories_generator.database import db


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = 'products'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str]
    create_date: Mapped[Optional[date]] = mapped_column(
        default=datetime.now(timezone('America/Sao_Paulo')).date()
    )
    name: Mapped[str]
    formatted_old_value: Mapped[Optional[str]]
    formatted_value: Mapped[str]
    installment: Mapped[Optional[str]]
    image_url: Mapped[str]
    url: Mapped[str]
    website: Mapped[str]


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str]
    password: Mapped[str]
    authenticated: Mapped[Optional[bool]] = mapped_column(default=False)
    is_admin: Mapped[Optional[bool]] = mapped_column(default=False)

    @property
    def is_authenticated(self):
        return self.authenticated

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)


class TelegramUser(Base):
    __tablename__ = 'telegram_users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str]
    bot_token: Mapped[Optional[str]]
    mercado_livre_image: Mapped[Optional[str]] = mapped_column(
        default='static/background.png'
    )
    magalu_image: Mapped[Optional[str]] = mapped_column(
        default='static/background.png'
    )
    amazon_image: Mapped[Optional[str]] = mapped_column(
        default='static/background.png'
    )
    text_model: Mapped[Optional[str]] = mapped_column(
        default='🔥{nome}\n\n{valor_antigo}\n💸{valor}\n💳 {parcelamento}\n\n👉Link p/ comprar: {link}'
    )
    chats: Mapped[List['Chat']] = relationship(
        back_populates='user', cascade='all,delete-orphan'
    )
    signatures: Mapped[List['Signature']] = relationship(
        back_populates='user', cascade='all,delete-orphan'
    )
    payments: Mapped[List['Payment']] = relationship(
        back_populates='user', cascade='all,delete-orphan'
    )


class Chat(Base):
    __tablename__ = 'chats'
    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[str]
    title: Mapped[str]
    user: Mapped['TelegramUser'] = relationship(back_populates='chats')
    user_id: Mapped[int] = mapped_column(ForeignKey('telegram_users.id'))


class Signature(Base):
    __tablename__ = 'signatures'
    id: Mapped[int] = mapped_column(primary_key=True)
    user: Mapped['TelegramUser'] = relationship(back_populates='signatures')
    user_id: Mapped[int] = mapped_column(ForeignKey('telegram_users.id'))
    plan: Mapped['Plan'] = relationship(back_populates='signatures')
    plan_id: Mapped[int] = mapped_column(ForeignKey('plans.id'))
    payment_id: Mapped[Optional[str]]
    create_date: Mapped[Optional[date]] = mapped_column(
        default=(datetime.now() - timedelta(hours=3)).date()
    )
    due_date: Mapped[date]


class Plan(Base):
    __tablename__ = 'plans'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    value: Mapped[Optional[float]]
    days: Mapped[int]
    signatures: Mapped[List['Signature']] = relationship(
        back_populates='plan', cascade='all,delete-orphan'
    )


class Payment(Base):
    __tablename__ = 'payments'
    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[str]
    user: Mapped['TelegramUser'] = relationship(back_populates='payments')
    user_id: Mapped[int] = mapped_column(ForeignKey('telegram_users.id'))
    chat_id: Mapped[str]


Base.metadata.create_all(db)
