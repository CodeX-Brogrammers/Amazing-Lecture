from random import choice, shuffle
from typing import Callable, Optional
from os import getenv
import logging
import json

from aioalice.types import AliceRequest, Button, MediaButton
from aioalice import Dispatcher, get_new_configured_app
from aioalice.dispatcher.storage import MemoryStorage
from aiohttp.web_request import Request
from beanie import PydanticObjectId
from aiohttp import web

from state import State, SessionState, GameStates
import filters
import models
import nlu

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

OK_Button = Button('Да')
REJECT_Button = Button('Нет')
REPEAT_Button = Button('Повтори')
BUTTONS = [OK_Button, REJECT_Button, REPEAT_Button]

POSSIBLE_ANSWER = ("Начинаем ?", "Готовы начать ?", "Поехали ?")
CONTINUE_ANSWER = ("Продолжим ?", "Едем дальше ?")
FACT_ANSWER = ("Хотите послушать интересный факт ?",)

# Создаем экземпляр диспетчера и подключаем хранилище в памяти


dp = Dispatcher(storage=MemoryStorage())  # Сделать Хранилище состояний на Redis
app = get_new_configured_app(dispatcher=dp, path=WEBHOOK_URL_PATH)


def can_repeat(func: Callable):
    async def wrapper(alice: AliceRequest, *args, **kwargs):
        response = await func(alice, *args, **kwargs)
        await dp.storage.set_data(alice.session.user_id, {"last": response})
        return response

    return wrapper


# Обработчик повторения последней команды
@dp.request_handler(filters.RepeatFilter(), state="*")
async def handle_repeat(alice: AliceRequest):
    state = await dp.storage.get_state(alice.session.user_id)
    if state.upper() in ("QUESTION_TIME", "GUESS_ANSWER", "HINT"):
        if nlu.calculate_coincidence(
            input_tokens=nlu.lemmatize(nlu.tokenizer(alice.request.command)),
            source_tokens=nlu.lemmatize(["вопрос"])
        ) >= 1.0:
            logging.info(f"User: {alice.session.user_id}: Handler->Повторить->Вопрос")
            question = await repeat_question(alice)
            answers = repeat_answers(alice)
            question["tts"] += f"\n{answers['tts']}"
            return alice.response_big_image(
                **question,
                buttons=answers["buttons"]
            )

        if nlu.calculate_coincidence(
            input_tokens=nlu.lemmatize(nlu.tokenizer(alice.request.command)),
            source_tokens=nlu.lemmatize(["ответ"])
        ) >= 1.0:
            logging.info(f"User: {alice.session.user_id}: Handler->Повторить->Ответы")
            answers = repeat_answers(alice)
            return alice.response(answers["text"], tts=answers["tts"], buttons=answers["buttons"])

    logging.info(f"User: {alice.session.user_id}: Handler->Повторить->Последний ответ")
    response = (await dp.storage.get_data(alice.session.user_id))
    response = response.get("last", alice.response("Мне нечего повторять"))
    return response


async def repeat_question(alice: AliceRequest):
    state = State.from_request(alice)
    question = await models.Question.get(PydanticObjectId(state.session.current_question))
    return dict(
        text=question.full_text.src,
        tts=question.full_text.tts,
        image_id=question.image.yandex_id,
        title="",
        description=question.full_text.src
    )


def repeat_answers(alice: AliceRequest):
    state = State.from_request(alice)

    answers = state.session.current_answers
    text = "\n".join((
        "Варианты ответов:",
        *[f"{i}: {answer}" for i, answer in answers]
    ))
    tts = "\n".join((
        "Варианты ответов:",
        *[f"{i}-й {answer}" for i, answer in answers]
    ))
    buttons = [
        Button(
            title=text,
            payload={"is_true": i == state.session.current_true_answer, "number": i}
        )
        for i, text in answers
    ]
    return {"text": text, "tts": tts, "buttons": buttons}


