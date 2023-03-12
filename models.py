from typing import Optional
from enum import Enum
from os import getenv
import asyncio

from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, conlist, root_validator

from beanie import Document, Indexed, init_beanie


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
    client = AsyncIOMotorClient(getenv("MONGODB_URL"))
    await init_beanie(database=client["QUEST"], document_models=[Question])


# This is an asynchronous example, so we will access it from an async function
async def example():
    # Beanie uses Motor async client under the hood
    client = AsyncIOMotorClient(getenv("MONGO_URL"))

    # Initialize beanie with the Product document class
    await init_beanie(database=client["QUEST"], document_models=[Question])

    questions = await Question.find_all().to_list()
    print(questions)


if __name__ == "__main__":
    asyncio.run(example())
