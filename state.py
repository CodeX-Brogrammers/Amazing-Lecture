from typing import Optional

from aioalice.utils.helper import Helper, HelperMode, Item
from pydantic import BaseModel, conint, Field
from aioalice.types import AliceRequest


class SessionState(BaseModel):
    passed_questions: Optional[list[str]] = Field(default_factory=list)
    current_answers: Optional[list[tuple[int, str]]] = Field(default_factory=list)
    current_true_answer: Optional[int] = Field(default=None)
    current_question: Optional[str] = None


class UserState(BaseModel):
    score: Optional[conint(ge=0)] = Field(0)


class State(BaseModel):
    session: SessionState
    user: UserState
    application: dict

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
    FACT = Item()  # Выбор ответов
    HINT = Item()  # Подсказка
    END = Item()  # Завершение