@dp.request_handler(filters.StartFilter(), state=None)
@can_repeat
async def handle_start(alice: AliceRequest):
    logging.info(f"Handler->Старт")
    await dp.storage.set_state(alice.session.user_id, GameStates.START)
    answer = "Уважаемые студенты, рада видеть вас на своей лекции. " \
             "Я профессор исторических наук, Аврора Хистория. " \
             "Вы можете узнать больше, если скажите \"Помощь\" и \"Что ты умеешь?\"" \
             "Я хочу поговорить с вами о том, как история может стать настоящей сказкой. " \
             "Что если я отправлю вас в настоящий мир фантазий и историй? " \
             "Я уже подготовила наш волшебный поезд. Готовы ли вы отправиться в это путешествие? "
    return alice.response(answer, buttons=BUTTONS)


# Обработчик "что ты умеешь" до игры
# TODO: расширить набор команд
@dp.request_handler(filters.CanDoFilter(), state="*")
@can_repeat
async def handle_can_do(alice: AliceRequest):
    logging.info(f"User: {alice.session.user_id}: Handler->Что ты умеешь")
    answer = "Навык будет задавать вам вопросы и предлагать варианты ответов. " \
             "Для успешного прохождения навыка вам нужно ответить верно как можно больше раз. " \
             "У вас есть  возможность взять подсказку для вопроса, но количество подсказок ограничено."
    state = await dp.storage.get_state(alice.session.user_id)
    if state in ("DEFAULT_STATE", "*"):
        answer = f"{answer}\n{choice(POSSIBLE_ANSWER)}"
    return alice.response(answer)


# Обработчик помощи до игры
@dp.request_handler(filters.HelpFilter(), state="*")
@can_repeat
async def handle_help(alice: AliceRequest):
    logging.info(f"User: {alice.session.user_id}: Handler->Помощь")
    answer = "Навык \"Удивительная лекция\" отправит вас в увлекательное путешествие." \
             "Продвигаясь все дальше вы будете отвечать на вопросы и зарабатывать баллы." \
             "Погрузитесь в атмосферу Древнего Рима, Средневековья," \
             " Эпохи Возрождения вместе с замечательным проводником Авророй Хисторией."
    state = await dp.storage.get_state(alice.session.user_id)
    if state in ("DEFAULT_STATE", "*"):
        answer = f"{answer}\n{choice(POSSIBLE_ANSWER)}"
    return alice.response(answer)


@dp.request_handler(filters.ConfirmFilter(), state=GameStates.START)
@can_repeat
async def handle_start_game(alice: AliceRequest):
    logging.info(f"User: {alice.session.user_id}: Handler->Начать игру")
    return await handler_question(alice)


# Отказ от игры и выход
@dp.request_handler(filters.RejectFilter(), state=GameStates.START)
async def handle_reject_game(alice: AliceRequest):
    logging.info(f"User: {alice.session.user_id}: Handler->Отмена игры")
    answer = "Было приятно видеть вас на моей лекции. Заходите почаще, всегда рада."
    return alice.response(answer, end_session=True)


