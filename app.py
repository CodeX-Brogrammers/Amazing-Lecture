from collections import defaultdict
from typing import Callable
from random import choice
import logging

from aioalice.utils.helper import Helper, HelperMode, Item
from aioalice import Dispatcher, get_new_configured_app
from aioalice.dispatcher.storage import MemoryStorage
from aioalice.types import AliceRequest, Button
from aiohttp import web

import filters

# Blank:
# - звуковое сопровождение
# - совместная игра
# - свои вопросы

WEBHOOK_URL_PATH = '/post'  # webhook endpoint

WEBAPP_HOST = '0.0.0.0'
WEBAPP_PORT = 5000

logging.basicConfig(format=u'%(filename)s [LINE:%(lineno)d] #%(levelname)-8s [%(asctime)s]  %(message)s',
                    level=logging.INFO)

OK_Button = Button('Ладно')
REJECT_Button = Button('Нет')
REPEAT_Button = Button('Повтори')
BUTTONS = [OK_Button, REJECT_Button, REPEAT_Button]

POSSIBLE_ANSWER = ("Начинаем ?", "Готовы начать ?", "Поехали ?")


# Создаем экземпляр диспетчера и подключаем хранилище в памяти


dp = Dispatcher(storage=MemoryStorage())
app = get_new_configured_app(dispatcher=dp, path=WEBHOOK_URL_PATH)


class RequestState:
    def __init__(self, session, user, application):
        self.session = defaultdict(int, session)
        self.user = defaultdict(int, user)
        self.application = defaultdict(int, application)

    @classmethod
    def from_request(cls, alice: AliceRequest):
        return cls(**alice._raw_kwargs["state"])


class GameStates(Helper):
    mode = HelperMode.snake_case

    START = Item()  # Навык только запустился
    # SELECT_GAME = Item()  # Выбор режима (Default или Fast)
    # SELECT_DIFFICULTY = Item()  # ?Выбор сложности?
    QUESTION_TIME = Item()  # Время вопроса
    GUESS_ANSWER = Item()  # Выбор ответов
    HINT = Item()  # Подсказка
    END = Item()  # Завершение


def can_repeat(func: Callable):
    async def wrapper(alice: AliceRequest, *args, **kwargs):
        await dp.storage.set_data(alice.session.user_id, {"last": func})
        return await func(alice, *args, **kwargs)
    return wrapper


# Обработчик повторения последней команды
@dp.request_handler(filters.RepeatFilter(), state=None)
async def handle_repeat(alice_request: AliceRequest):
    handler = (await dp.storage.get_data(alice_request.session.user_id)).get("last", lambda: None)
    logging.info(f"User: {alice_request.session.user_id}: Handler->Repeat->{handler.__name__}")
    return await handler(alice_request)


@dp.request_handler(filters.StartFilter(), state=None)
@can_repeat
async def handle_start(alice_request: AliceRequest):
    logging.info(f"User: {alice_request.session.user_id}: Handler->Start")
    await dp.storage.set_state(alice_request.session.user_id, GameStates.START)
    answer = "Уважаемые студенты, рада видеть вас на своей лекции. " \
             "Я профессор исторических наук, Аврора Хистория. " \
             "Я хочу поговорить с вами о том, как история может стать настоящей сказкой. " \
             "Многие из вас думают, что история - скучный набор фактов и дат. " \
             "Но что если я отправлю вас в настоящий мир фантазий и историй? " \
             "Я уже подготовила наш волшебный поезд. Готовы ли вы отправиться в это путешествие? "
    return alice_request.response(answer, buttons=BUTTONS)


# Обработчик "что ты умеешь" до игры
# TODO: расширить набор команд
@dp.request_handler(commands=["что ты умеешь"])
@can_repeat
async def handle_can_do(alice_request: AliceRequest):
    logging.info(f"User: {alice_request.session.user_id}: Handler->Help")
    answer = "Навык будет задавать вам вопросы и предлагать варианты ответов. " \
             "Для успешного прохождения навыка вам нужно ответить верно как можно больше раз. " \
             "У вас есть  возможность взять подсказку для вопроса, но количество подсказок ограничено."
    answer += choice(POSSIBLE_ANSWER)
    return alice_request.response(answer, tts=answer + '<speaker audio="alice-music-drum-loop-1.opus">')


