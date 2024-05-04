import os

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
            callback_query.message.chat.id, 'Digite a URL do anúncio'
        )
        bot.register_next_step_handler(callback_query.message, on_ad_url)

    def on_ad_url(message):
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
        for website in ['mercadolivre', 'amazon', 'shopee', 'magazineluiza']:
            if website in message.text:
                functions = {
                    'mercadolivre': browser.get_mercado_livre_product_info,
                    'amazon': browser.get_amazon_product_info,
                    'magazineluiza': browser.get_magalu_product_info,
                }
                info = functions[website](message.text)
                with Session() as session:
                    query = select(User).where(
                        User.username == message.chat.username
                    )
                    user_model = session.scalars(query).first()
                    images_paths = {
                        'mercadolivre': (
                            user_model.mercado_livre_stories_image,
                            user_model.mercado_livre_feed_image,
                        ),
                        'amazon': (
                            user_model.amazon_stories_image,
                            user_model.amazon_feed_image,
                        ),
                        'magazineluiza': (
                            user_model.magalu_stories_image,
                            user_model.magalu_feed_image,
                        ),
                    }
                    images_paths = images_paths[website]
                story_image_path, feed_image_path = browser.generate_images(
                    info,
                    config['DOMAIN'] + images_paths[0],
                    config['DOMAIN'] + images_paths[1],
                )
                bot.delete_message(message.chat.id, generating_message.id)
                bot.send_message(message.chat.id, 'Segue imagem para Stories:')
                bot.send_photo(message.chat.id, open(story_image_path, 'rb'))
                bot.send_message(message.chat.id, 'Segue imagem para Feed:')
                bot.send_photo(message.chat.id, open(feed_image_path, 'rb'))
                os.remove(story_image_path)
                os.remove(feed_image_path)
                start(message)
                return
        bot.send_message(
            message.chat.id,
            'URL inválida, digite uma URL de alguns desses sites: Shopee, Mercado Livre, Amazon, Magalu',
        )
        start(message)
