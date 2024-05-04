import os
from pathlib import Path

import toml
from sqlalchemy import select
from telebot.util import quick_markup

from stories_generator.browser import Browser
from stories_generator.config import config
from stories_generator.database import Session
from stories_generator.models import Signature, User
from stories_generator.utils import get_today_date

browser = Browser(headless=False)


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
        bot.register_next_step_handler(callback_query.message, on_ad_url)

    def on_ad_url(message):
        bot.send_message(message.chat.id, 'Digite o link de afiliado')
        bot.register_next_step_handler(
            message, lambda m: on_affiliate_url(m, message.text)
        )

    def on_affiliate_url(message, ad_url):
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
        for website in [
            'mercadolivre',
            'amazon',
            'shopee',
            'magazineluiza',
            'magazinevoce',
        ]:
            if website in ad_url:
                functions = {
                    'mercadolivre': browser.get_mercado_livre_product_info,
                    'amazon': browser.get_amazon_product_info,
                    'magazineluiza': browser.get_magalu_product_info,
                    'magazinevoce': browser.get_magalu_product_info,
                }
                info = functions[website](ad_url)
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
                )
                bot.send_message(
                    message.chat.id,
                    'Escolha uma opção',
                    reply_markup=quick_markup(
                        {
                            'Editar': {
                                'callback_data': f'edit_feed_message_caption:{feed_image_path.name}'
                            },
                            'Enviar': {
                                'callback_data': f'send_feed:{feed_image_path.name}'
                            },
                            'Voltar': {
                                'callback_data': f'remove_feed_image_and_exit:{feed_image_path.name}'
                            },
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
        func=lambda c: 'edit_feed_message_caption:' in c.data
    )
    def edit_feed_message_caption(callback_query):
        feed_image_name = callback_query.data.split(':')[-1]
        bot.send_message(
            callback_query.message.chat.id, 'Envie a mensagem para o feed'
        )
        bot.register_next_step_handler(
            callback_query.message,
            lambda m: on_feed_message(m, feed_image_name),
        )

    def on_feed_message(message, feed_image_name):
        bot.send_photo(
            message.chat.id,
            open(Path('static') / feed_image_name, 'rb'),
            caption=message.text,
        )
        bot.send_message(
            message.chat.id,
            'Escolha uma opção',
            reply_markup=quick_markup(
                {
                    'Editar': {
                        'callback_data': f'edit_feed_message_caption:{feed_image_name}'
                    },
                    'Enviar': {
                        'callback_data': f'send_feed:{feed_image_name}'
                    },
                    'Voltar': {
                        'callback_data': f'remove_feed_image_and_exit:{feed_image_name}'
                    },
                },
                row_width=1,
            ),
        )

    @bot.callback_query_handler(
        func=lambda c: 'remove_feed_image_and_exit:' in c.data
    )
    def remove_feed_image_and_exit(callback_query):
        feed_image_name = callback_query.data.split(':')[-1]
        os.remove(Path('static') / feed_image_name)
        start(callback_query.message)
