from dataclasses import dataclass
from typing import Optional, Union
from os import getenv
import asyncio
import enum

from beanie import Document, Indexed, init_beanie, PydanticObjectId
from pydantic import BaseModel, conlist, model_validator, Field
from motor.motor_asyncio import AsyncIOMotorClient

from settings import settings


class RepeatKey(enum.Enum):
    LAST = "last"
    HINT = "hint"
    QUESTION = "question"


@dataclass(slots=True, frozen=True)
class CleanAnswer:
    src: str
    clean: list[str]
    number: int


@dataclass(slots=True, frozen=True)
class Diff:
    answer: str
    number: int
    coincidence: float


@dataclass(slots=True, frozen=True)
class UserCheck:
    diff: Optional[Diff] = None
    is_true_answer: bool = False


class Text(BaseModel):
    src: str
    tts: Optional[str]

    @model_validator(mode='before')
    def check_tts(cls, kwargs: dict):
        if kwargs.get("tts", None) is None:
            kwargs["tts"] = kwargs["src"]
        return kwargs


class Image(BaseModel):
    src: str
    yandex_id: str


class Answer(BaseModel):
    text: Text
    description: Text
    is_true: bool = False


class QuestionStatistic(Document):
    question_id: Indexed(str, unique=True)


class UserData(Document):
    user_id: Indexed(str, unique=True)
    passed_questions: list[PydanticObjectId] = Field(default_factory=list)

    @classmethod
    async def get_user_data(cls, user_id: str) -> "UserData":
        user_data = await cls.find_one({"user_id": user_id})

        if user_data is None:
            user_data = UserData(user_id=user_id)
            await user_data.save()

        return user_data

    async def add_passed_question(self, question_id: Union[str, PydanticObjectId]):
        if question_id not in self.passed_questions:
            if isinstance(question_id, str):
                question_id = PydanticObjectId(question_id)
            self.passed_questions.append(question_id)
            await self.save()

"""
user_id
|-> Пройденные верно вопросы list(question_id)
|-> Пройденные неверно вопросы list(question_id)
"""

# Модель из БД
class Question(Document):
    full_text: Text
    short_text: Text
    hint: Text
    answers: conlist(Answer, max_length=3)
    image: Optional[Image]
    fact: Text

    class Settings:
        name = "Questions"


async def init_database(*_):
    client = AsyncIOMotorClient(settings.mongodb_url)
    await init_beanie(database=client["QUEST"], document_models=[Question, UserData])


# This is an asynchronous example, so we will access it from an async function
async def example():
    # Beanie uses Motor async client under the hood
    client = AsyncIOMotorClient(settings.mongodb_url)
    ids = [
        PydanticObjectId("640dd396fda67cd71b9c9f3a"),
        PydanticObjectId("640dd396fda67cd71b9c9f39"),
        PydanticObjectId("640dd396fda67cd71b9c9f38"),
        PydanticObjectId("640dd396fda67cd71b9c9f37"),
        PydanticObjectId("640dd396fda67cd71b9c9f36"),
        PydanticObjectId("640dd396fda67cd71b9c9f3e"),
        PydanticObjectId("640dd396fda67cd71b9c9f3d"),
        PydanticObjectId("640dd396fda67cd71b9c9f3c"),
        PydanticObjectId("640dd396fda67cd71b9c9f3b"),
    ]
    # Initialize beanie with the Product document class
    await init_beanie(database=client["QUEST"], document_models=[Question, UserData])

    data = await UserData.get_user_data("super123")
    data.passed_questions = []
    await data.save()
    data = await Question.aggregate([
        {'$match': {'_id': {'$nin': data.passed_questions}}},
        {"$sample": {"size": 1}}
    ]).to_list()
    print(*data, sep="\n")

    #
    # data = await UserData.get_user_data("super123")
    # await data.add_passed_question("640dd396fda67cd71b9c9f3a")
    # print(data)
    # data = await UserData.get_user_data("super123")
    # print(data)


if __name__ == "__main__":
    asyncio.run(example())
