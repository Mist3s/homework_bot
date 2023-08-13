import os
import time
import logging

import requests
from telegram import Bot
from dotenv import load_dotenv

load_dotenv('.env')

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s, %(levelname)s, %(name)s, %(message)s',
    level=logging.DEBUG,
    filename='main.log'
)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if (PRACTICUM_TOKEN or TELEGRAM_TOKEN or TELEGRAM_CHAT_ID) is None:
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение отправлено')
    except ConnectionError:
        logging.error('Бот не смог отправить сообщение')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса Практикум.Домашка."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        response.json()
    except requests.exceptions.RequestException as er:
        logging.error(er)
    if response.status_code != 200:
        raise ConnectionError('Ошибка ответа API')
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if type(response) != dict:
        raise TypeError('Неверный тип данных в ответе API.')
    if response.get('current_date') is None:
        raise KeyError('В ответе API нет ключа current_date')
    if response.get('homeworks') is None:
        raise KeyError('В ответе API нет ключа homeworks')
    if type(response['homeworks']) != list \
            or type(response['current_date']) != int:
        raise TypeError('Неверный тип данных в ответе API.')
    return response['homeworks']


def parse_status(homework):
    """Извлекает из домашней работе её статус."""
    if not homework.get('homework_name'):
        raise ValueError('В ответе API нет ключа homework_name.')
    homework_name = homework['homework_name']
    if homework['status'] not in HOMEWORK_VERDICTS:
        raise ValueError('Не известный статус.')
    verdict = HOMEWORK_VERDICTS[homework['status']]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Одна или несколько переменных '
                         'не доступны, бот остановлен.')
        return

    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    homeworks = []
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            for homework in response['homeworks']:
                if homework not in homeworks:
                    homeworks.append(homework)
                    message = parse_status(homework)
                    send_message(bot, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