@dp.request_handler(filters.ConfirmFilter(), state=GameStates.QUESTION_TIME)
@can_repeat
async def handler_question(alice: AliceRequest):
    # Получить случайный вопрос
    # TODO: что-то придумать для исключения вопросов из пулла после их проходения
    # |-> Можно сохранять в сессии пройденные вопросы
    # Сохранить его ID в State
    # Отправить вопрос с вариантами ответов
    logging.info(f"User: {alice.session.user_id}: Handler->Получение вопроса")
    state = State.from_request(alice)

    await dp.storage.set_state(alice.session.user_id, state=GameStates.GUESS_ANSWER)

    data = await models.Question.aggregate([
        {'$match': {'_id': {'$nin': tuple(map(lambda q: PydanticObjectId(q), state.session.passed_questions))}}},
        {"$sample": {"size": 1}}
    ]).to_list()

    if len(data) == 0:
        logging.info(f"User: {alice.session.user_id}: Handler->Получение вопроса->вопросы закончились")
        return await handler_end(alice)

    question: models.Question = models.Question.parse_obj(data[0])
    state.session.current_question = str(question.id)
    state.session.passed_questions.append(
        state.session.current_question
    )
    answers = question.answers
    shuffle(answers)
    answers = [(index, answer) for index, answer in enumerate(answers, 1)]
    text = question.full_text.src
    tts = "\n".join((
        question.full_text.tts, "Варианты ответов:",
        *[f"{i}-й {answer.text.tts}" for i, answer in answers]
    ))

    buttons = [Button(title=answer.text.src, payload={"is_true": answer.is_true, "number": i})
               for i, answer in answers]
    state.session.current_answers = [(i, answer.text.src) for i, answer in answers]
    state.session.current_true_answer = [i for i, answer in answers if answer.is_true][0]
    return alice.response_big_image(
        text,
        tts=tts,
        session_state=state.session.dict(),
        buttons=buttons,
        image_id=question.image.yandex_id,
        title="",
        description=text
    )


@dp.request_handler(filters.RejectFilter(), state=GameStates.QUESTION_TIME)
async def handler_reject_question(alice: AliceRequest):
    return await handler_end(alice)


@dp.request_handler(state=GameStates.GUESS_ANSWER)
async def handler_quess_answer(alice: AliceRequest):
    is_true_answer, diff = nlu.check_user_answer(alice)
    if is_true_answer:
        return await handler_true_answer(alice)
    return await handler_false_answer(alice, diff)


async def handler_true_answer(alice: AliceRequest):
    # Получить ID вопроса из State-а
    # Если ответ верный, добавить балл
    logging.info(f"User: {alice.session.user_id}: Handler->Отгадал ответ")
    state = State.from_request(alice)
    state.user.score += 1

    await dp.storage.set_state(alice.session.user_id, state=GameStates.FACT)
    session = state.session
    answer_text = session.current_answers[session.current_true_answer - 1][1]
    question = await models.Question.get(PydanticObjectId(session.current_question))
    answer = [answer for answer in question.answers if answer.text.src == answer_text][0]
    fact_text = choice(FACT_ANSWER)
    state.session.current_question = None
    return alice.response(
        "\n".join((answer.description.src, fact_text)),
        tts="\n".join((answer.description.tts, fact_text)),
        user_state_update=state.user.dict(),
        session_state=state.session.dict(),
        buttons=[OK_Button, REJECT_Button]
    )


async def handler_false_answer(alice: AliceRequest, diff: Optional[models.Diff]):
    # Получить ID вопроса из State-а
    # Если ответ неверный, предложить подсказку или отказаться
    logging.info(f"User: {alice.session.user_id}: Handler->Не отгадал ответ")
    if diff is None:
        return alice.response("Извините, я вас не понимаю, повторите пожалуйста")

    await dp.storage.set_state(alice.session.user_id, state=GameStates.HINT)
    state = State.from_request(alice)
    question = await models.Question.get(state.session.current_question)
    answer = [answer for answer in question.answers if answer.text.src == diff.answer][0]
    return alice.response(
        "\n".join((answer.description.src, "Хотите получить подсказку ?")),
        tts="\n".join((answer.description.tts, "Хотите получить подсказку ?")),
        buttons=[OK_Button, REJECT_Button]
    )


@dp.request_handler(filters.ConfirmFilter(), state=GameStates.FACT)
@can_repeat
async def handler_fact_confirm(alice: AliceRequest):
    logging.info(f"User: {alice.session.user_id}: Handler->Отправка факта")
    state = State.from_request(alice)
    question_id = state.session.current_question
    question = await models.Question.get(PydanticObjectId(question_id))

    continue_answer = choice(CONTINUE_ANSWER)
    await dp.storage.set_state(alice.session.user_id, state=GameStates.QUESTION_TIME)
    return alice.response(
        "\n".join((question.fact.src, continue_answer)),
        tts="\n".join((question.fact.tts, continue_answer))
    )


