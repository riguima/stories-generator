from importlib import import_module

import telebot
import toml
from sqlalchemy import select
from telebot.util import quick_markup, update_types

from stories_generator.config import config
from stories_generator.database import Session
from stories_generator.models import TelegramUser

bot = telebot.TeleBot(config['BOT_TOKEN'])


@bot.message_handler(commands=['start', 'help', 'menu'])
def start(message):
    if message.chat.username:
        with Session() as session:
            query = select(TelegramUser).where(TelegramUser.username == message.chat.username)
            user_model = session.scalars(query).first()
            if user_model is None:
                user_model = TelegramUser(username=message.chat.username)
                session.add(user_model)
                session.commit()
                session.flush()
        options = {
            'Minhas Assinaturas': {
                'callback_data': f'show_signature:{message.chat.username}'
            },
            'Layout': {'callback_data': 'show_layout'},
            'Gerar Imagens': {'callback_data': 'generate_images'},
        }
        if message.chat.id in config['ADMINS']:
            options['Editar Mensagem do Menu'] = {
                'callback_data': 'edit_menu_message'
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
