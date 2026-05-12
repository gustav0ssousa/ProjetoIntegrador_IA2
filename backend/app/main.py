from contextlib import asynccontextmanager
from csv import DictWriter
from datetime import UTC, datetime
from io import StringIO
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorCollection

from app.config import Settings, get_settings
from app.database import (
    close_mongo_connection,
    collection_dependency,
    connect_to_mongo,
    document_to_response,
    get_collection,
    to_object_id,
)
from app.models import (
    HealthResponse,
    LeituraCreate,
    LeituraListResponse,
    LeituraResponse,
    SimulacaoResumo,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await connect_to_mongo(settings)
    yield
    await close_mongo_connection()


app = FastAPI(
    title="API de Monitoramento de Deslizamentos",
    description="Recebe leituras do ESP32, salva no MongoDB e disponibiliza consulta/exportacao.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def filtro_leituras(
    id_simulacao: str | None = None,
    inicio: datetime | None = None,
    fim: datetime | None = None,
) -> dict:
    filtro: dict = {}
    if id_simulacao:
        filtro["id_simulacao"] = id_simulacao
    periodo: dict = {}
    if inicio:
        periodo["$gte"] = inicio.replace(tzinfo=UTC) if inicio.tzinfo is None else inicio.astimezone(UTC)
    if fim:
        periodo["$lte"] = fim.replace(tzinfo=UTC) if fim.tzinfo is None else fim.astimezone(UTC)
    if periodo:
        filtro["timestamp"] = periodo
    return filtro


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"message": "API de Monitoramento de Deslizamentos"}


@app.get("/health", response_model=HealthResponse)
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    collection = get_collection(settings)
    await collection.database.client.admin.command("ping")
    return HealthResponse(status="ok", database=settings.mongodb_database)


@app.post(
    "/leituras",
    response_model=LeituraResponse,
    status_code=status.HTTP_201_CREATED,
)
async def criar_leitura(
    leitura: LeituraCreate,
    collection: Annotated[AsyncIOMotorCollection, Depends(collection_dependency)],
) -> dict:
    document = leitura.to_document()
    result = await collection.insert_one(document)
    document["_id"] = result.inserted_id
    return document_to_response(document)


@app.get("/leituras", response_model=LeituraListResponse)
async def listar_leituras(
    collection: Annotated[AsyncIOMotorCollection, Depends(collection_dependency)],
    id_simulacao: str | None = None,
    inicio: datetime | None = None,
    fim: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> LeituraListResponse:
    filtro = filtro_leituras(id_simulacao=id_simulacao, inicio=inicio, fim=fim)
    total = await collection.count_documents(filtro)
    cursor = collection.find(filtro).sort("timestamp", -1).skip(offset).limit(limit)
    items = [document_to_response(document) async for document in cursor]
    return LeituraListResponse(total=total, limit=limit, offset=offset, items=items)


@app.get("/leituras/export/csv")
async def exportar_leituras_csv(
    collection: Annotated[AsyncIOMotorCollection, Depends(collection_dependency)],
    id_simulacao: str | None = None,
    inicio: datetime | None = None,
    fim: datetime | None = None,
    limit: int = Query(default=5000, ge=1, le=50000),
) -> Response:
    filtro = filtro_leituras(id_simulacao=id_simulacao, inicio=inicio, fim=fim)
    cursor = collection.find(filtro).sort("timestamp", 1).limit(limit)

    buffer = StringIO()
    campos = [
        "id",
        "timestamp",
        "id_simulacao",
        "aceleracao_x",
        "aceleracao_y",
        "aceleracao_z",
        "giroscopio_x",
        "giroscopio_y",
        "giroscopio_z",
        "umidade_solo",
        "chuva",
        "inclinacao",
        "nivel_alerta",
        "evento_deslizamento",
        "observacoes_experimento",
    ]
    writer = DictWriter(buffer, fieldnames=campos)
    writer.writeheader()

    async for document in cursor:
        sensores = document.get("sensores", {})
        writer.writerow(
            {
                "id": str(document["_id"]),
                "timestamp": document.get("timestamp"),
                "id_simulacao": document.get("id_simulacao"),
                "aceleracao_x": sensores.get("aceleracao_x"),
                "aceleracao_y": sensores.get("aceleracao_y"),
                "aceleracao_z": sensores.get("aceleracao_z"),
                "giroscopio_x": sensores.get("giroscopio_x"),
                "giroscopio_y": sensores.get("giroscopio_y"),
                "giroscopio_z": sensores.get("giroscopio_z"),
                "umidade_solo": sensores.get("umidade_solo"),
                "chuva": sensores.get("chuva"),
                "inclinacao": sensores.get("inclinacao"),
                "nivel_alerta": document.get("nivel_alerta"),
                "evento_deslizamento": document.get("evento_deslizamento"),
                "observacoes_experimento": document.get("observacoes_experimento"),
            }
        )

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="leituras.csv"'},
    )


@app.get("/leituras/{leitura_id}", response_model=LeituraResponse)
async def obter_leitura(
    leitura_id: str,
    collection: Annotated[AsyncIOMotorCollection, Depends(collection_dependency)],
) -> dict:
    document = await collection.find_one({"_id": to_object_id(leitura_id)})
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leitura nao encontrada",
        )
    return document_to_response(document)


@app.get("/simulacoes", response_model=list[SimulacaoResumo])
async def listar_simulacoes(
    collection: Annotated[AsyncIOMotorCollection, Depends(collection_dependency)],
) -> list[dict]:
    pipeline = [
        {"$sort": {"timestamp": 1}},
        {
            "$group": {
                "_id": "$id_simulacao",
                "total_leituras": {"$sum": 1},
                "primeiro_timestamp": {"$first": "$timestamp"},
                "ultimo_timestamp": {"$last": "$timestamp"},
                "eventos_deslizamento": {
                    "$sum": {"$cond": ["$evento_deslizamento", 1, 0]}
                },
                "ultimo_nivel_alerta": {"$last": "$nivel_alerta"},
            }
        },
        {"$sort": {"ultimo_timestamp": -1}},
    ]
    simulacoes = []
    async for item in collection.aggregate(pipeline):
        item["id_simulacao"] = item.pop("_id")
        simulacoes.append(item)
    return simulacoes
