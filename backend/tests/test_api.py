from bson import ObjectId
from fastapi.testclient import TestClient

from app.database import collection_dependency
from app.main import app


class InsertOneResult:
    inserted_id = ObjectId()


class FakeCursor:
    def __init__(self, documents):
        self.documents = list(documents)

    def sort(self, field, direction):
        reverse = direction == -1
        self.documents.sort(key=lambda item: item.get(field), reverse=reverse)
        return self

    def skip(self, offset):
        self.documents = self.documents[offset:]
        return self

    def limit(self, limit):
        self.documents = self.documents[:limit]
        return self

    def __aiter__(self):
        self._iter = iter(self.documents)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = documents or []

    async def insert_one(self, document):
        self.last_inserted = document
        return InsertOneResult()

    def find(self, _filter):
        return FakeCursor(self.documents)

    async def count_documents(self, _filter):
        return len(self.documents)


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
    assert set(body["sensores"]) == {
        "aceleracao_x",
        "aceleracao_y",
        "aceleracao_z",
        "giroscopio_x",
        "giroscopio_y",
        "giroscopio_z",
        "umidade_solo",
        "inclinacao",
    }


def test_post_api_sensors_normaliza_payload_humidity():
    collection = FakeCollection()
    app.dependency_overrides[collection_dependency] = lambda: collection
    client = TestClient(app)

    response = client.post(
        "/api/sensors",
        json={
            "sensorId": "esp32-higrometro-01",
            "sensorType": "humidity",
            "value": 2480,
            "unit": "raw",
            "metadata": {
                "deviceId": "esp32-sensores-01",
                "ao": 2480,
                "d0": 0,
                "wet": True,
            },
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["sucesso"] is True
    assert body["leitura"]["id_simulacao"] == "esp32-sensores-01"
    assert body["leitura"]["sensores"]["umidade_solo"] == 2480


def test_post_api_sensors_prioriza_umidade_normalizada():
    collection = FakeCollection()
    app.dependency_overrides[collection_dependency] = lambda: collection
    client = TestClient(app)

    response = client.post(
        "/api/sensors",
        json={
            "sensorId": "esp32-hw103a-01",
            "sensorType": "humidity",
            "value": 1800,
            "unit": "raw",
            "metadata": {
                "deviceId": "esp32-sensores-01",
                "ao": 1800,
                "umidade_norm": 3620,
            },
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["leitura"]["sensores"]["umidade_solo"] == 3620


def test_post_api_sensors_normaliza_payload_accelerometer_ms2_para_g():
    collection = FakeCollection()
    app.dependency_overrides[collection_dependency] = lambda: collection
    client = TestClient(app)

    response = client.post(
        "/api/sensors",
        json={
            "sensorId": "esp32-acelerometro-01",
            "sensorType": "accelerometer",
            "value": {"x": 0.0, "y": 0.0, "z": 9.80665},
            "unit": "m/s2",
            "metadata": {
                "deviceId": "esp32-sensores-01",
                "giroscopioX": 0.1,
                "giroscopioY": 0.2,
                "giroscopioZ": 0.3,
            },
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    sensores = response.json()["leitura"]["sensores"]
    assert sensores["aceleracao_z"] == 1.0
    assert sensores["giroscopio_x"] == 0.1


def test_post_mqtt_webhook_reutiliza_normalizador():
    collection = FakeCollection()
    app.dependency_overrides[collection_dependency] = lambda: collection
    client = TestClient(app)

    response = client.post(
        "/mqtt/webhook",
        json={
            "topic": "clearflow/sensors/vibration",
            "payload": {
                "sensorId": "esp32-vibracao-01",
                "value": 1,
                "unit": "status",
                "metadata": {"deviceId": "esp32-sensores-01"},
            },
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["reading"]["sensores"]["inclinacao"] == 1
    assert body["reading"]["evento_deslizamento"] is True


def test_get_analytics_e_alerts_derivam_leituras_reais():
    documents = [
        {
            "_id": ObjectId(),
            "timestamp": "2026-05-07T20:30:00+00:00",
            "id_simulacao": "SIM_ALERTA",
            "sensores": {
                "aceleracao_x": 0.4,
                "aceleracao_y": 0.0,
                "aceleracao_z": 1.0,
                "giroscopio_x": 0.0,
                "giroscopio_y": 0.0,
                "giroscopio_z": 0.0,
                "umidade_solo": 2900,
                "inclinacao": 0,
            },
            "nivel_alerta": "laranja",
            "evento_deslizamento": False,
        }
    ]
    app.dependency_overrides[collection_dependency] = lambda: FakeCollection(documents)
    client = TestClient(app)

    analytics_response = client.get("/analytics")
    alerts_response = client.get("/alerts")

    app.dependency_overrides.clear()

    assert analytics_response.status_code == 200
    assert analytics_response.json()["resumo"]["totalLeituras"] == 1
    assert alerts_response.status_code == 200
    assert alerts_response.json()["total"] == 1
