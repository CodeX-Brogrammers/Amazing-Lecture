import logging
from operator import attrgetter
from typing import Optional

import pymorphy2
from aioalice.types import AliceRequest

from models import Diff
from state import State

morph = pymorphy2.MorphAnalyzer()


def lemmatize(tokens: list[str]):
    result = set()
    for token in tokens:
        p = morph.parse(token)[0]
        result.add(p.normal_form)

    return result


def calculate_correct_answer_by_number(
        user_answer: str, answers: list[tuple[int, str]], threshold: float = 0.33) -> list[Diff]:
    result = []
    normalize_user_answer = lemmatize(user_answer.lower().split())
    for answer in answers:
        normalize_answer = set(str(answer[0]))
        coincidence = len(normalize_user_answer & normalize_answer) / len(normalize_answer)
        if coincidence >= threshold:
            result.append(
                Diff(
                    answer=answer[1],
                    number=answer[0],
                    coincidence=coincidence
                )
            )
    result.sort(key=attrgetter("coincidence"))
    return result


def calculate_correct_answer_by_text(
        user_answer: str, answers: list[tuple[int, str]], threshold: float = 0.33) -> list[Optional[Diff]]:
    result = []
    user_answer = user_answer.lower().replace("-", " ")
    normalize_user_answer = lemmatize(user_answer.split())
    for answer in answers:
        normalize_answer = lemmatize(answer[1].lower().split())
        coincidence = len(normalize_user_answer & normalize_answer) / len(normalize_answer)
        if coincidence >= threshold:
            result.append(
                Diff(
                    answer=answer[1],
                    number=answer[0],
                    coincidence=coincidence
                )
            )
    result.sort(key=attrgetter("coincidence"))
    return result


def check_user_answer(alice: AliceRequest) -> tuple[bool, Optional[Diff]]:
    state = State.from_request(alice)
    if alice.request.type == "ButtonPressed":
        logging.info(f"True answer button clicked")
        answer_number = alice.request.payload["number"]
        return alice.request.payload.get("is_true", False), \
               Diff(
                   answer=state.session.current_answers[answer_number - 1][1],
                   number=answer_number,
                   coincidence=0
               )

    result = calculate_correct_answer_by_text(
        alice.request.command, state.session.current_answers
    )
    logging.info(f"Answer by text: {result}" + str(state.session.current_answers))
    if result:
        diff = result[0]
        return state.session.current_true_answer == diff.number, diff

    result = calculate_correct_answer_by_number(
        alice.request.command, state.session.current_answers
    )
    logging.info(f"Answer by number: {result}" + str(state.session.current_answers))
    if result:
        diff = result[0]
        return state.session.current_true_answer == diff.number, diff

    return False, None


if __name__ == '__main__':
    true_answer = "Рим"
    our_answers = [(i, text) for i, text in enumerate(["Рим", "Карфаген", "Флоренция"], 1)]
    answer = "думаю он находится в риме"
    print(calculate_correct_answer_by_text(answer, our_answers))

    answer = "думаю это 1"
    print(calculate_correct_answer_by_number(answer, our_answers))
