import os
import time
import logging
import sys
from http import HTTPStatus

import requests
from telegram import Bot
from telegram.error import TelegramError
from dotenv import load_dotenv

from exceptions import HomeWorksException

load_dotenv()

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


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение отправлено')
    except TelegramError as er:
        logging.error(f'Бот не смог отправить сообщение: {message}. [{er}]')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса Практикум.Домашка."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != HTTPStatus.OK:
            raise HomeWorksException(f'Код ответа API: {response.status_code}')
        return response.json()
    except requests.exceptions.RequestException as er:
        raise HomeWorksException('Ошибка API-сервиса '
                                 'Практикум.Домашка.') from er


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(f'API вернул в ответе {type(response)} вместо "dict".')
    if 'current_date' not in response:
        raise KeyError('В ответе API нет ключа current_date')
    if 'homeworks' not in response:
        raise KeyError('В ответе API нет ключа homeworks')
    if not isinstance(response['homeworks'], list):
        raise TypeError(f'API вернул значение "homeworks": '
                        f'{type(response["homeworks"])} вместо "list".')
    if not isinstance(response['current_date'], int):
        raise TypeError(f'API вернул значение "current_date": '
                        f'{type(response["current_date"])} вместо "int".')
    return response['homeworks']


def parse_status(homework):
    """Извлекает из домашней работе её статус."""
    if not homework.get('homework_name'):
        raise ValueError('В ответе API нет ключа homework_name.')
    homework_name = homework['homework_name']
    if homework.get('status') not in HOMEWORK_VERDICTS:
        raise ValueError(f'Не известный статус: {homework["status"]}.')
    verdict = HOMEWORK_VERDICTS[homework['status']]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Одна или несколько переменных '
                         'не доступны, бот остановлен.')
        sys.exit(1)

    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        homeworks = ''
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            if not response['homeworks']:
                logging.debug('Новых домашних заданий нету.')
            timestamp = int(response['current_date'])
            for homework in response['homeworks']:
                if homework != homeworks:
                    homeworks = homework
                    message = parse_status(homework)
                    send_message(bot, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format=('%(asctime)s | %(levelname)s | %(name)s | '
                'Функция: %(funcName)s | Строка: %(lineno)d | %(message)s'),
        level=logging.DEBUG,
        filename=f'{os.getcwd()}/main.log'
    )
    main()
