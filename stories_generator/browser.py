from time import sleep
import toml
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


class Browser:
    def __init__(self, headless=True):
        self.driver = uc.Chrome(headless=headless, use_subprocess=False)

    def get_amazon_product_info(self, url):
        self.driver.get(url)
        sleep(1)
        self.driver.refresh()
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
            'installment': self.find_element('.best-offer-name').text,
            'image_url': self.find_element('#landingImage').get_attribute('src'),
            'url': self.driver.current_url,
        }

    def get_mercado_livre_product_info(self, url):
        self.driver.get(url)
        self.driver.refresh()
        return {
            'name': self.find_element('.ui-pdp-title').text,
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
            'image_url': self.find_element('.ui-pdp-image.ui-pdp-gallery__figure__image').get_attribute('src'),
            'url': self.driver.current_url,
        }

    def get_magalu_product_info(self, url):
        self.driver.get(url)
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
            'installment': self.find_element(
                'p[data-testid="installment"]'
            ).text,
            'image_url': self.find_element('img[data-testid="image-selected-thumbnail"]').get_attribute('src'),
            'url': self.driver.current_url,
        }

    def generate_image(self, info):
        config = toml.load(open('.config.toml', 'r'))
        self.driver.get(config['MODEL_URL'])
        for element in self.find_elements('span'):
            if element.text == 'Título':
                name = info['name'] if len(info['name']) < 50 else info['name'][:45] + ' ...'
                self.driver.execute_script(f'arguments[0].textContent = "{name}"', element)
            elif element.text == 'Preço original':
                self.driver.execute_script(f'arguments[0].textContent = "R$ {info["old_value"]:.2f}"'.replace('.', ','), element)
            elif element.text == 'Preço desconto':
                self.driver.execute_script(f'arguments[0].textContent = "R$ {info["value"]:.2f}"'.replace('.', ','), element)
            elif element.text == 'Parcelamento':
                self.driver.execute_script(f'arguments[0].textContent = "{info["installment"]}"', element)
        for element in self.find_elements('div'):
            if element.get_attribute('style') == 'z-index: 4;':
                self.driver.execute_script(f'arguments[0].style.background = "url({info["image_url"]}) center center / contain no-repeat"', element)
                self.driver.execute_script('arguments[0].style.fill = "transparent"', element)
                self.driver.execute_script('arguments[0].style.fill = "transparent"', self.find_element('path', element=element))
                sleep(3)
                self.find_element('img').screenshot('teste.png')

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
