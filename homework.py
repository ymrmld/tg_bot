import logging
import os
import sys
import exceptions

from http import HTTPStatus
import requests
import telegram
from telegram.ext import Updater
import time

from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
ENDPOINT = os.getenv('ENDPOINT')
RETRY_PERIOD = 600
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

updater = Updater(token=TELEGRAM_TOKEN)
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
    cheks = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }

    for chek in cheks:
        if cheks[chek] is None:
            logger.critical('Ошибка импорта токенов.')
            raise exceptions.NegativeValue('Неверно передан токен!')
        elif not ENDPOINT:
            logger.error('Ошибка импорта эндпоинта.')
            raise exceptions.NegativeValue('Неверно передан эндпоинт!')
        else:
            return True


def send_message(bot, message):
    """Отправить сообщение в телеграм."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f'Бот отправил сообщение. {message}')
    except Exception as error:
        logger.error(f'Бот не отправил сообщение, так как : {error}')
        raise exceptions.Negative(
            f'Бот не отправил сообщение, так как : {error}'
        )


def get_api_answer(timestamp):
    """Запрос к эндпоинту, ответ API."""
    params = {'from_date': timestamp}
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if response.status_code != HTTPStatus.OK:
            logger.error('Ошибка при запросе к основному API.')
            send_message(
                bot, f'Сбой работы. Ответ сервера {response.status_code}'
            )
            raise exceptions.NotFoundStatuse(
                'Ошибка при запросе к основному API.'
            )
        response = response.json()
        return response
    except requests.exceptions.RequestException as request_error:
        logger.error(f'Код ответа API (RequestException): {request_error}')
        raise exceptions.Negative(
            f'Код ответа API (RequestException): {request_error}'
        )


def check_response(response):
    """Проверка ответа API."""
    if type(response) != dict:
        logger.error('Определен неверный тип данных.')
        raise TypeError('Определен неверный тип данных.')
    homework = response.get('homeworks')
    if type(homework) != list:
        logger.error('Определен неверный тип данных.')
        raise TypeError('Определен неверный тип данных.')
    return homework


def parse_status(homework):
    """Проверить статус работы в ответе сервера."""
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    if homework_name is None:
        logger.error(f'Отсутствует ключ {homework_name}.')
        send_message(bot, f'Отсутствует ключ {homework_name}.')
        raise exceptions.Negative(f'Отсутствует ключ {homework_name}.')
    if status is None:
        logger.error(f'Отсутствует статус {status}.')
        raise exceptions.Negative(f'Отсутствует статус {status}.')
    if status not in HOMEWORK_VERDICTS.keys():
        logger.error('Недокументированный статус.')
        send_message(bot, 'Недокументированный статус.')
        raise exceptions.Negative('Недокументированный статус.')

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while check_tokens():
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            logger.info(f'Получили список работ {homework}')

            if len(homework) > 0:
                send_message(bot, parse_status(homework[0]))
            else:
                logger.debug('Нет нового статуса')

        except Exception as error:
            logger.error(f'Сбой в работе программы: {error}')
            send_message(bot, f'Сбой в работе программы: {error}')
            time.sleep(RETRY_PERIOD)

        finally:
            timestamp = int(time.time())
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
