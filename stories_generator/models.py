from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from stories_generator.database import db


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str]
    shopee_image: Mapped[Optional[str]]
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
    user: Mapped['User'] = relationship(back_populates='chats')
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))


class Signature(Base):
    __tablename__ = 'signatures'
    id: Mapped[int] = mapped_column(primary_key=True)
    user: Mapped['User'] = relationship(back_populates='signatures')
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
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
    value: Mapped[float]
    days: Mapped[int]
    signatures: Mapped[List['Signature']] = relationship(
        back_populates='plan', cascade='all,delete-orphan'
    )


class Payment(Base):
    __tablename__ = 'payments'
    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[str]
    user: Mapped['User'] = relationship(back_populates='payments')
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    chat_id: Mapped[str]


Base.metadata.create_all(db)