@dp.request_handler(filters.RejectFilter(), state=GameStates.FACT)
@can_repeat
async def handler_fact_reject(alice: AliceRequest):
    logging.info(f"User: {alice.session.user_id}: Handler->Отказ от факта")
    return await handler_question(alice)


@dp.request_handler(filters.ConfirmFilter(), state=GameStates.HINT)
@can_repeat
async def handler_hint(alice: AliceRequest):
    # Получить ID вопроса из State-а
    # Если у пользователя достаточно баллов, даем подсказку
    # Иначе не даем
    # TODO: Добавить убавление подсказок
    logging.info(f"User: {alice.session.user_id}: Handler->Отправка подсказки")
    await dp.storage.set_state(alice.session.user_id, state=GameStates.GUESS_ANSWER)
    state = State.from_request(alice)
    question_id = state.session.current_question
    question = await models.Question.get(PydanticObjectId(question_id))
    answers = repeat_answers(alice)
    return alice.response(
        "\n".join(("Подсказка:", question.hint.src)),
        tts="\n".join(("Подсказка:", question.hint.tts)),
        buttons=answers["buttons"]
    )


@dp.request_handler(filters.RejectFilter(), state=GameStates.HINT)
@can_repeat
async def handler_hint(alice: AliceRequest):
    logging.info(f"User: {alice.session.user_id}: Handler->Отказ от подсказки")
    return await handler_fact_confirm(alice)


@can_repeat
async def handler_end(alice: AliceRequest):
    logging.info(f"User: {alice.session.user_id}: Handler->Заключение")
    await dp.storage.set_state(alice.session.user_id, GameStates.END)
    text = "Что-ж мы прибываем на конечную станцию и наше путешествие подходит к концу.\n" \
           "Это было крайне увлекательно!\n" \
           "Я давно не встречала таких интересных людей, как вы!\n" \
           "Спасибо за наше путешествие. Возвращайтесь почаще, наш поезд всегда вас ждёт!\n" \
           "Желаете начать заново?"
    return alice.response(text)


@dp.request_handler(filters.ConfirmFilter(), state=GameStates.END)
async def handler_restart_game(alice: AliceRequest):
    logging.info(f"User: {alice.session.user_id}: Handler->Перезапуск игры")
    alice._raw_kwargs["state"]["session"] = {}
    return await handler_question(alice)


@dp.request_handler(filters.RejectFilter(), state=GameStates.END)
async def handler_confirm_close_game(alice: AliceRequest):
    logging.info(f"User: {alice.session.user_id}: Handler->Завершение игры")
    return alice.response("👋", end_session=True)


# TODO: 
# 1. Отображать статистику игрока ака "Процент успешности"
# @dp.request_handler(state=None)
# async def handle_intent(alice: AliceRequest):
#     data = alice.request.nlu._raw_kwargs
#     answer = f"Intents: {data['intents']}\nTokens: {data['tokens']}"
#     return alice.response(answer, tts='ДА<speaker audio="alice-sounds-things-explosion-1.opus">')


@dp.errors_handler()
async def the_only_errors_handler(alice, e):
    logging.error('An error!', exc_info=e)
    return alice.response('Что-то пошло не так')


@web.middleware
async def log_middleware(request: Request, handler):
    data = await request.json()
    _request = data["request"]
    user_id = data['session']['user_id']
    user_fsm_state = await dp.storage.get_state(user_id)
    logging.info(
        f"User ({user_id}) enter"
        f"\nCommand: {_request.get('command', None)}"
        f"\nToken: {_request['nlu']['tokens']}"
        f"\nIntents: {_request['nlu']['intents']}"
        f"\nFSM State: {user_fsm_state}"
    )
    response = await handler(request)
    logging.info(
        f"User ({user_id}) exit"
        f"\nFSM State: {user_fsm_state}"
    )
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
    app.middlewares.extend((log_middleware, session_state_middleware))
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT, loop=dp.loop)
