import os
import re
from datetime import datetime, timedelta
from pathlib import Path

import telebot
import toml
from httpx import get
from sqlalchemy import select
from telebot.util import quick_markup

from stories_generator.browser import Browser
from stories_generator.config import config
from stories_generator.database import Session
from stories_generator.models import Chat, Product, Signature, TelegramUser
from stories_generator.utils import get_today_date

browser = Browser()

feed_messages = {}

FEED_REPLY_MARKUP = {
    'Editar Texto': {
        'callback_data': 'edit_feed_message_caption',
    },
    'Editar Informações': {
        'callback_data': 'edit_feed_infos',
    },
    'Inserir Cupom': {
        'callback_data': 'edit_feed_cupom',
    },
    'Editar Imagem de Fundo': {
        'callback_data': 'edit_feed_image',
    },
    'Enviar': {
        'callback_data': 'send_feed',
    },
    'Voltar': {
        'callback_data': 'delete_message_and_return',
    },
}


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
        bot.register_next_step_handler(
            callback_query.message, on_affiliate_url
        )

    def on_affiliate_url(message):
        with Session() as session:
            query = select(TelegramUser).where(
                TelegramUser.username == message.chat.username
            )
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
        response = get(message.text, follow_redirects=True)
        websites = [
            'mercadolivre',
            'magazineluiza',
            'magazinevoce',
            'amazon',
        ]
        url = None
        website = None
        for w in websites:
            if w in str(response.url):
                if w in ['magazineluiza', 'magazinevoce']:
                    website = 'magalu'
                else:
                    website = w
                url = str(response.url)
                break
        if response.status_code != 200 or url is None or website is None:
            bot.send_message(
                message.chat.id,
                'URL inválida, digite uma URL de alguns desses sites: Mercado Livre, Amazon, Magalu',
            )
            bot.delete_message(message.chat.id, generating_message.id)
            start(message)
            return
        functions = {
            'mercadolivre': browser.get_mercado_livre_product_info,
            'amazon': browser.get_amazon_product_info,
            'magalu': browser.get_magalu_product_info,
        }
        info = functions[website](message.text)
        with Session() as session:
            query = select(TelegramUser).where(
                TelegramUser.username == message.chat.username
            )
            user_model = session.scalars(query).first()
            images_paths = {
                'mercadolivre': user_model.mercado_livre_image,
                'amazon': user_model.amazon_image,
                'magalu': user_model.magalu_image,
            }
            image_path = images_paths[website]
            if image_path is None:
                bot.send_message(
                    message.chat.id,
                    'Você não fez upload de uma imagem, faça upload da imagem em "Layout"',
                    reply_markup=quick_markup(
                        {
                            'Voltar': {'callback_data': 'return_to_main_menu'},
                        },
                        row_width=1,
                    ),
                )
                bot.delete_message(message.chat.id, generating_message.id)
                return
        story_image_path, feed_image_path = browser.generate_images(
            info, image_path
        )
        bot.delete_message(message.chat.id, generating_message.id)
        try:
            old_value = f'R$ {info["old_value"]:.2f}'.replace('.', ',')
        except ValueError:
            old_value = ''
        with Session() as session:
            query = (
                select(Product)
                .where(Product.username == message.chat.username)
                .where(Product.url == message.text)
            )
            product = session.scalars(query).first()
            if product:
                session.delete(product)
            product = Product(
                username=message.chat.username,
                name=info['name'],
                formatted_old_value=old_value,
                formatted_value=f'R$ {info["value"]:.2f}'.replace('.', ','),
                installment=info['installment'],
                image_url=info['image_url'],
                url=message.text,
                website=website,
                create_datetime=datetime.now() - timedelta(hours=3),
            )
            session.add(product)
            session.commit()
            session.flush()
            bot.send_photo(
                message.chat.id,
                open(story_image_path, 'rb'),
                caption=f'Story gerado ✨🖼️✨\nLink: {config["DOMAIN"]}/{message.chat.username}/produto/{product.id}',
            )
            caption = user_model.text_model.format(
                nome=info['name'],
                valor_antigo=f'~{old_value}~',
                valor=f'R$ {info["value"]:.2f}'.replace('.', ','),
                parcelamento=info['installment'],
                link=f'{config["DOMAIN"]}/{message.chat.username}/produto/{product.id}',
            )
            caption = (
                caption.replace('.', '\\.')
                .replace('+', '\\+')
                .replace(')', '\\)')
                .replace('(', '\\(')
                .replace('-', '\\-')
                .replace('_', '\\_')
                .replace('|', '\\|')
                .replace('*', '\\*')
                .replace('!', '\\!')
            )
            if not info['installment']:
                caption = caption.replace('\n💳', '')
            feed_messages[message.chat.username] = [
                bot.send_photo(
                    message.chat.id,
                    open(feed_image_path, 'rb'),
                    caption=caption,
                    parse_mode='MarkdownV2',
                ),
                feed_image_path,
                info,
                product.id,
                image_path,
            ]
            bot.send_message(
                message.chat.id,
                'Escolha uma opção',
                reply_markup=quick_markup(FEED_REPLY_MARKUP, row_width=1),
            )
            os.remove(story_image_path)

    @bot.callback_query_handler(
        func=lambda c: c.data == 'edit_feed_message_caption'
    )
    def edit_feed_message_caption(callback_query):
        bot.send_message(
            callback_query.message.chat.id, 'Envie a mensagem para o feed'
        )
        bot.register_next_step_handler(callback_query.message, on_feed_message)

    def on_feed_message(message):
        _, feed_image_path = browser.generate_images(feed_messages[message.chat.username][2], feed_messages[message.chat.username][-1])
        caption = (
            message.text.replace('.', '\\.')
            .replace('+', '\\+')
            .replace(')', '\\)')
            .replace('(', '\\(')
            .replace('-', '\\-')
            .replace('_', '\\_')
            .replace('|', '\\|')
            .replace('*', '\\*')
            .replace('!', '\\!')
        )
        feed_messages[message.chat.username][0] = bot.send_photo(
            message.chat.id,
            open(feed_image_path, 'rb'),
            caption=caption,
            parse_mode='MarkdownV2',
        )
        bot.send_message(
            message.chat.id,
            'Escolha uma opção',
            reply_markup=quick_markup(FEED_REPLY_MARKUP, row_width=1),
        )

    @bot.callback_query_handler(func=lambda c: c.data == 'edit_feed_infos')
    def edit_feed_infos(callback_query):
        bot.send_message(
            callback_query.message.chat.id, 'Envie o Valor Antigo (Digite 0 para pular)'
        )
        bot.register_next_step_handler(
            callback_query.message, on_feed_old_value
        )

    def on_feed_old_value(message):
        global feed_messages
        try:
            old_value = float(message.text.replace(',', '.'))
            if old_value == 0:
                feed_messages[message.chat.username][2]['old_value'] = ''
            else:
                feed_messages[message.chat.username][2]['old_value'] = old_value
            bot.send_message(message.chat.id, 'Envie o Valor Atual (Digite 0 para pular)')
            bot.register_next_step_handler(message, on_feed_value)
        except ValueError:
            bot.send_message(
                message.chat.id,
                'Valor inválido, digite um número como no exemplo: 10,50 ou 19,99',
            )
            bot.register_next_step_handler(message, on_feed_old_value)

    def on_feed_value(message):
        global feed_messages
        try:
            value = float(message.text.replace(',', '.'))
            if value == 0:
                feed_messages[message.chat.username][2]['value'] = ''
            else:
                feed_messages[message.chat.username][2]['value'] = value
            bot.send_message(message.chat.id, 'Envie o Parcelamento (Digite 0 para pular)')
            bot.register_next_step_handler(message, on_feed_installment)
        except ValueError:
            bot.send_message(
                message.chat.id,
                'Valor inválido, digite um número como no exemplo: 10,50 ou 19,99',
            )
            bot.register_next_step_handler(message, on_feed_value)

    def on_feed_installment(message):
        global feed_messages
        if message.text == '0':
            feed_messages[message.chat.username][2]['installment'] = ''
        else:
            feed_messages[message.chat.username][2]['installment'] = message.text
        show_feed_message(message)

    @bot.callback_query_handler(func=lambda c: c.data == 'edit_feed_cupom')
    def edit_feed_cupom(callback_query):
        bot.send_message(callback_query.message.chat.id, 'Envie o Cupom')
        bot.register_next_step_handler(callback_query.message, on_feed_cupom)

    def on_feed_cupom(message):
        global feed_messages
        feed_messages[message.chat.username][2]['cupom'] = message.text
        show_feed_message(message)

    def show_feed_message(message):
        with Session() as session:
            query = select(TelegramUser).where(
                TelegramUser.username == message.chat.username
            )
            user_model = session.scalars(query).first()
            info = feed_messages[message.chat.username][2]
            try:
                old_value = f'R$ {info["old_value"]:.2f}'.replace('.', ',')
            except ValueError:
                old_value = ''
            query = (
                select(Product)
                .where(Product.username == message.chat.username)
                .where(Product.url == info['url'])
            )
            product = session.scalars(query).first()
            product.formatted_old_value = old_value
            product.formatted_value = f'R$ {info["value"]:.2f}'.replace('.', ',')
            product.installment = info['installment']
            session.commit()
            caption = user_model.text_model.format(
                nome=info['name'],
                valor_antigo=f'~{old_value}~',
                valor=f'R$ {info["value"]:.2f}'.replace('.', ','),
                parcelamento=info['installment'],
                link=f'{config["DOMAIN"]}/{message.chat.username}/produto/{feed_messages[message.chat.username][3]}',
            )
            caption = (
                caption.replace('.', '\\.')
                .replace('+', '\\+')
                .replace(')', '\\)')
                .replace('(', '\\(')
                .replace('-', '\\-')
                .replace('_', '\\_')
                .replace('|', '\\|')
                .replace('*', '\\*')
                .replace('!', '\\!')
            )
            if info.get('cupom'):
                caption = re.sub(r'\n\n👉', f'\n🎟️ {info["cupom"]}\n\n', caption)
            if not info['installment']:
                caption = caption.replace('\n💳', '')
            story_image_path, feed_image_path = browser.generate_images(feed_messages[message.chat.username][2], feed_messages[message.chat.username][-1])
            bot.send_photo(
                message.chat.id,
                open(story_image_path, 'rb'),
                caption=f'Story gerado ✨🖼️✨\nLink: {config["DOMAIN"]}/{message.chat.username}/produto/{feed_messages[message.chat.username][-2]}',
            )
            feed_messages[message.chat.username][0] = bot.send_photo(
                message.chat.id,
                open(feed_image_path, 'rb'),
                caption=caption,
                parse_mode='MarkdownV2',
            )
            bot.send_message(
                message.chat.id,
                'Escolha uma opção',
                reply_markup=quick_markup(FEED_REPLY_MARKUP, row_width=1),
            )

    @bot.callback_query_handler(func=lambda c: c.data == 'edit_feed_image')
    def edit_feed_image(callback_query):
        bot.send_photo(
            callback_query.message.chat.id,
            open(Path('static') / 'send_as_document.png', 'rb'),
            caption='Envie a imagem como documento',
            reply_markup=quick_markup(
                {
                    'Voltar': {'callback_data': 'delete_message_and_return'},
                }
            ),
        )
        bot.register_next_step_handler(callback_query.message, on_feed_image)

    def on_feed_image(message):
        global feed_messages
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
                bot.register_next_step_handler(message, on_feed_image)
                return
            image_file = bot.download_file(image.file_path)
            image_path = (
                Path('static')
                / f'{image.file_id}.{image.file_path.split(".")[-1]}'
            )
            with open(image_path, 'wb') as f:
                f.write(image_file)
            feed_messages[message.chat.username][-1] = image_path
            show_feed_message(message)

    @bot.callback_query_handler(func=lambda c: c.data == 'send_feed')
    def send_feed(callback_query):
        reply_markup = {}
        with Session() as session:
            query = select(TelegramUser).where(
                TelegramUser.username == callback_query.message.chat.username
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
            query = select(TelegramUser).where(
                TelegramUser.username == callback_query.message.chat.username
            )
            user_model = session.scalars(query).first()
            if user_model.bot_token:
                user_bot = telebot.TeleBot(user_model.bot_token)
                info = feed_messages[callback_query.message.chat.username][2]
                try:
                    old_value = f'R$ {info["old_value"]:.2f}'.replace('.', ',')
                except ValueError:
                    old_value = ''
                query = (
                    select(Product)
                    .where(Product.username == callback_query.message.chat.username)
                    .where(Product.url == info['url'])
                )
                product = session.scalars(query).first()
                caption = user_model.text_model.format(
                    nome=info['name'],
                    valor_antigo=f'~{old_value}~',
                    valor=f'R$ {info["value"]:.2f}'.replace('.', ','),
                    parcelamento=info['installment'],
                    link=f'{config["DOMAIN"]}/{callback_query.message.chat.username}/produto/{product.id}',
                )
                caption = (
                    caption.replace('.', '\\.')
                    .replace('+', '\\+')
                    .replace(')', '\\)')
                    .replace('(', '\\(')
                    .replace('-', '\\-')
                    .replace('_', '\\_')
                    .replace('|', '\\|')
                    .replace('*', '\\*')
                    .replace('!', '\\!')
                )
                if not info['installment']:
                    caption = caption.replace('\n💳', '')
                _, feed_image_path = browser.generate_images(feed_messages[callback_query.message.chat.username][2], feed_messages[callback_query.message.chat.username][-1])
                user_bot.send_photo(
                    int(chat.chat_id),
                    open(feed_image_path, 'rb'),
                    caption=caption,
                    parse_mode='MarkdownV2',
                )
                bot.send_message(
                    callback_query.message.chat.id, 'Feed Enviado!'
                )
            else:
                bot.send_message(
                    callback_query.message.chat.id,
                    'Defina primeiro o Bot Token para fazer o envio do feed',
                )
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

    @bot.callback_query_handler(func=lambda c: c.data == 'set_bot_token')
    def set_bot_token(callback_query):
        bot.send_message(
            callback_query.message.chat.id,
            'Envie o Token do Bot que enviará os feed nos grupos ou canais',
        )
        bot.register_next_step_handler(callback_query.message, on_bot_token)

    def on_bot_token(message):
        with Session() as session:
            query = select(TelegramUser).where(
                TelegramUser.username == message.chat.username
            )
            user = session.scalars(query).first()
            user.bot_token = message.text
            session.commit()
            bot.send_message(message.chat.id, 'Bot Token Definido!')
            start(message)
