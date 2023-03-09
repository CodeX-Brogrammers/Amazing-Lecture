import logging

from aiohttp import web
from aioalice import Dispatcher, get_new_configured_app, types
from aioalice.dispatcher import MemoryStorage


# Blank:
# - звуковое сопровождение 


WEBHOOK_URL_PATH = '/post'  # webhook endpoint

WEBAPP_HOST = 'localhost'
WEBAPP_PORT = 5050


logging.basicConfig(format=u'%(filename)s [LINE:%(lineno)d] #%(levelname)-8s [%(asctime)s]  %(message)s',
                    level=logging.INFO)

# Создаем экземпляр диспетчера и подключаем хранилище в памяти
dp = Dispatcher(storage=MemoryStorage())


ele_link = 'https://market.yandex.ru/search?text=слон'
# Заготавливаем кнопку на всякий случай
OK_Button = types.Button('Ладно', url=ele_link)


@dp.request_handler(func=lambda areq: areq.session.new)
async def handle_start(alice_request):
    answer = """Уважаемые студенты, рада видеть вас на своей лекции.
Я профессор исторических наук, Аврора Хистория.
Я хочу поговорить с вами о том, как история может стать настоящей сказкой.
Многие из вас думают, что история - скучный набор фактов и дат.
Но что если я отправлю вас в настоящий мир фантазий и историй?
Я уже подготовила наш волшебный поезд.
Готовы ли вы отправиться в это путешествие?
"""
    return alice_request.response(answer)


# Обработчик помощи
@dp.request_handler(commands=["помощь", "поясни", "расскажи"])
async def handle_help(alice_request):
    answer = """Навык "Удивительная лекция" отправит вас в увлекательное путешествие.
Продвигаясь все дальше вы будете отвечать на вопросы и зарабатывать баллы.
Погрузитесь в атмосферу Древнего Рима, Средневековья, Эпохи Возрождения вместе с замечательным проводником Авророй Хисторией.
"""
    return alice_request.response(answer, tts=answer + '<speaker audio="alice-music-drum-loop-1.opus">')


# Обработчик "Что ты умеешь ?"
@dp.request_handler(commands=['ладно', 'куплю', 'покупаю', 'хорошо', 'окей'])
async def handle_help(alice_request):
    answer = f'Слона можно найти на Яндекс.Маркете!'
    return alice_request.response(answer, tts=answer + '<speaker audio="alice-music-drum-loop-1.opus">')


# Обработчик "Стоп крана"
# TODO: 
# 1. Отображать статистику игрока ака "Процент успешности"
@dp.request_handler(contains=['хочу', 'луну'])
async def handle_stop(alice_request):
    print(alice_request)
    answer = "Прощай🌚"
    return alice_request.response(answer, tts=answer + '<speaker audio="alice-music-drum-loop-1.opus">')


if __name__ == '__main__':
    app = get_new_configured_app(dispatcher=dp, path=WEBHOOK_URL_PATH)
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT, loop=dp.loop)
