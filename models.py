from dataclasses import dataclass
from typing import Optional
from os import getenv
import asyncio

from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, conlist, root_validator

from beanie import Document, Indexed, init_beanie, PydanticObjectId


@dataclass(slots=True, frozen=True)
class Diff:
    answer: str
    number: int
    coincidence: float


class Text(BaseModel):
    src: str
    tts: Optional[str]

    @root_validator(pre=True)
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
    image: Optional[Image]


# Модель из БД
class Question(Document):
    full_text: Text
    short_text: Text
    hint: Text
    answers: conlist(Answer, max_items=3)
    images: Optional[Image]
    fact: Text

    class Settings:
        name = "Questions"


async def init_database(*_):
    client = AsyncIOMotorClient(getenv("MONGO_URL"))
    await init_beanie(database=client["QUEST"], document_models=[Question])


# This is an asynchronous example, so we will access it from an async function
async def example():
    # Beanie uses Motor async client under the hood
    client = AsyncIOMotorClient(getenv("MONGO_URL"))
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
    await init_beanie(database=client["QUEST"], document_models=[Question])

    data = await Question.aggregate([
        {'$match': {'_id': {'$nin': tuple(map(lambda q: PydanticObjectId(q), ids))}}},
        {"$sample": {"size": 1}}
    ]).to_list()
    print(data)


if __name__ == "__main__":
    asyncio.run(example())
