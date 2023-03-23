from functools import lru_cache
from operator import attrgetter
from typing import Union
import logging

from aioalice.types import AliceRequest
import pymorphy2

from models import Diff, UserCheck
from state import State

morph = pymorphy2.MorphAnalyzer()


def lemmatize(tokens: list[str]) -> list[str]:
    result = list()
    for token in tokens:
        p = morph.parse(token)[0]
        result.append(p.normal_form)

    return result


def tokenizer(text: str) -> list[str]:
    text = text.lower().replace("-", " ")
    return text.split()


def calculate_coincidence(
        input_tokens: Union[set[str], list[str]],
        source_tokens: Union[set[str], list[str]]) -> float:
    if isinstance(input_tokens, list):
        input_tokens = set(input_tokens)
    if isinstance(source_tokens, list):
        source_tokens = set(source_tokens)
    return len(input_tokens & source_tokens) / len(source_tokens)


def calculate_correct_answer_by_number(
        user_answer: str, answers: list[tuple[int, str]], threshold: float = 0.33) -> list[Diff]:
    result = []
    normalize_user_answer = set(lemmatize(tokenizer(user_answer)))
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
    result.sort(key=attrgetter("coincidence"), reverse=True)
    return result


def calculate_correct_answer_by_text(
        user_answer: str, answers: list[tuple[int, str]], threshold: float = 0.33) -> list[Diff]:
    result = []
    normalize_user_answer = set(lemmatize(tokenizer(user_answer)))
    for answer in answers:
        normalize_answer = set(lemmatize(tokenizer(answer[1])))
        coincidence = calculate_coincidence(normalize_user_answer, normalize_answer)
        if coincidence >= threshold:
            result.append(
                Diff(
                    answer=answer[1],
                    number=answer[0],
                    coincidence=coincidence
                )
            )
    result.sort(key=attrgetter("coincidence"), reverse=True)
    return result


def find_occurrences(words: list[str], find_words: list[str], skip_index: set[int] = None) -> set:
    if skip_index is None:
        skip_index = set()
    result = set()
    last_index = -1
    for i, word in enumerate(words):
        if word in find_words and not skip_index.intersection((i,)):
            if last_index == -1:
                last_index = i
                result.add(i)
                continue

            if last_index != -1 and last_index == i - 1:
                result.add(i)
    return result


def exclude_words(words: list[str], enters: set[int]) -> bool:
    for number in enters:
        if number >= 1 and number != len(words):
            if words[number - 1] in ("не", "ни"):
                break
    else:
        return False
    return True


def find_common_words(tokens: list[str]) -> set[str]:
    tokens = [set(lemmatize(tokenizer(token))) for token in tokens]
    result = set(tokens[0])
    for token in tokens[1:]:
        result.intersection_update(token)
    return result


def remove_common_words(text_tokens: list[str], words: set[str]) -> list[str]:
    result = [word for word in text_tokens if word not in words]
    return result


def clean_user_command(command: str, answers: list[tuple[int, str]]):
    user_answer_tokens = lemmatize(tokenizer(command))
    common_answers_words = find_common_words([value[1] for value in answers])
    result = remove_common_words(user_answer_tokens, common_answers_words)

    _answers = [
        (answer[0],
         remove_common_words(lemmatize(tokenizer(answer[1])), common_answers_words))
        for answer in answers
    ]

    skip_index = set()
    text_enters = []
    for _answer in _answers:
        indexs = find_occurrences(result, _answer[1], skip_index)
        text_enters.append(indexs)
        skip_index.symmetric_difference_update(indexs)

    for _answer in _answers:
        text_enters = find_occurrences(result, _answer[1])
        text_exclude = exclude_words(result, text_enters)
        if text_exclude:
            for number in text_enters:
                result[number] = "*"

        number_enters = find_occurrences(result, [str(_answer[0])])
        number_exclude = exclude_words(result, number_enters)
        if number_exclude:
            for number in number_enters:
                result[number] = "*"

    return " ".join(result)


def check_user_answer(alice: AliceRequest) -> Union[UserCheck, list[Diff]]:
    state = State.from_request(alice)
    if alice.request.type == "ButtonPressed":
        logging.info(f"Answer button clicked")
        answer_number = alice.request.payload["number"]
        return UserCheck(
            is_true_answer=alice.request.payload.get("is_true", False),
            diff=Diff(
                answer=state.session.current_answers[answer_number - 1][1],
                number=answer_number,
                coincidence=0
            ))

    user_answer = clean_user_command(alice.request.command, state.session.current_answers)
    diffs = calculate_correct_answer_by_text(
        user_answer, state.session.current_answers
    )
    logging.info(f"Answer by text: {diffs};\nAnswers: {state.session.current_answers}")
    if len(diffs) == 1:
        diff = diffs[0]
        return UserCheck(
            is_true_answer=state.session.current_true_answer == diff.number,
            diff=diff
        )
    elif len(diffs) > 1:
        return diffs

    diffs = calculate_correct_answer_by_number(
        user_answer, state.session.current_answers
    )
    logging.info(f"Answer by number: {diffs};\nAnswers: {state.session.current_answers}")
    if len(diffs) == 1:
        diff = diffs[0]
        return UserCheck(
            is_true_answer=state.session.current_true_answer == diff.number,
            diff=diff
        )
    elif len(diffs) > 1:
        return diffs

    return UserCheck()


@lru_cache()
def declension_of_word_after_numeral(word: str, number: int) -> str:
    word = morph.parse(word)[0]
    return word.make_agree_with_number(number).word


if __name__ == '__main__':
    import time

    start = time.time()
    answer = "это точно не битва при бородино это битва при ватерлоо или аустерлиц"
    answers = [(i, answer) for i, answer in enumerate([
        "битва при аустерлица", "битва при бородино", "битва при ватерлоо"], 1)]

    print(clean_user_command(answer, answers))
    print(time.time() - start)
    clean_user_command(answer, answers)