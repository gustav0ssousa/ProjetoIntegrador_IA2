from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status

from app.models import LeituraCreate


DEFAULT_DEVICE_ID = "esp32-sensores-01"
GRAVITY_MS2 = 9.80665


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(default)
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _int_adc(value: Any, default: int = 0) -> int:
    return max(0, min(4095, int(round(_number(value, default)))))


def _timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "sim", "yes", "on"}
    return False


def _axis_value(value: Any, unit: str) -> float:
    axis = _number(value)
    if unit.lower() in {"m/s2", "m/s²", "ms2"}:
        return axis / GRAVITY_MS2
    return axis


def normalizar_sensor_payload(payload: dict[str, Any]) -> LeituraCreate:
    sensor_type = payload.get("sensorType") or payload.get("sensor_type")
    metadata = payload.get("metadata") or {}
    value = payload.get("value")
    unit = str(payload.get("unit") or "")
    timestamp = _timestamp(payload.get("timestamp") or payload.get("createdAt"))
    device_id = str(metadata.get("deviceId") or payload.get("deviceId") or DEFAULT_DEVICE_ID)

    data: dict[str, Any] = {
        "timestamp": timestamp,
        "id_simulacao": device_id,
        "aceleracao_x": 0.0,
        "aceleracao_y": 0.0,
        "aceleracao_z": 1.0,
        "giroscopio_x": 0.0,
        "giroscopio_y": 0.0,
        "giroscopio_z": 0.0,
        "umidade_solo": 0,
        "inclinacao": 0,
        "hw103a_ao": None,
        "hw103a_do": None,
        "hw103a_do_wet": None,
        "sw520_raw": None,
        "sw520_hits": None,
        "sw520_edges": None,
        "sw520_streak": None,
        "mpu_motion_g": None,
        "evento_deslizamento": False,
        "observacoes_experimento": f"Payload compat sensores_pi: {sensor_type or 'unknown'}",
    }

    if sensor_type == "humidity":
        data["umidade_solo"] = _int_adc(
            metadata.get("moistureNormalized", metadata.get("umidade_norm", metadata.get("ao", value)))
        )
        data["hw103a_ao"] = _int_adc(metadata.get("hw103a_ao", metadata.get("ao", data["umidade_solo"])))
        data["hw103a_do"] = int(_boolish(metadata.get("d0", metadata.get("do", 0))))
        data["hw103a_do_wet"] = _boolish(metadata.get("hw103a_do_wet", metadata.get("wet", False)))
        data["observacoes_experimento"] = "Payload compat sensores_pi: humidity"
    elif sensor_type == "vibration":
        detected = _boolish(metadata.get("vibrando")) or _boolish(payload.get("vibrando")) or _boolish(payload.get("detected"))
        digital = metadata.get("digitalRead", value)
        detected = detected or _boolish(digital)
        data["inclinacao"] = 1 if detected else 0
        data["sw520_raw"] = int(_boolish(digital))
        data["sw520_hits"] = int(_number(metadata.get("hits", metadata.get("sw520_hits", 0))))
        data["sw520_edges"] = int(_number(metadata.get("edges", metadata.get("sw520_edges", 0))))
        data["sw520_streak"] = int(_number(metadata.get("streak", metadata.get("sw520_streak", 0))))
        data["evento_deslizamento"] = detected
        data["observacoes_experimento"] = "Payload compat sensores_pi: vibration"
    elif sensor_type == "accelerometer":
        if not isinstance(value, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Payload accelerometer deve conter value com x, y e z",
            )
        data["aceleracao_x"] = _axis_value(value.get("x"), unit)
        data["aceleracao_y"] = _axis_value(value.get("y"), unit)
        data["aceleracao_z"] = _axis_value(value.get("z", 1.0), unit)
        data["giroscopio_x"] = _number(metadata.get("giroscopioX", metadata.get("gyroX", 0)))
        data["giroscopio_y"] = _number(metadata.get("giroscopioY", metadata.get("gyroY", 0)))
        data["giroscopio_z"] = _number(metadata.get("giroscopioZ", metadata.get("gyroZ", 0)))
        data["mpu_motion_g"] = _number(metadata.get("mpuMotionG", metadata.get("mpu_motion_g", 0)))
        data["observacoes_experimento"] = "Payload compat sensores_pi: accelerometer"
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"sensorType invalido ou ausente: {sensor_type}",
        )

    return LeituraCreate(**data)


def normalizar_mqtt_payload(payload: dict[str, Any]) -> LeituraCreate:
    topic = payload.get("topic")
    body = payload.get("payload")
    if not topic or not isinstance(body, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payload MQTT invalido. Esperado: { topic, payload }",
        )

    sensor_type = str(topic).split("/")[-1]
    return normalizar_sensor_payload(
        {
            "sensorId": body.get("sensorId"),
            "sensorType": sensor_type,
            "value": body.get("value"),
            "unit": body.get("unit"),
            "metadata": body.get("metadata") or {},
            "timestamp": payload.get("timestamp"),
        }
    )


def leitura_document_to_sensor_readings(document: dict[str, Any]) -> list[dict[str, Any]]:
    sensores = document.get("sensores") or {}
    timestamp = document.get("timestamp") or document.get("created_at")
    created_at = timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp
    base = {
        "deviceId": document.get("id_simulacao", DEFAULT_DEVICE_ID),
        "timestamp": created_at,
        "createdAt": created_at,
        "metadata": {
            "leituraId": str(document.get("_id", document.get("id", ""))),
            "nivel_alerta": document.get("nivel_alerta"),
            "evento_deslizamento": document.get("evento_deslizamento", False),
        },
    }

    aceleracao_x = _number(sensores.get("aceleracao_x"))
    aceleracao_y = _number(sensores.get("aceleracao_y"))
    aceleracao_z = _number(sensores.get("aceleracao_z", 1.0))
    magnitude = (aceleracao_x**2 + aceleracao_y**2 + aceleracao_z**2) ** 0.5

    return [
        {
            **base,
            "sensorId": "esp32-higrometro-01",
            "sensorType": "humidity",
            "value": sensores.get("umidade_solo", 0),
            "unit": "raw",
            "ao": sensores.get("umidade_solo", 0),
        },
        {
            **base,
            "sensorId": "esp32-vibracao-01",
            "sensorType": "vibration",
            "value": sensores.get("inclinacao", 0),
            "unit": "status",
            "digitalRead": sensores.get("inclinacao", 0),
            "vibrando": bool(sensores.get("inclinacao", 0)),
            "detected": bool(sensores.get("inclinacao", 0)),
            "edges": sensores.get("sw520_edges", 0),
            "streak": sensores.get("sw520_streak", 0),
        },
        {
            **base,
            "sensorId": "esp32-acelerometro-01",
            "sensorType": "accelerometer",
            "value": {
                "x": aceleracao_x,
                "y": aceleracao_y,
                "z": aceleracao_z,
            },
            "unit": "g",
            "accelerometer": {
                "x": aceleracao_x,
                "y": aceleracao_y,
                "z": aceleracao_z,
                "magnitude": round(magnitude, 2),
                "motionG": sensores.get("mpu_motion_g"),
            },
            "giroscopio": {
                "x": sensores.get("giroscopio_x", 0),
                "y": sensores.get("giroscopio_y", 0),
                "z": sensores.get("giroscopio_z", 0),
            },
        },
    ]
