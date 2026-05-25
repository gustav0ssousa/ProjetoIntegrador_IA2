from datetime import datetime
from typing import Any

from app.database import document_to_response
from app.risk import (
    ACELERACAO_ALERTA_G,
    ACELERACAO_ATENCAO_G,
    UMIDADE_ALERTA_CONTINUO,
    UMIDADE_PULSO_MIN,
    NivelAlerta,
    calcular_movimento_g,
)


ALERT_LIMITS = {
    "humidity": {
        "min": 0,
        "max": 4095,
        "warningMin": UMIDADE_PULSO_MIN,
        "warningMax": UMIDADE_ALERTA_CONTINUO,
        "unit": "raw_normalizado",
    },
    "accelerometer": {
        "min": 0,
        "max": 2,
        "warningMin": ACELERACAO_ATENCAO_G,
        "warningMax": ACELERACAO_ALERTA_G,
        "unit": "g_movimento",
    },
    "vibration": {
        "min": 0,
        "max": 1,
        "warningMin": 1,
        "warningMax": 1,
        "unit": "sw520_continuo",
    },
}


def _to_iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return None
    return str(value)


def _risk_score(document: dict[str, Any]) -> int:
    nivel = document.get("nivel_alerta")
    rank = {
        NivelAlerta.VERDE.value: 10,
        NivelAlerta.AMARELO.value: 35,
        NivelAlerta.LARANJA.value: 65,
        NivelAlerta.VERMELHO.value: 90,
    }
    return rank.get(str(nivel), 0)


def _risk_summary(score: float) -> dict[str, str]:
    if score >= 80:
        return {
            "nivel": "critico",
            "cor": "vermelho",
            "mensagem": "Risco critico: sinais fortes de instabilidade foram detectados.",
        }
    if score >= 55:
        return {
            "nivel": "alto",
            "cor": "laranja",
            "mensagem": "Risco alto: os sensores indicam alteracao relevante no solo.",
        }
    if score >= 30:
        return {
            "nivel": "moderado",
            "cor": "amarelo",
            "mensagem": "Risco moderado: acompanhamento continuo recomendado.",
        }
    return {
        "nivel": "baixo",
        "cor": "verde",
        "mensagem": "Risco baixo: leituras em condicao estavel.",
    }


def montar_analytics(documents: list[dict[str, Any]]) -> dict[str, Any]:
    historico = []
    counts = {"baixo": 0, "moderado": 0, "alto": 0, "critico": 0}

    for document in documents:
        sensores = document.get("sensores") or {}
        score = _risk_score(document)
        risk = _risk_summary(score)
        counts[risk["nivel"]] += 1
        historico.append(
            {
                "id": str(document.get("_id", document.get("id", ""))),
                "horario": _to_iso(document.get("timestamp")),
                "id_simulacao": document.get("id_simulacao"),
                "pontuacao": score,
                "risco": risk["nivel"],
                "umidadeAnalogica": sensores.get("umidade_solo"),
                "vibracao": sensores.get("inclinacao"),
                "inclinacao": sensores.get("inclinacao"),
                "mpuMotionG": _series_value(document, "accelerometer"),
                "sw520Edges": sensores.get("sw520_edges"),
                "sw520Streak": sensores.get("sw520_streak"),
                "sensores": sensores,
            }
        )

    latest = documents[0] if documents else None
    latest_response = None
    if latest:
        latest_response = document_to_response(dict(latest))
        latest_response["timestamp"] = _to_iso(latest_response.get("timestamp"))
        latest_response["created_at"] = _to_iso(latest_response.get("created_at"))
    latest_score = _risk_score(latest) if latest else 0
    average = round(sum(item["pontuacao"] for item in historico) / len(historico), 2) if historico else 0

    return {
        "sucesso": True,
        "fonte": "leituras",
        "resumo": {
            "totalLeituras": len(documents),
            "mediaPontuacao": average,
            "pontuacaoAtual": latest_score,
            "ultimaAtualizacao": _to_iso(latest.get("timestamp")) if latest else None,
            "riscoAtual": _risk_summary(latest_score),
            "quantidadePorRisco": counts,
        },
        "ultimaLeitura": latest_response,
        "historicoGrafico": list(reversed(historico)),
        "historicoCompleto": historico,
    }


def _series_value(document: dict[str, Any], metric: str) -> float:
    sensores = document.get("sensores") or {}
    if metric == "humidity":
        return float(sensores.get("umidade_solo", 0))
    if metric == "vibration":
        return float(sensores.get("inclinacao", 0))
    if metric == "accelerometer":
        if sensores.get("mpu_motion_g") is not None:
            return round(float(sensores.get("mpu_motion_g", 0)), 3)
        x = float(sensores.get("aceleracao_x", 0))
        y = float(sensores.get("aceleracao_y", 0))
        z = float(sensores.get("aceleracao_z", 1))
        return round(calcular_movimento_g(x, y, z), 3)
    return 0.0


def _trend(values: list[float]) -> str:
    if len(values) < 2:
        return "stable"
    if values[-1] > values[0]:
        return "increasing"
    if values[-1] < values[0]:
        return "decreasing"
    return "stable"


def _predict(values: list[float]) -> tuple[float | None, float]:
    if not values:
        return None, 0
    if len(values) < 3:
        return round(values[-1], 2), 0.35

    x_mean = (len(values) - 1) / 2
    y_mean = sum(values) / len(values)
    numerator = sum((index - x_mean) * (value - y_mean) for index, value in enumerate(values))
    denominator = sum((index - x_mean) ** 2 for index in range(len(values)))
    slope = numerator / denominator if denominator else 0
    intercept = y_mean - slope * x_mean
    prediction = intercept + slope * len(values)
    spread = max(values) - min(values) or 1
    mean_error = sum(abs(value - (intercept + slope * index)) for index, value in enumerate(values)) / len(values)
    confidence = max(0.2, min(0.96, 1 - mean_error / spread))
    return round(prediction, 2), round(confidence, 2)


def _classify_prediction(metric: str, prediction: float | None) -> tuple[str, str]:
    if prediction is None:
        return "low", "Dados insuficientes para predicao confiavel."
    if metric == "humidity":
        if prediction >= UMIDADE_ALERTA_CONTINUO:
            return "high", "Tendencia de solo saturado."
        if prediction >= UMIDADE_PULSO_MIN:
            return "medium", "Tendencia de umidade relevante no solo."
    if metric == "vibration":
        if prediction >= 1:
            return "high", "Tendencia elevada de vibracao/inclinacao."
    if metric == "accelerometer":
        if prediction >= ACELERACAO_ALERTA_G:
            return "high", "Tendencia de movimentacao elevada pelo acelerometro."
        if prediction >= ACELERACAO_ATENCAO_G:
            return "medium", "Tendencia de movimentacao moderada."
    return "low", "Tendencia dentro da faixa esperada."


def montar_predictions(documents: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = list(reversed(documents))
    predictions = []

    for metric in ["humidity", "vibration", "accelerometer"]:
        values = [_series_value(document, metric) for document in ordered]
        prediction, confidence = _predict(values)
        risk_level, risk_description = _classify_prediction(metric, prediction)
        predictions.append(
            {
                "sensorType": metric,
                "current": round(values[-1], 2) if values else None,
                "prediction": prediction,
                "confidence": confidence,
                "trend": _trend(values),
                "riskLevel": risk_level,
                "riskDescription": risk_description,
                "timeToThreshold": None,
                "samples": len(values),
            }
        )

    return {"sucesso": True, "predictions": predictions}
