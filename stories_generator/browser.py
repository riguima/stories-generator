import os
import textwrap
from pathlib import Path
from uuid import uuid4

import undetected_chromedriver as uc
from httpx import get
from PIL import Image, ImageDraw, ImageFont
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


class Browser:
    def __init__(self):
        self.driver = uc.Chrome(headless=True, use_subprocess=False)

    def get_amazon_product_info(self, url):
        self.driver.get(url)
        self.driver.refresh()
        if self.driver.find_elements(By.CSS_SELECTOR, '.best-offer-name'):
            installment = self.find_element('.best-offer-name').text
        else:
            installment = ''
        if self.driver.find_elements(By.CSS_SELECTOR, '.a-text-price'):
            old_value = float(
                self.find_element('.a-text-price')
                .text[2:]
                .replace('.', '')
                .replace(',', '.')
            )
        else:
            old_value = ''
        return {
            'name': self.find_element('#productTitle').text.strip(),
            'old_value': old_value,
            'value': float(
                self.find_element('.a-price-whole')
                .text.replace('.', '')
                .replace(',', '.')
            ),
            'installment': installment,
            'image_url': self.find_element('#landingImage').get_attribute(
                'data-old-hires'
            ),
            'url': url,
        }

    def get_mercado_livre_product_info(self, url):
        self.driver.get(url)
        self.driver.refresh()
        if not self.driver.find_elements(By.CSS_SELECTOR, '.ui-pdp-title'):
            self.driver.get(
                self.find_element('.poly-component__title').get_attribute(
                    'href'
                )
            )
        if self.driver.find_elements(
            By.CSS_SELECTOR, '.ui-pdp-price__original-value'
        ):
            old_value = float(
                self.find_element('.andes-money-amount__fraction')
                .text.replace('.', '')
                .replace(',', '.')
            )
        else:
            old_value = ''
        value = float(
            self.find_element('meta[itemprop=price]').get_attribute('content')
        )
        if self.driver.find_elements(
            By.CSS_SELECTOR, '.ui-pdp-price__subtitles'
        ):
            installment = self.find_element('.ui-pdp-price__subtitles').text
            installment = installment.replace('\n', ' ').replace(' , ', ',')
        else:
            installment = ''
        return {
            'name': self.find_element('.ui-pdp-title').text,
            'old_value': old_value,
            'value': value,
            'installment': installment,
            'image_url': self.find_element(
                '.ui-pdp-image.ui-pdp-gallery__figure__image'
            ).get_attribute('src'),
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
        stories_image = Image.open(background_image_path)
        filename = f'product-image.{info["image_url"].split(".")[-1]}'
        with open(filename, 'wb') as f:
            response = get(info['image_url'])
            f.write(response.content)
        product_image = Image.open(filename)
        if product_image.height < 650:
            product_image = product_image.resize(
                (product_image.width * 2, product_image.height * 2)
            )
        product_image.thumbnail((900, 650), Image.Resampling.LANCZOS)
        stories_image.paste(
            product_image,
            (
                stories_image.width // 2 - product_image.width // 2,
                350 + (650 // 2 - product_image.height // 2),
            ),
        )
        bold_font = ImageFont.truetype(
            str(Path('fonts') / 'arial-bold.ttf'), 100
        )
        font = ImageFont.truetype(str(Path('fonts') / 'arial.ttf'), 60)
        small_font = ImageFont.truetype(str(Path('fonts') / 'arial.ttf'), 50)
        draw = ImageDraw.Draw(stories_image)
        name = (
            info['name']
            if len(info['name']) < 50
            else info['name'][:40] + '...'
        )
        lines = textwrap.wrap(name, width=30)
        result_name = ''
        for line in lines:
            result_name += line + '\n'
        name_coords = (80, 1030)
        draw.text(name_coords, result_name, font=font, fill=(0, 0, 0))
        try:
            old_value = f'R$ {info["old_value"]:.2f}'.replace('.', ',')
        except ValueError:
            old_value = ''
        draw.text(
            (80, name_coords[1] + 140),
            old_value,
            font=small_font,
            fill=(100, 100, 100),
        )
        width = draw.textlength(old_value, font=font) - 30
        height = 50
        draw.line(
            (
                80,
                name_coords[1] + 140 + height // 2,
                80 + width,
                name_coords[1] + 140 + height // 2,
            ),
            fill=(100, 100, 100),
            width=2,
        )
        value = f'R$ {info["value"]:.2f}'.replace('.', ',')
        draw.text(
            (80, name_coords[1] + 190),
            value,
            font=bold_font,
            fill=(0, 0, 0),
        )
        lines = textwrap.wrap(info['installment'], width=40)
        result_installment = ''
        for line in lines:
            result_installment += line + '\n'
        draw.text(
            (80, name_coords[1] + 300),
            result_installment,
            font=small_font,
            fill=(0, 0, 0),
        )
        stories_filename = str(Path('static') / f'{uuid4()}.png')
        stories_image.save(stories_filename)
        feed_image = stories_image.crop((0, 300, 1080, 1500))
        feed_filename = str(Path('static') / f'{uuid4()}.png')
        feed_image.save(feed_filename)
        os.remove(filename)
        return stories_filename, feed_filename

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
