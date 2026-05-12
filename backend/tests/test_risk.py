from app.risk import NivelAlerta, calcular_nivel_alerta


def test_calcula_verde_sem_sinais_de_risco():
    assert (
        calcular_nivel_alerta(
            umidade_solo=300,
            chuva=100,
            inclinacao=0,
            aceleracao_x=0.01,
            aceleracao_y=0.01,
            aceleracao_z=1.0,
            giroscopio_x=0.0,
            giroscopio_y=0.0,
            giroscopio_z=0.0,
        )
        == NivelAlerta.VERDE
    )


def test_calcula_laranja_com_chuva_e_solo_umido():
    assert (
        calcular_nivel_alerta(
            umidade_solo=1900,
            chuva=800,
            inclinacao=0,
            aceleracao_x=0.01,
            aceleracao_y=0.01,
            aceleracao_z=1.0,
            giroscopio_x=0.0,
            giroscopio_y=0.0,
            giroscopio_z=0.0,
        )
        == NivelAlerta.LARANJA
    )


def test_calcula_vermelho_com_inclinacao_ativada():
    assert (
        calcular_nivel_alerta(
            umidade_solo=300,
            chuva=100,
            inclinacao=1,
            aceleracao_x=0.01,
            aceleracao_y=0.01,
            aceleracao_z=1.0,
            giroscopio_x=0.0,
            giroscopio_y=0.0,
            giroscopio_z=0.0,
        )
        == NivelAlerta.VERMELHO
    )
