from aioalice.dispatcher.filters import Filter
from aioalice.types import AliceRequest


def _check_included_intent_names(alice: AliceRequest, intent_names: list[str]):
    intents: dict = alice.request.nlu._raw_kwargs["intents"]
    return any([intent_name in intents.keys() for intent_name in intent_names])


class ConfirmFilter(Filter):
    def check(self, alice: AliceRequest):
        return _check_included_intent_names(alice, ["YANDEX.CONFIRM"])


class RejectFilter(Filter):
    def check(self, alice: AliceRequest):
        return _check_included_intent_names(alice, ["YANDEX.REJECT"])


class RepeatFilter(Filter):
    def check(self, alice: AliceRequest):
        return _check_included_intent_names(alice, ["YANDEX.REPEAT"])


class HelpFilter(Filter):
    def check(self, alice: AliceRequest):
        return _check_included_intent_names(alice, ["YANDEX.HELP"])


class StartFilter(Filter):
    def check(self, alice: AliceRequest):
        return alice.session.new
