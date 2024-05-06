import base64
import os
import re
from pathlib import Path
from time import sleep

import toml
import undetected_chromedriver as uc
from httpx import get
from parsel import Selector
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


class Browser:
    def __init__(self, headless=True):
        self.driver = uc.Chrome(headless=headless, use_subprocess=False)
        self.driver.maximize_window()

    def get_amazon_product_info(self, url):
        response = get(url)
        selector = Selector(response.text)
        return {
            'name': selector.css('#productTitle::text').get().strip(),
            'old_value': float(
                selector.css('.a-size-small .a-offscreen::text')
                .get()[2:]
                .replace('.', '')
                .replace(',', '.')
            ),
            'value': float(
                selector.css('.a-price-whole::text')
                .get()
                .replace('.', '')
                .replace(',', '.')
            ),
            'installment': selector.css('.best-offer-name::text').get() or '',
            'image_url': selector.css('#landingImage').attrib['src'],
            'url': url,
        }

    def get_mercado_livre_product_info(self, url):
        response = get(url)
        selector = Selector(response.text)
        if not selector.css('.ui-pdp-title::text'):
            ad_url = selector.css('.poly-component__title').attrib['href']
            response = get(ad_url)
            selector = Selector(response.text)
        installment_selector = selector.css('#pricing_price_subtitle')
        if installment_selector:
            installment = ''
            for span in installment_selector.css('span::text'):
                installment += f'{span.get()} '
            installment = installment.replace(' , ', ',')
            installment = re.sub(
                'em ',
                'em ' + re.findall(r'\s(\d{2}+x)', response.text)[0] + ' ',
                installment,
            )
            if 'sem juros' in response.text:
                installment += 'sem juros'
        else:
            installment = ''
        old_value = float(
            selector.css('.andes-money-amount__fraction::text')
            .get()
            .replace('.', '')
            .replace(',', '.')
        )
        value = float(
            selector.css('.andes-money-amount__fraction::text')[1]
            .get()
            .replace('.', '')
            .replace(',', '.')
        )
        if old_value > value:
            value = old_value
            old_value = ''
        return {
            'name': selector.css('.ui-pdp-title::text').get(),
            'old_value': old_value,
            'value': value,
            'installment': installment,
            'image_url': selector.css(
                '.ui-pdp-image.ui-pdp-gallery__figure__image'
            ).attrib['src'],
            'url': url,
        }

    def get_magalu_product_info(self, url):
        self.driver.get(url)
        if self.driver.find_elements(
            By.CSS_SELECTOR, 'p[data-testid="installment"]'
        ):
            installment = self.find_element(
                'p[data-testid="installment"]'
            ).text
        else:
            installment = ''
        return {
            'name': self.find_element(
                'h1[data-testid="heading-product-title"]'
            ).text,
            'old_value': float(
                self.find_element('p[data-testid="price-original"]')
                .text[3:]
                .replace('.', '')
                .replace(',', '.')
            ),
            'value': float(
                self.find_element('p[data-testid="price-value"]')
                .text[3:]
                .replace('.', '')
                .replace(',', '.')
            ),
            'installment': installment,
            'image_url': self.find_element(
                'img[data-testid="image-selected-thumbnail"]'
            ).get_attribute('src'),
            'url': self.driver.current_url,
        }

    def generate_images(self, info, background_image_path):
        config = toml.load(open('.config.toml', 'r'))
        self.driver.get(config['MODEL_URL'])
        while True:
            try:
                for element in self.find_elements('span'):
                    if 'Título' in element.text:
                        name = (
                            info['name']
                            if len(info['name']) < 60
                            else info['name'][:50] + ' ...'
                        )
                        self.driver.execute_script(
                            'arguments[0].style.textWrap = "wrap"', element
                        )
                        self.driver.execute_script(
                            f'arguments[0].textContent = "{name}"', element
                        )
                    elif 'Preço original' in element.text:
                        value = f'{info["old_value"]:.2f}'.replace('.', ',')
                        self.driver.execute_script(
                            f'arguments[0].textContent = "R$ {value}"', element
                        )
                    elif 'Preço desconto' in element.text:
                        value = f'{info["value"]:.2f}'.replace('.', ',')
                        self.driver.execute_script(
                            f'arguments[0].textContent = "R$ {value}"', element
                        )
                    elif 'Parcelamento' in element.text:
                        self.driver.execute_script(
                            f'arguments[0].textContent = "{info["installment"]}"',
                            element,
                        )
                break
            except StaleElementReferenceException:
                continue
        looping = True
        for _ in range(5):
            try:
                for button in self.find_elements('button[type=button]'):
                    if 'cookies' in button.text:
                        button.click()
                        looping = False
                if not looping:
                    break
            except StaleElementReferenceException:
                sleep(1)
        image_element = self.find_elements('.bFnJ2A')[1]
        self.driver.execute_script(
            f'arguments[0].style.background = "url({info["image_url"]}) center center / contain no-repeat"',
            image_element,
        )
        self.driver.execute_script(
            'arguments[0].style.fill = "transparent"', image_element
        )
        self.find_element('body').click()
        sleep(5)
        background_element = self.find_element('.fbzKiw')
        with open(background_image_path, 'rb') as f:
            encoded_image = base64.b64encode(f.read())
        self.driver.execute_script(
            f'arguments[0].style.background = "url(data:image/png;base64,{encoded_image.decode()}) center center / contain no-repeat"',
            background_element,
        )
        stories_filename = f'{len(os.listdir(Path("static"))) + 1}.png'
        background_element.screenshot(str(Path('static') / stories_filename))
        sleep(1)
        feed_filename = f'{len(os.listdir(Path("static"))) + 1}.png'
        self.find_element('._0xkaeQ').screenshot(
            str(Path('static') / feed_filename)
        )
        return (
            Path('static') / stories_filename,
            Path('static') / feed_filename,
        )

    def find_element(self, selector, element=None, wait=10):
        return WebDriverWait(element or self.driver, wait).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )

    def find_elements(self, selector, element=None, wait=10):
        return WebDriverWait(element or self.driver, wait).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
        )

    def __del__(self):
        self.driver.quit()
