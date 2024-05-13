from pathlib import Path

from sqlalchemy import select
from telebot.util import quick_markup

from stories_generator.database import Session
from stories_generator.models import TelegramUser


def init_bot(bot, start):
    @bot.callback_query_handler(func=lambda c: c.data == 'show_layout')
    def show_layout(callback_query):
        bot.send_message(
            callback_query.message.chat.id,
            'Escolha uma opção',
            reply_markup=quick_markup(
                {
                    'Imagem': {'callback_data': 'image'},
                    'Modelo do texto': {'callback_data': 'text_model'},
                    'Voltar': {'callback_data': 'return_to_main_menu'},
                },
                row_width=1,
            ),
        )

    @bot.callback_query_handler(func=lambda c: c.data == 'image')
    def image(callback_query):
        show_websites_menu(callback_query.message, 'upload_image')

    @bot.callback_query_handler(func=lambda c: c.data == 'text_model')
    def text_model(callback_query):
        show_websites_menu(callback_query.message, 'edit_text_model')

    def show_websites_menu(message, action):
        bot.send_message(
            message.chat.id,
            'Escolha uma opção',
            reply_markup=quick_markup(
                {
                    'Mercado Livre': {
                        'callback_data': f'{action}:mercado_livre'
                    },
                    'Magalu': {'callback_data': f'{action}:magalu'},
                    'Amazon': {'callback_data': f'{action}:amazon'},
                    'Voltar': {'callback_data': 'return_to_main_menu'},
                },
                row_width=1,
            ),
        )

    @bot.callback_query_handler(func=lambda c: 'upload_image:' in c.data)
    def upload_image(callback_query):
        with Session() as session:
            query = select(TelegramUser).where(
                TelegramUser.username == callback_query.message.chat.username
            )
            user_model = session.scalars(query).first()
        website = callback_query.data.split(':')[-1]
        images = {
            'mercado_livre': user_model.mercado_livre_image,
            'magalu': user_model.magalu_image,
            'amazon': user_model.amazon_image,
        }
        image = images[website]
        if image:
            bot.send_message(
                callback_query.message.chat.id, 'A imagem atual é essa:'
            )
            bot.send_photo(callback_query.message.chat.id, open(image, 'rb'))
        else:
            bot.send_message(
                callback_query.message.chat.id,
                'Você ainda não fez upload de uma imagem',
            )
        bot.send_photo(
            callback_query.message.chat.id,
            open(Path('static') / 'send_as_document.png', 'rb'),
            caption='Envie a imagem como documento para ficar como modelo',
            reply_markup=quick_markup(
                {
                    'Voltar': {'callback_data': 'return_to_main_menu'},
                }
            ),
        )
        bot.register_next_step_handler(
            callback_query.message, lambda m: on_image(m, website)
        )

    def on_image(message, website):
        if message.document:
            image = bot.get_file(message.document.file_id)
            valid_extensions = ['jpeg', 'jpg', 'png']
            if image.file_path.split('.')[-1].lower() not in valid_extensions:
                bot.send_message(
                    message.chat.id,
                    'Imagem inválida, tente novamente',
                    reply_markup=quick_markup(
                        {'Voltar': {'callback_data': 'return_to_main_menu'}}
                    ),
                )
                bot.register_next_step_handler(
                    message, lambda m: on_image(m, website)
                )
                return
            image_file = bot.download_file(image.file_path)
            image_path = str(
                Path('static')
                / f'{image.file_id}.{image.file_path.split(".")[-1]}'
            )
            with open(image_path, 'wb') as f:
                f.write(image_file)
            with Session() as session:
                query = select(TelegramUser).where(
                    TelegramUser.username == message.chat.username
                )
                user_model = session.scalars(query).first()
                if website == 'mercado_livre':
                    user_model.mercado_livre_image = image_path
                elif website == 'magalu':
                    user_model.magalu_image = image_path
                elif website == 'amazon':
                    user_model.amazon_image = image_path
                session.commit()
            bot.send_message(message.chat.id, 'Imagem Adicionada!')
            start(message)
        else:
            bot.send_message(
                message.chat.id, 'Imagem inválida, tente novamente'
            )
            bot.register_next_step_handler(
                message, lambda m: on_image(m, website)
            )

    @bot.callback_query_handler(func=lambda c: 'edit_text_model:' in c.data)
    def edit_text_model(callback_query):
        bot.send_message(
            callback_query.message.chat.id,
            'Envie uma mensagem como no exemplo abaixo para trocar o modelo do texto, utilizando também as tags',
        )
        bot.send_message(
            callback_query.message.chat.id,
            '🔥{nome}\n\n{valor_antigo}\n💸{valor}\n💳 {parcelamento}\n\n👉Link p/ comprar: {link}',
        )
        bot.register_next_step_handler(callback_query.message, on_text_model)

    def on_text_model(message):
        with Session() as session:
            query = select(TelegramUser).where(
                TelegramUser.username == message.chat.username
            )
            user_model = session.scalars(query).first()
            user_model.text_model = message.text
            session.commit()
            bot.send_message(message.chat.id, 'Texto Editado!')
            start(message)