# Обработчик помощи до игры
@dp.request_handler(filters.HelpFilter(), state=GameStates.START)
@can_repeat
async def handle_help(alice_request: AliceRequest):
    logging.info(f"User: {alice_request.session.user_id}: Handler->Help")
    answer = "Навык \"Удивительная лекция\" отправит вас в увлекательное путешествие." \
             "Продвигаясь все дальше вы будете отвечать на вопросы и зарабатывать баллы." \
             "Погрузитесь в атмосферу Древнего Рима, Средневековья," \
             " Эпохи Возрождения вместе с замечательным проводником Авророй Хисторией."
    answer += choice(POSSIBLE_ANSWER)
    return alice_request.response(answer, tts=answer + '<speaker audio="alice-music-drum-loop-1.opus">')


# Обработчик помощи во время игры
# Обработчик "что ты умеешь" во время игры


@dp.request_handler(filters.ConfirmFilter(), state=GameStates.START)
@can_repeat
async def handle_start_game(alice_request: AliceRequest):
    logging.info(f"User: {alice_request.session.user_id}: Handler->Start game")
    await dp.storage.set_state(alice_request.session.user_id, GameStates.QUESTION_TIME)
    answer = "Отлично! Наш поезд отправляется в увлекательное путешествие. " \
             "Я надеюсь, что вы сможете погрузиться в такой необычный мир фантазий. " \
             "И помните,что каждая достопримечательность имеет свою уникальную историю" \
             " и может стать источником вдохновения для вашего будущего творчества."
    return alice_request.response(answer)


# Отказ от игры и выход
@dp.request_handler(filters.RejectFilter(), state=GameStates.START)
async def handle_reject_game(alice_request: AliceRequest):
    logging.info(f"User: {alice_request.session.user_id}: Handler->Reject game")
    answer = "Было приятно видеть вас на моей лекции. Заходите почаще, всегда рада."
    return alice_request.response(answer, end_session=True)


@dp.request_handler(filters.RejectFilter())
async def handle_reject(alice_request: AliceRequest):
    answer = "Ну и ладно"
    return alice_request.response(answer)


@dp.request_handler(contains="добавь", state="*")
async def handler_set_score(alice: AliceRequest):
    state = RequestState.from_request(alice)
    state.user["score"] += 1
    return alice.response(f"Score: {state.user['score']}", session_state={"test": True}, user_state_update=state.user)


@dp.request_handler(contains="убавь", state="*")
async def handler_set_score(alice: AliceRequest):
    state = RequestState.from_request(alice)
    state.user["score"] -= 1
    return alice.response(f"Score: {state.user['score']}", session_state={"test": True}, user_state_update=state.user)


@dp.request_handler(filters.ScoreFilter(filters.Operation.LE, 0), contains="подска")
async def handler(alice: AliceRequest):
    return alice.response("Нет🌝")


@dp.request_handler(filters.ScoreFilter(filters.Operation.GE, 1), contains="подска")
async def handler(alice: AliceRequest):
    state = RequestState.from_request(alice)
    state.user['score'] -= 1
    return alice.response("}{🌚р🌚ш🌚", user_state_update=state.user)


# TODO: 
# 1. Отображать статистику игрока ака "Процент успешности"
@dp.request_handler(state=None)
async def handle_intent(alice_request: AliceRequest):
    data = alice_request.request.nlu._raw_kwargs
    answer = f"Intents: {data['intents']}\nTokens: {data['tokens']}"
    return alice_request.response(answer, tts='ДА<speaker audio="alice-sounds-things-explosion-1.opus">')


@dp.errors_handler()
async def the_only_errors_handler(alice_request, e):
    logging.error('An error!', exc_info=e)
    return alice_request.response('Oops! There was an error!')


if __name__ == '__main__':
    app = get_new_configured_app(dispatcher=dp, path=WEBHOOK_URL_PATH)
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT, loop=dp.loop)
