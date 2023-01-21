import datetime as dt
import json
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()

PRACTICUM_TOKEN = os.getenv(
    'PRACTICUM_TOKEN',
    default='AAVcF8hAAYckQAAAADZoors0O7kVwRTuXuKBjB3Ag'
)
TELEGRAM_TOKEN = os.getenv(
    'TELEGRAM_TOKEN',
    default='5905167654:MmaDLXZ37WLwvaBHnWFjoo174'
)
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', default=8234567890)
ENDPOINT = os.getenv(
    'ENDPOINT',
    default='https://practicum.yandex.ru/api/user_api/homework_statuses/'
)
RETRY_PERIOD = 600
SECONDS_FOR_CHANGE = 50
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)


def check_tokens():
    """Проверка доступности переменных."""
    chek_token = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    cheks = all(chek_token)

    if not cheks:
        logger.critical('Ошибка импорта токенов.')
        return False

    return True


def send_message(bot, message):
    """Отправить сообщение в телеграм."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f'Бот отправил сообщение. {message}')
    except Exception as error:
        logger.error(f'Бот не отправил сообщение, так как : {error}')


def get_api_answer(timestamp):
    """Запрос к эндпоинту, ответ API."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except requests.exceptions.RequestException as request_error:
        logger.error(f'Код ответа API (RequestException): {request_error}')
        raise exceptions.Negative(
            f'Код ответа API (RequestException): {request_error}'
        )

    if response.status_code != HTTPStatus.OK:
        raise exceptions.NotFoundStatuse(
            'Ошибка при запросе к основному API.'
        )

    try:
        response = response.json()
    except json.decoder.JSONDecodeError:
        logger.error('Ответ сервера не может быть преобразован в JSON.')
        raise json.JSONDecodeError(
            'Ответ сервера не может быть преобразован в JSON.'
        )
    return response


def check_response(response):
    """Проверка ответа API."""
    if not isinstance(response, dict):
        logger.error('Определен неверный тип данных.')
        raise TypeError('Определен неверный тип данных.')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        logger.error('Определен неверный тип данных.')
        raise TypeError('Определен неверный тип данных.')
    return homeworks


def parse_status(homework):
    """Проверить статус работы в ответе сервера."""
    homework_name = homework.get('homework_name')
    status = homework.get('status')

    if homework_name is None:
        logger.error(f'Отсутствует ключ {homework_name}.')
        raise exceptions.Negative(f'Отсутствует ключ {homework_name}.')

    if status is None:
        logger.error(f'Отсутствует статус {status}.')
        raise exceptions.Negative(f'Отсутствует статус {status}.')

    if status not in HOMEWORK_VERDICTS.keys():
        logger.error('Недокументированный статус.')
        raise exceptions.Negative('Недокументированный статус.')

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time()) - SECONDS_FOR_CHANGE
    error_save = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            start = dt.datetime.now()
            homeworks = check_response(response)
            logger.info(f'Получили список работ {homeworks}')

            if len(homeworks) > 0:
                send_message(bot, parse_status(homeworks[0]))
            else:
                logger.debug('Нет нового статуса')
            error_save = ''
            if response['current_date'] is None:
                current_timestamp = start.timestamp() - SECONDS_FOR_CHANGE
            else:
                current_timestamp = response['current_date']

        except Exception as error:
            logger.error(f'Сбой в работе программы: {error}')

            if error_save != error:
                send_message(bot, f'Сбой в работе программы: {error}')
                error_save = error

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
