import re
import secrets
import string
from datetime import timedelta
from importlib import import_module
from pathlib import Path

import telebot
import toml
from sqlalchemy import select
from telebot.util import quick_markup, update_types

from stories_generator.config import config
from stories_generator.database import Session
from stories_generator.models import Plan, Signature, TelegramUser, User
from stories_generator.utils import get_today_date

bot = telebot.TeleBot(config['BOT_TOKEN'])


@bot.message_handler(commands=['start', 'help', 'menu'])
def start(message):
    if message.chat.username:
        with Session() as session:
            query = select(TelegramUser).where(
                TelegramUser.username == message.chat.username
            )
            user_model = session.scalars(query).first()
            query = select(Plan).where(Plan.value == None)
            plan_model = session.scalars(query).first()
            if plan_model is None:
                plan_model = Plan(name='Plano Teste', days=0)
                session.add(plan_model)
                session.commit()
            if user_model is None:
                user_model = User(
                    username=message.chat.username,
                    password=''.join(
                        secrets.choice(string.ascii_letters + string.digits)
                        for _ in range(20)
                    ),
                    is_admin=True,
                )
                telegram_user_model = TelegramUser(
                    username=message.chat.username
                )
                session.add(user_model)
                session.add(telegram_user_model)
                session.flush()
                signature_model = Signature(
                    user_id=user_model.id,
                    plan_id=plan_model.id,
                    due_date=get_today_date()
                    + timedelta(days=plan_model.days),
                )
                session.add(signature_model)
                session.commit()
        options = {
            'Minhas Assinaturas': {
                'callback_data': f'show_signature:{message.chat.username}'
            },
            'Acesso do Site': {'callback_data': 'show_admin_login'},
            'Definir Bot Token': {'callback_data': 'set_bot_token'},
            'Layout': {'callback_data': 'show_layout'},
            'Gerar Imagens': {'callback_data': 'generate_images'},
        }
        if message.chat.id in config['ADMINS']:
            options['Alterar Plano Teste'] = {
                'callback_data': 'edit_test_plan'
            }
            options['Assinantes'] = {'callback_data': 'show_subscribers'}
            options['Editar Mensagem do Menu'] = {
                'callback_data': 'edit_menu_message'
            }
            options['Editar Imagem Padrão'] = {
                'callback_data': 'edit_background_image'
            }
            options['Adicionar Plano'] = {'callback_data': 'add_plan'}
            options['Planos'] = {'callback_data': 'show_plans'}
            options['Adicionar Membro'] = {'callback_data': 'add_member'}
            options['Membros'] = {'callback_data': 'show_members'}
        bot.send_message(
            message.chat.id,
            config['MENU_MESSAGE'].format(nome=message.chat.first_name),
            reply_markup=quick_markup(options, row_width=1),
        )
    else:
        bot.send_message(
            message.chat.id,
            'Adicione um arroba para sua conta do Telegram para utilizar esse bot',
        )


@bot.callback_query_handler(lambda c: c.data == 'show_admin_login')
def show_admin_login(callback_query):
    with Session() as session:
        query = select(User).where(
            User.username == callback_query.message.chat.username
        )
        user_model = session.scalars(query).first()
        bot.send_message(
            callback_query.message.chat.id,
            f'Link do Site: https://promodegrupo.com/{callback_query.message.chat.username}\n\nLink: https://promodegrupo.com/login\n\nLogin: {user_model.username}\nSenha: {user_model.password}',
            reply_markup=quick_markup(
                {
                    'Trocar Senha': {'callback_data': 'change_admin_password'},
                    'Voltar': {'callback_data': 'return_to_main_menu'},
                },
                row_width=1,
            ),
        )


@bot.callback_query_handler(lambda c: c.data == 'change_admin_password')
def change_admin_password(callback_query):
    bot.send_message(callback_query.message.chat.id, 'Digite a nova senha')
    bot.register_next_step_handler(callback_query.message, on_admin_password)


def on_admin_password(message):
    with Session() as session:
        query = select(User).where(User.username == message.chat.username)
        user_model = session.scalars(query).first()
        user_model.password = message.text
        session.commit()
        bot.send_message(message.chat.id, 'Senha Alterada!')
        start(message)


@bot.callback_query_handler(func=lambda c: c.data == 'show_subscribers')
def show_subscribers(callback_query):
    with Session() as session:
        users = session.scalars(select(TelegramUser)).all()
        actives = 0
        plans = ''
        for user_model in users:
            query = (
                select(Signature)
                .where(Signature.due_date >= get_today_date())
                .where(Signature.user_id == user_model.id)
            )
            signatures_models = session.scalars(query).all()
            if signatures_models:
                actives += 1
                for signature_model in signatures_models:
                    if signature_model.plan.name in plans:
                        pattern = signature_model.plan.name + r': \d+'
                        actives_in_plan = int(
                            re.findall(
                                signature_model.plan.name + r': (\d+)', plans
                            )[0]
                        )
                        plans = re.sub(
                            pattern,
                            f'{signature_model.plan.name}: {actives_in_plan + 1}',
                            plans,
                        )
                    else:
                        plans += f'\n{signature_model.plan.name}: 1'
        bot.send_message(
            callback_query.message.chat.id,
            f'Número de Usuários: {len(users)}\nAtivos: {actives}\nInativos: {len(users) - actives}\n{plans}',
            reply_markup=quick_markup(
                {'Voltar': {'callback_data': 'return_to_main_menu'}}
            ),
        )


@bot.callback_query_handler(func=lambda c: c.data == 'edit_menu_message')
def edit_menu_message(callback_query):
    bot.send_message(
        callback_query.message.chat.id,
        'Envie a mensagem que vai ficar no menu\n\nTags: {nome}',
    )
    bot.register_next_step_handler(callback_query.message, on_menu_message)


def on_menu_message(message):
    global config
    config['MENU_MESSAGE'] = message.text
    toml.dump(config, open('.config.toml', 'w'))
    bot.send_message(message.chat.id, 'Mensagem Editada!')
    start(message)


@bot.callback_query_handler(func=lambda c: c.data == 'edit_background_image')
def edit_background_image(callback_query):
    bot.send_message(
        callback_query.message.chat.id, 'Envie a nova imagem de fundo'
    )
    bot.register_next_step_handler(callback_query.message, on_background_image)


def on_background_image(message):
    if message.document:
        image = bot.get_file(message.document.file_id)
        valid_extensions = ['jpeg', 'jpg', 'png']
        if image.file_path.split('.')[-1].lower() not in valid_extensions:
            bot.send_message(
                message.chat.id, 'Imagem inválida, tente novamente'
            )
            bot.register_next_step_handler(message, on_background_image)
            return
        image_file = bot.download_file(image.file_path)
        with open(Path('static') / 'background.png', 'wb') as f:
            f.write(image_file)
        bot.send_message(message.chat.id, 'Imagem de Fundo Alterada!')
        start(message)
    else:
        bot.send_message(message.chat.id, 'Imagem inválida, tente novamente')
        bot.register_next_step_handler(message, on_background_image)


@bot.callback_query_handler(func=lambda c: c.data == 'return_to_main_menu')
def return_to_main_menu(callback_query):
    start(callback_query.message)


def load_extensions():
    for extension in config['EXTENSIONS']:
        extension_module = import_module(extension)
        extension_module.init_bot(bot, start)


if __name__ == '__main__':
    load_extensions()
    bot.infinity_polling(allowed_updates=update_types)
