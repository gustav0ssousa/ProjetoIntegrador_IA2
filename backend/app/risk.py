from enum import StrEnum


class NivelAlerta(StrEnum):
    VERDE = "verde"
    AMARELO = "amarelo"
    LARANJA = "laranja"
    VERMELHO = "vermelho"


def calcular_nivel_alerta(
    umidade_solo: int,
    chuva: int,
    inclinacao: int,
    aceleracao_x: float,
    aceleracao_y: float,
    aceleracao_z: float,
    giroscopio_x: float,
    giroscopio_y: float,
    giroscopio_z: float,
    evento_deslizamento: bool = False,
) -> NivelAlerta:
    """Heuristica inicial para classificar risco com fusao simples de sensores.

    Os limites usam leituras ADC comuns do ESP32, de 0 a 4095. Ajuste depois da
    calibracao real dos sensores na maquete.
    """
    if evento_deslizamento or inclinacao == 1:
        return NivelAlerta.VERMELHO

    chuva_presente = chuva >= 700
    solo_umido = umidade_solo >= 1800
    solo_saturado = umidade_solo >= 2800
    vibracao = (
        abs(aceleracao_x) >= 0.35
        or abs(aceleracao_y) >= 0.35
        or abs(aceleracao_z - 1.0) >= 0.45
        or abs(giroscopio_x) >= 35
        or abs(giroscopio_y) >= 35
        or abs(giroscopio_z) >= 35
    )

    sinais_de_risco = sum([chuva_presente, solo_umido, vibracao])

    if solo_saturado and chuva_presente and vibracao:
        return NivelAlerta.VERMELHO
    if sinais_de_risco >= 2:
        return NivelAlerta.LARANJA
    if sinais_de_risco == 1:
        return NivelAlerta.AMARELO
    return NivelAlerta.VERDE
