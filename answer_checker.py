from operator import attrgetter

import pymorphy2

from models import Diff

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
    normalize_user_answer = lemmatize(user_answer.split())
    for answer in answers:
        normalize_answer = set(str(answer[0]))
        coincidence = len(normalize_user_answer & normalize_answer) / len(normalize_answer)
        if coincidence >= threshold:
            result.append(
                Diff(
                    answer=answer[1],
                    coincidence=coincidence
                )
            )
    result.sort(key=attrgetter("coincidence"))
    return result


def calculate_correct_answer_by_text(
        user_answer: str, answers: list[tuple[int, str]], threshold: float = 0.33) -> list[Diff]:
    result = []
    normalize_user_answer = lemmatize(user_answer.split())
    for answer in answers:
        normalize_answer = lemmatize(answer[1].split())
        coincidence = len(normalize_user_answer & normalize_answer) / len(normalize_answer)
        if coincidence >= threshold:
            result.append(
                Diff(
                    answer=answer[1],
                    coincidence=coincidence
                )
            )
    result.sort(key=attrgetter("coincidence"))
    return result


if __name__ == '__main__':
    true_answer = "Рим"
    our_answers = [SimpleAnswer(number=i, text=text) for i, text in enumerate(["Рим", "Карфаген", "Флоренция"], 1)]
    answer = "думаю он находится в риме"
    print(calculate_correct_answer_by_text(answer, our_answers))

    answer = "думаю это 1"
    print(calculate_correct_answer_by_number(answer, our_answers))
