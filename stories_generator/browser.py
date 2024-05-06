import os
import base64
from pathlib import Path
from time import sleep

import toml
import undetected_chromedriver as uc
from selenium.common.exceptions import (StaleElementReferenceException,
                                        TimeoutException)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


class Browser:
    def __init__(self, headless=True):
        self.driver = uc.Chrome(headless=headless, use_subprocess=False)
        self.driver.maximize_window()

    def get_amazon_product_info(self, url):
        self.driver.get(url)
        sleep(1)
        self.driver.refresh()
        try:
            installment = self.find_element('.best-offer-name').text
        except TimeoutException:
            installment = ''
        return {
            'name': self.find_element('#productTitle').text,
            'old_value': float(
                self.find_element('.a-size-small .a-offscreen')
                .get_attribute('textContent')[2:]
                .replace('.', '')
                .replace(',', '.')
            ),
            'value': float(
                self.find_element('.a-price-whole')
                .text.replace('.', '')
                .replace(',', '.')
            ),
            'installment': installment,
            'image_url': self.find_element('#landingImage').get_attribute(
                'src'
            ),
            'url': self.driver.current_url,
        }

    def get_mercado_livre_product_info(self, url):
        self.driver.get(url)
        self.driver.refresh()
        try:
            name = self.find_element('.ui-pdp-title').text,
        except TimeoutException:
            self.find_element('.poly-component__title').click()
            name = self.find_element('.ui-pdp-title').text,
        return {
            'name': name,
            'old_value': float(
                self.find_element('.andes-money-amount__fraction')
                .text.replace('.', '')
                .replace(',', '.')
            ),
            'value': float(
                self.find_elements('.andes-money-amount__fraction')[1]
                .text.replace('.', '')
                .replace(',', '.')
            ),
            'installment': self.find_element('.ui-pdp-price__subtitles')
            .text.replace('\n', ' ')
            .replace(' , ', ','),
            'image_url': self.find_element(
                '.ui-pdp-image.ui-pdp-gallery__figure__image'
            ).get_attribute('src'),
            'url': self.driver.current_url,
        }

    def get_magalu_product_info(self, url):
        self.driver.get(url)
        try:
            installment = self.find_element(
                'p[data-testid="installment"]'
            ).text
        except TimeoutException:
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
