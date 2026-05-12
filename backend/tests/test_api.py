from bson import ObjectId
from fastapi.testclient import TestClient

from app.database import collection_dependency
from app.main import app


class InsertOneResult:
    inserted_id = ObjectId()


class FakeCollection:
    async def insert_one(self, document):
        return InsertOneResult()


def override_collection():
    return FakeCollection()


def test_post_leituras_cria_documento_com_sensores_aninhados():
    app.dependency_overrides[collection_dependency] = override_collection
    client = TestClient(app)

    response = client.post(
        "/leituras",
        json={
            "timestamp": "2026-05-07T20:30:00",
            "id_simulacao": "SIM_TESTE",
            "aceleracao_x": 0.02,
            "aceleracao_y": 0.01,
            "aceleracao_z": 1.0,
            "giroscopio_x": 0.1,
            "giroscopio_y": 0.0,
            "giroscopio_z": 0.2,
            "umidade_solo": 720,
            "chuva": 480,
            "inclinacao": 0,
            "evento_deslizamento": False,
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["id_simulacao"] == "SIM_TESTE"
    assert body["nivel_alerta"] == "verde"
    assert body["sensores"]["umidade_solo"] == 720
    assert body["sensores"]["chuva"] == 480
