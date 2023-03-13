from random import choice, shuffle
from typing import Callable
from os import getenv
import logging
import json

from aioalice import Dispatcher, get_new_configured_app
from aioalice.dispatcher.storage import MemoryStorage
from aioalice.types import AliceRequest, Button
from beanie import PydanticObjectId
from aiohttp import web

import filters
import models
from state import State, SessionState, GameStates

# Blank:
# - звуковое сопровождение
# - совместная игра
# - свои вопросы
# - Session state надо передавать в каждый запрос
# - Повтори ответы

WEBHOOK_URL_PATH = '/post'  # webhook endpoint

WEBAPP_HOST = getenv("APP_ADDRESS", "localhost")
WEBAPP_PORT = 5000

logging.basicConfig(format=u'%(filename)s [LINE:%(lineno)d] #%(levelname)-8s [%(asctime)s]  %(message)s',
                    level=logging.INFO)

OK_Button = Button('Ладно')
REJECT_Button = Button('Нет')
REPEAT_Button = Button('Повтори')
BUTTONS = [OK_Button, REJECT_Button, REPEAT_Button]

POSSIBLE_ANSWER = ("Начинаем ?", "Готовы начать ?", "Поехали ?")
CONTINUE_ANSWER = ("Продолжим ?", "Едем дальше ?")
FACT_ANSWER = ("Хотите послушать интересный факт ?",)

# Создаем экземпляр диспетчера и подключаем хранилище в памяти


dp = Dispatcher(storage=MemoryStorage())
app = get_new_configured_app(dispatcher=dp, path=WEBHOOK_URL_PATH)


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
             "Вы можете узнать больше, если скажите \"Помощь\" и \"Что ты умеешь?\"" \
             "Я хочу поговорить с вами о том, как история может стать настоящей сказкой. " \
             "Что если я отправлю вас в настоящий мир фантазий и историй? " \
             "Я уже подготовила наш волшебный поезд. Готовы ли вы отправиться в это путешествие? "
    return alice_request.response(answer, buttons=BUTTONS)
    
    # TODO: придумать как вывести без уточнений


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
async def handle_start_game(alice_request: AliceRequest):
    return await handler_question(alice_request)
# @can_repeat
# async def handle_start_game(alice_request: AliceRequest):
#     logging.info(f"User: {alice_request.session.user_id}: Handler->Start game")
#     await dp.storage.set_state(alice_request.session.user_id, GameStates.QUESTION_TIME)
#     answer = "Отлично! Наш поезд отправляется в увлекательное путешествие. " \
#              "Я надеюсь, что вы сможете погрузиться в такой необычный мир фантазий. " \
#              "И помните,что каждая достопримечательность имеет свою уникальную историю" \
#              " и может стать источником вдохновения для вашего будущего творчества."
#
#     return alice_request.response(answer)


# Отказ от игры и выход
@dp.request_handler(filters.RejectFilter(), state=GameStates.START)
async def handle_reject_game(alice_request: AliceRequest):
    logging.info(f"User: {alice_request.session.user_id}: Handler->Reject game")
    answer = "Было приятно видеть вас на моей лекции. Заходите почаще, всегда рада."
    return alice_request.response(answer, end_session=True)


# @dp.request_handler(filters.RejectFilter())
# async def handle_reject(alice_request: AliceRequest):
#     answer = "Ну и ладно"
#     return alice_request.response(answer)


@dp.request_handler(contains="добавь", state="*")
async def handler_set_score(alice: AliceRequest):
    state = State.from_request(alice)
    state.user.score += 1
    return alice.response(
        f"Score: {state.user.score}", user_state_update=state.user.dict()
    )


@dp.request_handler(contains="убавь", state="*")
async def handler_set_score(alice: AliceRequest):
    state = State.from_request(alice)
    state.user.score -= 1
    return alice.response(
        f"Score: {state.user.score}", user_state_update=state.user.dict()
    )


@dp.request_handler(filters.ScoreFilter(filters.Operation.LE, 0), contains="подска")
async def handler(alice: AliceRequest):
    return alice.response("Нет🌝")


@dp.request_handler(filters.ScoreFilter(filters.Operation.GE, 1), contains="подска")
async def handler(alice: AliceRequest):
    state = State.from_request(alice)
    state.user.score -= 1
    return alice.response("}{🌚р🌚ш🌚", user_state_update=state.user.dict())


