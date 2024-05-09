from sqlalchemy import select

from stories_generator.database import Session
from stories_generator.models import Chat, TelegramUser


def init_bot(bot, start):
    @bot.message_handler(content_types=['new_chat_members'])
    def on_group_join(message):
        with Session() as session:
            query = select(TelegramUser).where(
                TelegramUser.username == message.from_user.username
            )
            user = session.scalars(query).first()
            if user:
                chat = Chat(
                    user=user,
                    chat_id=str(message.chat.id),
                    title=message.chat.title,
                )
                session.add(chat)
                session.commit()

    @bot.message_handler(content_types=['left_chat_member'])
    def on_group_left(message):
        with Session() as session:
            query = select(TelegramUser).where(
                TelegramUser.username == message.from_user.username
            )
            user = session.scalars(query).first()
            if user:
                query = (
                    select(Chat)
                    .where(Chat.user_id == user.id)
                    .where(Chat.chat_id == message.chat.id)
                )
                chat = session.scalars(query).first()
                if chat:
                    session.delete(chat)
                    session.commit()

    @bot.my_chat_member_handler()
    def on_channel_update(update):
        with Session() as session:
            query = select(TelegramUser).where(
                TelegramUser.username == update.from_user.username
            )
            user = session.scalars(query).first()
            if user:
                if update.new_chat_member.status == 'administrator':
                    chat = Chat(
                        user=user,
                        chat_id=str(update.chat.id),
                        title=update.chat.title,
                    )
                    session.add(chat)
                    session.commit()
                elif update.new_chat_member.status == 'kicked':
                    query = (
                        select(Chat)
                        .where(Chat.user_id == user.id)
                        .where(Chat.chat_id == update.chat.id)
                    )
                    chat = session.scalars(query).first()
                    if chat:
                        session.delete(chat)
                        session.commit()
