from collections.abc import AsyncIterator
from typing import Any

from bson import ObjectId
from fastapi import Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.config import Settings, get_settings


client: AsyncIOMotorClient | None = None


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
    return document


def to_object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ID de leitura invalido",
        )
    return ObjectId(value)
