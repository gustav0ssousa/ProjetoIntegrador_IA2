from enum import StrEnum


class NivelAlerta(StrEnum):
    VERDE = "verde"
    AMARELO = "amarelo"
    LARANJA = "laranja"
    VERMELHO = "vermelho"


UMIDADE_PULSO_MIN = 2400
UMIDADE_ALERTA_CONTINUO = 3400
ACELERACAO_ATENCAO_G = 0.4
ACELERACAO_ALERTA_G = 0.7


def calcular_movimento_g(aceleracao_x: float, aceleracao_y: float, aceleracao_z: float) -> float:
    return (aceleracao_x**2 + aceleracao_y**2 + (aceleracao_z - 1.0) ** 2) ** 0.5


def calcular_nivel_alerta(
    umidade_solo: int,
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
    movimento_g = calcular_movimento_g(aceleracao_x, aceleracao_y, aceleracao_z)

    if evento_deslizamento or inclinacao == 1 or movimento_g > ACELERACAO_ALERTA_G:
        return NivelAlerta.VERMELHO

    solo_atencao = umidade_solo >= UMIDADE_PULSO_MIN
    solo_alerta = umidade_solo >= UMIDADE_ALERTA_CONTINUO
    movimento_atencao = movimento_g > ACELERACAO_ATENCAO_G
    giro_alto = (
        abs(giroscopio_x) >= 35
        or abs(giroscopio_y) >= 35
        or abs(giroscopio_z) >= 35
    )

    sinais_de_risco = sum([solo_atencao, movimento_atencao, giro_alto])

    if solo_alerta:
        return NivelAlerta.LARANJA
    if sinais_de_risco >= 2:
        return NivelAlerta.LARANJA
    if sinais_de_risco == 1:
        return NivelAlerta.AMARELO
    return NivelAlerta.VERDE
