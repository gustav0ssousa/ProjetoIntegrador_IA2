from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.risk import NivelAlerta, calcular_nivel_alerta


class Sensores(BaseModel):
    aceleracao_x: float
    aceleracao_y: float
    aceleracao_z: float
    giroscopio_x: float
    giroscopio_y: float
    giroscopio_z: float
    umidade_solo: int = Field(ge=0, le=4095)
    chuva: int = Field(ge=0, le=4095)
    inclinacao: int = Field(ge=0, le=1)


class LeituraCreate(Sensores):
    timestamp: datetime | None = None
    id_simulacao: str = Field(min_length=1, max_length=80)
    nivel_alerta: NivelAlerta | None = None
    evento_deslizamento: bool = False
    observacoes_experimento: str | None = Field(default=None, max_length=500)

    @field_validator("timestamp")
    @classmethod
    def normalizar_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def sensores(self) -> Sensores:
        return Sensores(**self.model_dump(include=set(Sensores.model_fields)))

    def nivel_alerta_final(self) -> NivelAlerta:
        if self.nivel_alerta is not None:
            return self.nivel_alerta
        return calcular_nivel_alerta(
            umidade_solo=self.umidade_solo,
            chuva=self.chuva,
            inclinacao=self.inclinacao,
            aceleracao_x=self.aceleracao_x,
            aceleracao_y=self.aceleracao_y,
            aceleracao_z=self.aceleracao_z,
            giroscopio_x=self.giroscopio_x,
            giroscopio_y=self.giroscopio_y,
            giroscopio_z=self.giroscopio_z,
            evento_deslizamento=self.evento_deslizamento,
        )

    def to_document(self) -> dict[str, Any]:
        timestamp = self.timestamp or datetime.now(UTC)
        return {
            "timestamp": timestamp,
            "id_simulacao": self.id_simulacao,
            "sensores": self.sensores().model_dump(),
            "nivel_alerta": self.nivel_alerta_final().value,
            "evento_deslizamento": self.evento_deslizamento,
            "observacoes_experimento": self.observacoes_experimento,
            "created_at": datetime.now(UTC),
        }


class LeituraResponse(BaseModel):
    id: str
    timestamp: datetime
    id_simulacao: str
    sensores: Sensores
    nivel_alerta: NivelAlerta
    evento_deslizamento: bool
    observacoes_experimento: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class LeituraListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[LeituraResponse]


class HealthResponse(BaseModel):
    status: str
    database: str


class SimulacaoResumo(BaseModel):
    id_simulacao: str
    total_leituras: int
    primeiro_timestamp: datetime | None = None
    ultimo_timestamp: datetime | None = None
    eventos_deslizamento: int
    ultimo_nivel_alerta: NivelAlerta | None = None
