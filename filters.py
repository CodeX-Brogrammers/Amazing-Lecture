from operator import le, ge, lt, gt, eq
from typing import Callable
import enum

from aioalice.dispatcher.filters import Filter
from aioalice.types import AliceRequest

import answer_checker
from state import State


class Operation(enum.Enum):
    LE = le
    GE = ge
    LT = lt
    GT = gt
    EQ = eq


class StateType(enum.Enum):
    SESSION = "session"
    USER = "user"
    APPLICATION = "application"


def _check_included_intent_names(alice: AliceRequest, intent_names: list[str]):
    intents: dict = alice.request.nlu._raw_kwargs["intents"]
    return any([intent_name in intents.keys() for intent_name in intent_names])


class ConfirmFilter(Filter):
    def check(self, alice: AliceRequest):
        return _check_included_intent_names(alice, ["YANDEX.CONFIRM", "AGREE"])


class RejectFilter(Filter):
    def check(self, alice: AliceRequest):
        return _check_included_intent_names(alice, ["YANDEX.REJECT", "REFUSAL"])


class RepeatFilter(Filter):
    def check(self, alice: AliceRequest):
        return _check_included_intent_names(alice, ["YANDEX.REPEAT", "REPEAT"])


class HelpFilter(Filter):
    def check(self, alice: AliceRequest):
        return _check_included_intent_names(alice, ["YANDEX.HELP", "HELP"])


class StartFilter(Filter):
    def check(self, alice: AliceRequest):
        return alice.session.new


class TrueAnswerFilter(Filter):
    # TODO: сделать проверку ответа по
    #  - полученным откенам
    #  - по численному ответу
    @staticmethod
    def check(alice: AliceRequest):
        if alice.request.type == "ButtonPressed" \
                and alice.request.payload.get("is_true", False) is True:
            return True

        state = State.from_request(alice)
        result = answer_checker.calculate_correct_answer_by_text(
            alice.request.command, state.session.current_answers
        )
        if result:
            return True

        result = answer_checker.calculate_correct_answer_by_number(
            alice.request.command, state.session.current_answers
        )
        if result:
            return True

        return False


class FalseAnswerFilter(Filter):
    # TODO: сделать проверку ответа по
    #  - полученным откенам
    #  - по численному ответу
    def check(self, alice: AliceRequest):
        return not TrueAnswerFilter.check(alice)


class ScoreFilter(Filter):
    def __init__(self, operation: Operation, count: int, state_type: StateType = StateType.USER):
        self.count = count
        self.operation: Callable[[int, int], bool] = operation.value
        self.state_type = state_type.value

    def check(self, alice: AliceRequest):
        score = alice._raw_kwargs["state"][self.state_type].get("score", 0)
        return self.operation(score, self.count)
