from importlib import import_module

import telebot
from sqlalchemy import select
from telebot.util import quick_markup

from stories_generator.config import config
from stories_generator.database import Session
from stories_generator.models import User

bot = telebot.TeleBot(config['BOT_TOKEN'])


@bot.message_handler(commands=['start', 'help', 'menu'])
def start(message):
    if message.chat.username:
        with Session() as session:
            query = select(User).where(User.username == message.chat.username)
            user_model = session.scalars(query).first()
            if user_model is None:
                user_model = User(username=message.chat.username)
                session.add(user_model)
                session.commit()
                session.flush()
        options = {
            'Minhas Assinaturas': {
                'callback_data': f'show_signature:{message.chat.username}'
            },
            'Layout': {'callback_data': 'show_layout'},
            'Gerar Imagem': {'callback_data': 'generate_image'},
        }
        if message.chat.id in config['ADMINS']:
            options['Adicionar Plano'] = {'callback_data': 'add_plan'}
            options['Planos'] = {'callback_data': 'show_plans'}
            options['Adicionar Membro'] = {'callback_data': 'add_member'}
            options['Membros'] = {'callback_data': 'show_members'}
        bot.send_message(
            message.chat.id,
            f'👋 Olá, {message.chat.first_name}!\n\n🤖 Seja bem-vindo ao nosso bot!\n\nAo adquirir sua assinatura, insira seu link de afiliado na aba "Gerar" e receba a 📷 imagem de feed/stories e texto personalizado com as informações de cada produto.\n\nPersonalize suas imagens em "Layout".\nA imagem deve ter as dimensões de 1080x1920.\n🎨 Modelo de exemplo: https://www.canva.com/design/DAGEAVUKg38/OsVaNPL9wxq9URHSFi-hdQ/view?\nAtente-se às margens e áreas seguras da imagem (será onde os textos personalizados serão adicionados).',
            reply_markup=quick_markup(options, row_width=1),
        )
    else:
        bot.send_message(
            message.chat.id,
            'Adicione um arroba para sua conta do Telegram para utilizar esse bot',
        )


@bot.callback_query_handler(func=lambda c: c.data == 'return_to_main_menu')
def return_to_main_menu(callback_query):
    start(callback_query.message)


def load_extensions():
    for extension in config['EXTENSIONS']:
        extension_module = import_module(extension)
        extension_module.init_bot(bot, start)


if __name__ == '__main__':
    load_extensions()
    bot.infinity_polling()
