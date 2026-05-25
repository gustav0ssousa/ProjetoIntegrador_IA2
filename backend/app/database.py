from collections.abc import AsyncIterator
from typing import Any

from bson import ObjectId
from fastapi import Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.config import Settings, get_settings


client: AsyncIOMotorClient | None = None

SENSOR_RESPONSE_FIELDS = {
    "aceleracao_x",
    "aceleracao_y",
    "aceleracao_z",
    "giroscopio_x",
    "giroscopio_y",
    "giroscopio_z",
    "umidade_solo",
    "inclinacao",
    "hw103a_ao",
    "hw103a_do",
    "hw103a_do_wet",
    "sw520_raw",
    "sw520_hits",
    "sw520_edges",
    "sw520_streak",
    "mpu_motion_g",
}


async def connect_to_mongo(settings: Settings) -> None:
    global client
    client = AsyncIOMotorClient(settings.mongodb_uri)
    await client.admin.command("ping")
    collection = get_collection(settings)
    await collection.create_index([("timestamp", -1)])
    await collection.create_index([("id_simulacao", 1), ("timestamp", -1)])


async def close_mongo_connection() -> None:
    global client
    if client is not None:
        client.close()
        client = None


def get_collection(settings: Settings = Depends(get_settings)) -> AsyncIOMotorCollection:
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB nao conectado",
        )
    return client[settings.mongodb_database][settings.mongodb_collection]


async def collection_dependency(
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[AsyncIOMotorCollection]:
    yield get_collection(settings)


def document_to_response(document: dict[str, Any]) -> dict[str, Any]:
    document["id"] = str(document.pop("_id"))
    sensores = document.get("sensores")
    if isinstance(sensores, dict):
        document["sensores"] = {
            key: value
            for key, value in sensores.items()
            if key in SENSOR_RESPONSE_FIELDS
        }
    return document


def to_object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ID de leitura invalido",
        )
    return ObjectId(value)
