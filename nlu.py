from functools import lru_cache
from operator import attrgetter
from typing import Optional
import logging

from aioalice.types import AliceRequest
import pymorphy2

from models import Diff
from state import State

morph = pymorphy2.MorphAnalyzer()


def lemmatize(tokens: list[str]):
    result = set()
    for token in tokens:
        p = morph.parse(token)[0]
        result.add(p.normal_form)

    return result


def tokenizer(text: str) -> list[str]:
    text = text.lower().replace("-", " ")
    return text.split()


def calculate_coincidence(input_tokens: set[str], source_tokens: set[str]) -> float:
    return len(input_tokens & source_tokens) / len(source_tokens)


def calculate_correct_answer_by_number(
        user_answer: str, answers: list[tuple[int, str]], threshold: float = 0.33) -> Optional[Diff]:
    result = []
    normalize_user_answer = lemmatize(tokenizer(user_answer))
    for answer in answers:
        normalize_answer = set(str(answer[0]))
        coincidence = calculate_coincidence(normalize_user_answer, normalize_answer)
        if coincidence >= threshold:
            result.append(
                Diff(
                    answer=answer[1],
                    number=answer[0],
                    coincidence=coincidence
                )
            )
    result.sort(key=attrgetter("coincidence"))
    if result:
        return result[0]
    return None


def calculate_correct_answer_by_text(
        user_answer: str, answers: list[tuple[int, str]], threshold: float = 0.33) -> Optional[Diff]:
    result = []
    normalize_user_answer = lemmatize(tokenizer(user_answer))
    for answer in answers:
        normalize_answer = lemmatize(tokenizer(answer[1]))
        coincidence = calculate_coincidence(normalize_user_answer, normalize_answer)
        if coincidence >= threshold:
            result.append(
                Diff(
                    answer=answer[1],
                    number=answer[0],
                    coincidence=coincidence
                )
            )
    result.sort(key=attrgetter("coincidence"))
    if result:
        return result[0]
    return None


def check_user_answer(alice: AliceRequest) -> tuple[bool, Optional[Diff]]:
    state = State.from_request(alice)
    if alice.request.type == "ButtonPressed":
        logging.info(f"Answer button clicked")
        answer_number = alice.request.payload["number"]
        return alice.request.payload.get("is_true", False), \
               Diff(
                   answer=state.session.current_answers[answer_number - 1][1],
                   number=answer_number,
                   coincidence=0
               )

    diff = calculate_correct_answer_by_text(
        alice.request.command, state.session.current_answers
    )
    logging.info(f"Answer by text: {diff};\nAnswers: {state.session.current_answers}")
    if diff:
        return state.session.current_true_answer == diff.number, diff

    diff = calculate_correct_answer_by_number(
        alice.request.command, state.session.current_answers
    )
    logging.info(f"Answer by number: {diff};\nAnswers: {state.session.current_answers}")
    if diff:
        return state.session.current_true_answer == diff.number, diff

    return False, None


@lru_cache()
def declension_of_word_after_numeral(word: str, number: int) -> str:
    word = morph.parse(word)[0]
    return word.make_agree_with_number(number).word


if __name__ == '__main__':
    true_answer = "Рим"
    our_answers = [(i, text) for i, text in enumerate(["Рим", "Карфаген", "Флоренция"], 1)]
    answer = "думаю он находится в риме"
    print(calculate_correct_answer_by_text(answer, our_answers))

    answer = "думаю это 1"
    print(calculate_correct_answer_by_number(answer, our_answers))
