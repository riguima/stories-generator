import os

from stories_generator.browser import Browser

browser = Browser(headless=False)


def init_bot(bot, start):
    @bot.callback_query_handler(func=lambda c: c.data == 'generate_image')
    def generate_image(callback_query):
        bot.send_message(
            callback_query.message.chat.id, 'Digite a URL do anúncio'
        )
        bot.register_next_step_handler(callback_query.message, on_ad_url)

    def on_ad_url(message):
        for website in ['mercadolivre', 'amazon', 'shopee', 'magazineluiza']:
            if website in message.text:
                functions = {
                    'mercadolivre': browser.get_mercado_livre_product_info,
                    'amazon': browser.get_amazon_product_info,
                    'magazineluiza': browser.get_magalu_product_info,
                }
                info = functions[website](message.text)
                image_path = browser.generate_image(info)
                bot.send_photo(message.chat.id, open(image_path, 'rb'))
                os.remove(image_path)
                start(message)
                return
        bot.send_message(
            message.chat.id,
            'URL inválida, digite uma URL de alguns desses sites: Shopee, Mercado Livre, Amazon, Magalu',
        )
        start(message)
