from pathlib import Path

from sqlalchemy import select
from telebot.util import quick_markup

from stories_generator.database import Session
from stories_generator.models import User


def init_bot(bot, start):
    @bot.callback_query_handler(func=lambda c: c.data == 'show_layout')
    def show_layout(callback_query):
        bot.send_message(
            callback_query.message.chat.id,
            'Escolha uma opção',
            reply_markup=quick_markup(
                {
                    'Imagem Feed': {'callback_data': 'feed_image'},
                    'Imagem Stories': {'callback_data': 'stories_image'},
                    'Modelo do texto': {'callback_data': 'text_model'},
                    'Voltar': {'callback_data': 'return_to_main_menu'},
                },
                row_width=1,
            ),
        )

    @bot.callback_query_handler(func=lambda c: c.data == 'feed_image')
    def feed_image(callback_query):
        show_websites_menu(callback_query.message, 'upload_feed_image')

    @bot.callback_query_handler(func=lambda c: c.data == 'stories_image')
    def stories_image(callback_query):
        show_websites_menu(callback_query.message, 'upload_stories_image')

    @bot.callback_query_handler(func=lambda c: c.data == 'text_model')
    def text_model(callback_query):
        show_websites_menu(callback_query.message, 'edit_text_model')

    def show_websites_menu(message, action):
        bot.send_message(
            message.chat.id,
            'Escolha uma opção',
            reply_markup=quick_markup(
                {
                    'Shopee': {'callback_data': f'{action}:shopee'},
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

    @bot.callback_query_handler(func=lambda c: 'upload_feed_image:' in c.data)
    def upload_feed_image(callback_query):
        with Session() as session:
            query = select(User).where(
                User.username == callback_query.message.chat.username
            )
            user_model = session.scalars(query).first()
        website = callback_query.data.split(':')[-1]
        feed_images = {
            'shopee': user_model.shopee_feed_image,
            'mercado_livre': user_model.mercado_livre_feed_image,
            'magalu': user_model.magalu_feed_image,
            'amazon': user_model.amazon_feed_image,
        }
        image = feed_images[website]
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
        bot.send_message(
            callback_query.message.chat.id,
            'Envie uma imagem para ficar como modelo',
            reply_markup=quick_markup(
                {
                    'Voltar': {'callback_data': 'return_to_main_menu'},
                }
            ),
        )
        bot.register_next_step_handler(
            callback_query.message, lambda m: on_feed_image(m, website)
        )

    def on_feed_image(message, website):
        if message.photo or message.document:
            if message.photo:
                image = bot.get_file(message.photo[0].file_id)
            else:
                image = bot.get_file(message.document.file_id)
            valid_extensions = ['jpeg', 'jpg', 'png']
            if image.file_path.split('.')[-1] not in valid_extensions:
                bot.send_message(
                    message.chat.id, 'Image inválida, tente novamente'
                )
                bot.register_next_step_handler(
                    message, lambda m: on_feed_image(m, website)
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
                query = select(User).where(
                    User.username == message.chat.username
                )
                user_model = session.scalars(query).first()
                if website == 'shopee':
                    user_model.shopee_feed_image = image_path
                elif website == 'mercado_livre':
                    user_model.mercado_livre_feed_image = image_path
                elif website == 'magalu':
                    user_model.magalu_feed_image = image_path
                elif website == 'amazon':
                    user_model.amazon_feed_image = image_path
                session.commit()
            bot.send_message(message.chat.id, 'Imagem Adicionada!')
            start(message)
        else:
            bot.send_message(
                message.chat.id, 'Image inválida, tente novamente'
            )
            bot.register_next_step_handler(
                message, lambda m: on_feed_image(m, website)
            )

    @bot.callback_query_handler(
        func=lambda c: 'upload_stories_image:' in c.data
    )
    def upload_stories_image(callback_query):
        with Session() as session:
            query = select(User).where(
                User.username == callback_query.message.chat.username
            )
            user_model = session.scalars(query).first()
        website = callback_query.data.split(':')[-1]
        stories_images = {
            'shopee': user_model.shopee_stories_image,
            'mercado_livre': user_model.mercado_livre_stories_image,
            'magalu': user_model.magalu_stories_image,
            'amazon': user_model.amazon_stories_image,
        }
        image = stories_images[website]
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
        bot.send_message(
            callback_query.message.chat.id,
            'Envie uma imagem para ficar como modelo',
            reply_markup=quick_markup(
                {
                    'Voltar': {'callback_data': 'return_to_main_menu'},
                }
            ),
        )
        bot.register_next_step_handler(
            callback_query.message, lambda m: on_stories_image(m, website)
        )

    def on_stories_image(message, website):
        if message.photo or message.document:
            if message.photo:
                image = bot.get_file(message.photo[0].file_id)
            else:
                image = bot.get_file(message.document.file_id)
            valid_extensions = ['jpeg', 'jpg', 'png']
            if image.file_path.split('.')[-1] not in valid_extensions:
                bot.send_message(
                    message.chat.id, 'Image inválida, tente novamente'
                )
                bot.register_next_step_handler(
                    message, lambda m: on_feed_image(m, website)
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
                query = select(User).where(
                    User.username == message.chat.username
                )
                user_model = session.scalars(query).first()
                if website == 'shopee':
                    user_model.shopee_stories_image = image_path
                elif website == 'mercado_livre':
                    user_model.mercado_livre_stories_image = image_path
                elif website == 'magalu':
                    user_model.magalu_stories_image = image_path
                elif website == 'amazon':
                    user_model.amazon_stories_image = image_path
                session.commit()
            bot.send_message(message.chat.id, 'Imagem Adicionada!')
            start(message)
        else:
            bot.send_message(
                message.chat.id, 'Image inválida, tente novamente'
            )
            bot.register_next_step_handler(
                message, lambda m: on_stories_image(m, website)
            )

    @bot.callback_query_handler(func=lambda c: 'edit_text_model:' in c.data)
    def edit_text_model(callback_query):
        bot.send_message(
            callback_query.message.chat.id,
            'Envie uma mensagem como no exemplo abaixo para trocar o modelo do texto, utilizando também as tags',
        )
        bot.send_message(
            callback_query.message.chat.id,
            '🔥{nome}\n\n{valor_antigo}\n💸{valor_atual}\n💳 {parcelamento}\n\n👉Link p/ comprar: {link}',
        )
        bot.register_next_step_handler(callback_query.message, on_text_model)

    def on_text_model(message):
        with Session() as session:
            query = select(User).where(User.username == message.chat.username)
            user_model = session.scalars(query).first()
            user_model.text_model = message.text
            session.commit()
            bot.send_message(message.chat.id, 'Texto Editado!')
            start(message)
