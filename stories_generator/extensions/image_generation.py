import os

import toml
from sqlalchemy import select
from selenium.common.exceptions import InvalidArgumentException
from telebot.util import quick_markup

from stories_generator.browser import Browser
from stories_generator.config import config
from stories_generator.database import Session
from stories_generator.models import Chat, Signature, User
from stories_generator.utils import get_today_date

browser = Browser(headless=False)

feed_messages = {}


def init_bot(bot, start):
    @bot.callback_query_handler(func=lambda c: c.data == 'edit_model')
    def edit_model(callback_query):
        bot.send_message(
            callback_query.message.chat.id, 'Envie a URL do modelo'
        )
        bot.register_next_step_handler(callback_query.message, on_model_url)

    def on_model_url(message):
        global config
        config['MODEL_URL'] = message.text
        toml.dump(config, open('.config.toml', 'w'))
        bot.send_message(message.chat.id, 'Modelo Alterado!')
        start(message)

    @bot.callback_query_handler(func=lambda c: c.data == 'generate_images')
    def generate_images(callback_query):
        bot.send_message(
            callback_query.message.chat.id, 'Digite o link do anúncio'
        )
        bot.register_next_step_handler(callback_query.message, on_affiliate_url)

    def on_affiliate_url(message):
        with Session() as session:
            query = select(User).where(User.username == message.chat.username)
            user_model = session.scalars(query).first()
            query = (
                select(Signature)
                .where(Signature.user_id == user_model.id)
                .where(Signature.due_date >= get_today_date())
            )
            if not session.scalars(query).all():
                bot.send_message(
                    message.chat.id,
                    'Você não possui uma assinatura ativa',
                    reply_markup=quick_markup(
                        {
                            'Voltar': {'callback_data': 'return_to_main_menu'},
                        }
                    ),
                )
                return
        generating_message = bot.send_message(
            message.chat.id, 'Gerando Imagens...'
        )
        try:
            browser.driver.get(message.text)
        except InvalidArgumentException:
            bot.send_message(
                message.chat.id,
                'URL inválida, digite uma URL de alguns desses sites: Shopee, Mercado Livre, Amazon, Magalu',
            )
            bot.delete_message(message.chat.id, generating_message.id)
            start(message)
            return
        for website in [
            'mercadolivre',
            'amazon',
            'shopee',
            'magazineluiza',
            'magazinevoce',
        ]:
            if website in browser.driver.current_url:
                functions = {
                    'mercadolivre': browser.get_mercado_livre_product_info,
                    'amazon': browser.get_amazon_product_info,
                    'magazineluiza': browser.get_magalu_product_info,
                    'magazinevoce': browser.get_magalu_product_info,
                }
                info = functions[website](message.text)
                with Session() as session:
                    query = select(User).where(
                        User.username == message.chat.username
                    )
                    user_model = session.scalars(query).first()
                    images_paths = {
                        'mercadolivre': user_model.mercado_livre_image,
                        'amazon': user_model.amazon_image,
                        'magazineluiza': user_model.magalu_image,
                        'magazinevoce': user_model.magalu_image,
                    }
                    image_path = images_paths[website]
                    if image_path is None:
                        bot.send_message(
                            message.chat.id,
                            'Você não fez upload de uma imagem, faça upload da imagem em "Layout"',
                            reply_markup=quick_markup(
                                {
                                    'Voltar': {
                                        'callback_data': 'return_to_main_menu'
                                    },
                                },
                                row_width=1,
                            ),
                        )
                        bot.delete_message(
                            message.chat.id, generating_message.id
                        )
                        return
                story_image_path, feed_image_path = browser.generate_images(
                    info,
                    config['DOMAIN'] + image_path,
                )
                bot.delete_message(message.chat.id, generating_message.id)
                bot.send_photo(
                    message.chat.id,
                    open(story_image_path, 'rb'),
                    caption=f'Story gerado ✨🖼️✨\nLink: {message.text}',
                )
                feed_messages[message.chat.username] = [
                    bot.send_photo(
                        message.chat.id,
                        open(feed_image_path, 'rb'),
                        caption=user_model.text_model.format(
                            nome=info['name'],
                            valor_antigo=info['old_value'],
                            valor=info['value'],
                            parcelamento=info['installment'],
                            link=message.text,
                        ),
                    ),
                    feed_image_path,
                ]
                bot.send_message(
                    message.chat.id,
                    'Escolha uma opção',
                    reply_markup=quick_markup(
                        {
                            'Editar': {
                                'callback_data': 'edit_feed_message_caption'
                            },
                            'Enviar': {'callback_data': 'send_feed'},
                            'Voltar': {'callback_data': 'return_to_main_menu'},
                        },
                        row_width=1,
                    ),
                )
                os.remove(story_image_path)
                return
        bot.send_message(
            message.chat.id,
            'URL inválida, digite uma URL de alguns desses sites: Shopee, Mercado Livre, Amazon, Magalu',
        )
        bot.delete_message(message.chat.id, generating_message.id)
        start(message)

    @bot.callback_query_handler(
        func=lambda c: c.data == 'edit_feed_message_caption'
    )
    def edit_feed_message_caption(callback_query):
        bot.send_message(
            callback_query.message.chat.id, 'Envie a mensagem para o feed'
        )
        bot.register_next_step_handler(callback_query.message, on_feed_message)

    def on_feed_message(message):
        feed_messages[message.chat.username][0] = bot.send_photo(
            message.chat.id,
            open(feed_messages[message.chat.username][1], 'rb'),
            caption=message.text,
        )
        bot.send_message(
            message.chat.id,
            'Escolha uma opção',
            reply_markup=quick_markup(
                {
                    'Editar': {
                        'callback_data': 'edit_feed_message_caption',
                    },
                    'Enviar': {
                        'callback_data': 'send_feed',
                    },
                    'Voltar': {
                        'callback_data': 'delete_message_and_return',
                    },
                },
                row_width=1,
            ),
        )

    @bot.callback_query_handler(func=lambda c: c.data == 'send_feed')
    def send_feed(callback_query):
        reply_markup = {}
        with Session() as session:
            query = select(User).where(
                User.username == callback_query.message.chat.username
            )
            user = session.scalars(query).first()
            query = select(Chat).where(Chat.user_id == user.id)
            for chat in session.scalars(query).all():
                reply_markup[chat.title] = {
                    'callback_data': f'send_feed:{chat.id}'
                }
        reply_markup['Voltar'] = {'callback_data': 'delete_message_and_return'}
        bot.send_message(
            callback_query.message.chat.id,
            'Escolha um Grupo/Canal',
            reply_markup=quick_markup(reply_markup, row_width=1),
        )

    @bot.callback_query_handler(func=lambda c: 'send_feed:' in c.data)
    def send_feed_action(callback_query):
        chat_id = int(callback_query.data.split(':')[-1])
        with Session() as session:
            chat = session.get(Chat, chat_id)
            bot.send_photo(
                int(chat.chat_id),
                open(
                    feed_messages[callback_query.message.chat.username][1],
                    'rb',
                ),
                caption=feed_messages[callback_query.message.chat.username][
                    0
                ].caption,
            )
            bot.send_message(callback_query.message.chat.id, 'Feed Enviado!')
            os.remove(feed_messages[callback_query.message.chat.username][1])
            del feed_messages[callback_query.message.chat.username]
            start(callback_query.message)

    @bot.callback_query_handler(
        func=lambda c: c.data == 'delete_message_and_return'
    )
    def delete_message_and_return(callback_query):
        os.remove(feed_messages[callback_query.message.chat.username][1])
        del feed_messages[callback_query.message.chat.username]
        start(callback_query.message)