@dp.request_handler(state=GameStates.QUESTION_TIME)
async def handler_question(alice: AliceRequest):
    # Получить случайный вопрос
    # TODO: что-то придумать для исключения вопросов из пулла после их проходения
    # |-> Можно сохранять в сессии пройденные вопросы
    # Сохранить его ID в State
    # Отправить вопрос с вариантами ответов

    await dp.storage.set_state(alice.session.user_id, state=GameStates.GUESS_ANSWER)

    data = await models.Question.aggregate([{"$sample": {"size": 1}}]).to_list()
    if len(data) == 0:
        # Завершаем игру
        return alice.response("Похоже вопросы закончились 🙃")
    question: models.Question = models.Question.parse_obj(data[0])
    state = State.from_request(alice)
    state.session.current_question = str(question.id)

    answers = question.answers
    shuffle(answers)
    answers = [(index, answer) for index, answer in enumerate(answers, 1)]
    text = "\n".join((
        question.full_text.src, "\nВарианты ответов:",
        *[f"{i}: {answer.text.src}" for i, answer in answers]
    ))
    tts = "\n".join((
        question.full_text.tts, "Варианты ответов:",
        *[f"{i}-й {answer.text.tts}" for i, answer in answers]
    ))

    buttons = [Button(title=answer.text.src, payload={"is_true": answer.is_true, "number": i})
               for i, answer in answers]
    state.session.current_answers = [(i, answer.text.src) for i, answer in answers]
    return alice.response(
        text,
        tts=tts,
        session_state=state.session.dict(),
        buttons=buttons
    )


@dp.request_handler(filters.TrueAnswerFilter(), state=GameStates.GUESS_ANSWER)
async def handler_true_answer(alice: AliceRequest):
    # Получить ID вопроса из State-а
    # Если ответ верный, добавить балл
    state = State.from_request(alice)
    state.user.score += 1

    state.session.passed_questions.append(
        state.session.current_question
    )
    state.session.current_question = None
    await dp.storage.set_state(alice.session.user_id, state=GameStates.FACT)
    return alice.response(choice(FACT_ANSWER), user_state_update=state.user.dict())


@dp.request_handler(filters.FalseAnswerFilter(), state=GameStates.GUESS_ANSWER)
async def handler_false_answer(alice: AliceRequest):
    # Получить ID вопроса из State-а
    # Если ответ неверный, предложить подсказку или отказаться
    await dp.storage.set_state(alice.session.user_id, state=GameStates.HINT)
    state = State.from_request(alice)
    return alice.response(
        "К сожелению это не верный ответ. Хотите получить подсказку ?",
        session_state=state.session.dict()
    )


@dp.request_handler(filters.ConfirmFilter(), state=GameStates.FACT)
async def handler_fact_confirm(alice: AliceRequest):
    state = State.from_request(alice)
    question_id = state.session.current_question
    question = await models.Question.get(PydanticObjectId(question_id))

    fun_fact = "Интересный факт\n"
    continue_answer = choice(CONTINUE_ANSWER)
    state.session.current_question = None
    state.session.passed_questions.append(question_id)
    await dp.storage.set_state(alice.session.user_id, state=GameStates.QUESTION_TIME)
    return alice.response(
        "\n".join(fun_fact + question.fact.src + continue_answer),
        tts="\n".join(fun_fact + question.fact.tts + continue_answer),
        user_state_update=state.session.dict()
    )


@dp.request_handler(filters.RejectFilter(), state=GameStates.FACT)
async def handler_fact_reject(alice: AliceRequest):
    return await handler_question(alice)


@dp.request_handler(filters.ConfirmFilter(), state=GameStates.HINT)
async def handler_hint(alice: AliceRequest):
    # Получить ID вопроса из State-а
    # Если у пользователя достаточно баллов, даем подсказку
    # Иначе не даем
    # TODO: Добавить убавление подсказок
    await dp.storage.set_state(alice.session.user_id, state=GameStates.GUESS_ANSWER)
    state = State.from_request(alice)
    question_id = state.session.current_question
    question = await models.Question.get(PydanticObjectId(question_id))
    return alice.response(
        "\n".join(("Подсказка:", question.hint.src)),
        tts="\n".join(("Подсказка:", question.hint.tts))
    )


@dp.request_handler(filters.RejectFilter(), state=GameStates.HINT)
async def handler_hint(alice: AliceRequest):
    return await handler_fact_confirm(alice)


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


@web.middleware
async def log_middleware(request, handler):
    logging.info("User enter")
    response = await handler(request)
    logging.info("User exit")
    return response


@web.middleware
async def session_state_middleware(request, handler):
    response = await handler(request)
    data = (await request.json())["state"]["session"]
    state = SessionState.parse_obj(data).dict()
    body = json.loads(response.body)
    body["session_state"] = state | body["session_state"]
    response.body = json.dumps(body)
    return response


if __name__ == '__main__':
    app = get_new_configured_app(dispatcher=dp, path=WEBHOOK_URL_PATH)
    app.on_startup.append(models.init_database)
    app.middlewares.append(session_state_middleware)
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT, loop=dp.loop)
