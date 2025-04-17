import re
from datetime import timedelta

from sqlalchemy import select
from telebot.apihelper import ApiTelegramException
from telebot.util import quick_markup

from stories_generator.database import Session
from stories_generator.models import Plan, Signature, TelegramUser
from stories_generator.utils import get_plans_reply_markup, get_today_date


def init_bot(bot, start):
    @bot.callback_query_handler(func=lambda c: c.data == 'add_member')
    def add_member(callback_query):
        bot.send_message(callback_query.message.chat.id, 'Digite o arroba do membro')
        bot.register_next_step_handler(callback_query.message, on_username)

    def on_username(message):
        with Session() as session:
            user_model = TelegramUser(username=message.text)
            session.add(user_model)
            session.commit()
        bot.send_message(message.chat.id, 'Membro Adicionado!')
        start(message)

    @bot.callback_query_handler(func=lambda c: c.data == 'show_members')
    def show_members(callback_query):
        bot.send_message(
            callback_query.message.chat.id,
            'Membros',
            reply_markup=quick_markup(
                {
                    'Buscar Membros': {'callback_data': 'search_members'},
                    'Ver Membros': {'callback_data': 'see_members'},
                    'Voltar': {'callback_data': 'return_to_main_menu'},
                },
                row_width=1,
            ),
        )

    @bot.callback_query_handler(func=lambda c: c.data == 'see_members')
    def see_members(callback_query):
        with Session() as session:
            options = {}
            for user_model in session.scalars(select(TelegramUser)).all():
                options[user_model.username] = {
                    'callback_data': f'show_member:{user_model.username}'
                }
            options['Voltar'] = {'callback_data': 'return_to_main_menu'}
            bot.send_message(
                callback_query.message.chat.id,
                'Membros',
                reply_markup=quick_markup(options, row_width=1),
            )

    @bot.callback_query_handler(func=lambda c: c.data == 'search_members')
    def search_members(callback_query):
        bot.send_message(callback_query.message.chat.id, 'Digite o termo para busca')
        bot.register_next_step_handler(callback_query.message, on_search_term)

    def on_search_term(message):
        with Session() as session:
            options = {}
            options['Buscar Membros'] = {'callback_data': 'search_members'}
            for user_model in session.scalars(select(TelegramUser)).all():
                if message.text in user_model.username:
                    options[user_model.username] = {
                        'callback_data': f'show_member:{user_model.username}'
                    }
            options['Voltar'] = {'callback_data': 'return_to_main_menu'}
            bot.send_message(
                message.chat.id,
                'Membros',
                reply_markup=quick_markup(options, row_width=1),
            )

    @bot.callback_query_handler(func=lambda c: 'show_member:' in c.data)
    def show_members_action(callback_query):
        with Session() as session:
            username = callback_query.data.split(':')[-1]
            query = select(TelegramUser).where(TelegramUser.username == username)
            user_model = session.scalars(query).first()
            if user_model.signatures:
                send_member_menu(callback_query.message, user_model.signatures)
            else:
                bot.send_message(
                    callback_query.message.chat.id,
                    'Membro não possui uma assinatura ativa',
                    reply_markup=quick_markup(
                        {
                            'Adicionar Plano': {
                                'callback_data': (
                                    f'add_member_plan:{user_model.username}',
                                )
                            },
                            'Enviar Mensagem': {
                                'callback_data': f'send_message:{user_model.username}'
                            },
                            'Remover Membro': {
                                'callback_data': f'remove_member:{user_model.username}'
                            },
                            'Voltar': {'callback_data': 'return_to_main_menu'},
                        },
                        row_width=1,
                    ),
                )

    def send_member_menu(message, signatures_models):
        reply_markup = {}
        for signature_model in signatures_models:
            status = (
                'Ativa' if get_today_date() < signature_model.due_date else 'Inativa'
            )
            try:
                price = f'{signature_model.plan.value:.2f}'.replace('.', ',')
                label = (
                    f'Status: {status} - {signature_model.plan.name} - '
                    f'{signature_model.plan.days} Dias - R${price}'
                )
            except TypeError:
                label = (
                    f'Status: {status} - {signature_model.plan.name} - '
                    f'{signature_model.plan.days} Dias - Plano Teste'
                )
            reply_markup[label] = {
                'callback_data': f'show_member_signature:{signature_model.id}'
            }
        reply_markup['Adicionar Plano'] = {
            'callback_data': f'add_member_plan:{signatures_models[0].user.username}'
        }
        reply_markup['Enviar Mensagem'] = {
            'callback_data': f'send_message:{signatures_models[0].user.username}'
        }
        reply_markup['Remover Membro'] = {
            'callback_data': f'remove_member:{signatures_models[0].user.username}'
        }
        reply_markup['Voltar'] = {'callback_data': 'return_to_main_menu'}
        bot.send_message(
            message.chat.id,
            'Escolha uma opção',
            reply_markup=quick_markup(reply_markup, row_width=1),
        )

    @bot.callback_query_handler(func=lambda c: 'show_member_signature:' in c.data)
    def show_member_signature(callback_query):
        signature_id = int(callback_query.data.split(':')[-1])
        with Session() as session:
            signature_model = session.get(Signature, signature_id)
            status = (
                'Ativa' if get_today_date() <= signature_model.due_date else 'Inativa'
            )
            try:
                price = f'{signature_model.plan.value:.2f}'.replace('.', ',')
                text = (
                    f'Status: {status} - {signature_model.plan.name} - '
                    f'{signature_model.plan.days} Dias - R${price}\n\n'
                    f'Vencimento do plano: {signature_model.due_date:%d/%m/%Y}\n\n'
                    'Deseja cancelar essa assinatura?'
                )
            except TypeError:
                text = (
                    f'Status: {status} - {signature_model.plan.name} - '
                    f'{signature_model.plan.days} Dias - Plano Teste\n\n'
                    f'Vencimento do plano: {signature_model.due_date:%d/%m/%Y}\n\n'
                    'Deseja cancelar essa assinatura?'
                )
            bot.send_message(
                callback_query.message.chat.id,
                text,
                reply_markup=quick_markup(
                    {
                        'Sim': {'callback_data': f'cancel_signature:{signature_id}'},
                        'Não': {'callback_data': 'return_to_main_menu'},
                    },
                    row_width=1,
                ),
            )

    @bot.callback_query_handler(
        func=lambda c: bool(re.findall(r'add_member_plan:[^:]+$', c.data, re.DOTALL))
    )
    def add_member_plan(callback_query):
        username = callback_query.data.split(':')[-1]
        bot.send_message(
            callback_query.message.chat.id,
            'Escolha o plano',
            reply_markup=quick_markup(
                get_plans_reply_markup('add_member_plan', username),
                row_width=1,
            ),
        )

    @bot.callback_query_handler(
        func=lambda c: bool(re.findall(r'add_member_plan:.+?:.+?', c.data, re.DOTALL))
    )
    def add_member_plan_action(callback_query):
        plan_id, username = callback_query.data.split(':')[1:]
        bot.send_message(
            callback_query.message.chat.id,
            'Digite a quantidade de dias para o plano',
        )
        bot.register_next_step_handler(
            callback_query.message,
            lambda m: on_member_plan_days(m, plan_id, username),
        )

    def on_member_plan_days(message, plan_id, username):
        try:
            with Session() as session:
                query = select(TelegramUser).where(TelegramUser.username == username)
                user_model = session.scalars(query).first()
                plan_model = session.get(Plan, int(plan_id))
                signature_model = Signature(
                    user=user_model,
                    plan=plan_model,
                    due_date=get_today_date() + timedelta(days=int(message.text)),
                )
                session.add(signature_model)
                session.commit()
                if user_model.chat_id:
                    bot.send_message(
                        int(user_model.chat_id),
                        (
                            f'Olá, {user_model.username}.\n\n'
                            f'Adicionado {int(message.text)} dias para o plano '
                            f'{plan_model.name}.\n\nDigite /start e clique em '
                            '"Minhas assinaturas" para ter acesso a nova senha.',
                        )
                    )
            bot.send_message(message.chat.id, 'Plano Adicionado!')
        except ValueError:
            bot.send_message(
                message.chat.id,
                'Valor inválido, digite como no exemplo: 10 ou 15',
            )
        start(message)

    @bot.callback_query_handler(func=lambda c: 'send_message:' in c.data)
    def send_member_message(callback_query):
        username = callback_query.data.split(':')[-1]
        bot.send_message(
            callback_query.message.chat.id,
            (
                'Envie as mensagens que deseja enviar para o membro, utilize as tags: '
                '{nome}, digite /stop para parar',
            ),
        )
        bot.register_next_step_handler(
            callback_query.message, lambda m: on_member_message(m, username)
        )

    def on_member_message(message, username, for_send_messages=[]):
        if message.text == '/stop':
            sending_message = bot.send_message(message.chat.id, 'Enviando Mensagens...')
            with Session() as session:
                query = select(TelegramUser).where(TelegramUser.username == username)
                member = session.scalars(query).first()
                for for_send_message in for_send_messages:
                    try:
                        if member.chat_id:
                            bot.send_message(
                                str(member.chat_id),
                                for_send_message.text.format(nome=username),
                            )
                    except ApiTelegramException:
                        continue
            bot.delete_message(message.chat.id, sending_message.id)
            bot.send_message(message.chat.id, 'Mensagens Enviadas!')
            start(message)
        else:
            for_send_messages.append(message)
            bot.register_next_step_handler(
                message,
                lambda m: on_member_message(m, username, for_send_messages),
            )

    @bot.callback_query_handler(func=lambda c: 'remove_member:' in c.data)
    def remove_member_action(callback_query):
        with Session() as session:
            username = callback_query.data.split(':')[-1]
            query = select(TelegramUser).where(TelegramUser.username == username)
            user_model = session.scalars(query).first()
            session.delete(user_model)
            session.commit()
            bot.send_message(callback_query.message.chat.id, 'Membro Removido!')
            start(callback_query.message)
