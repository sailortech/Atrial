"""Testes do relatório do dia: as contas e o desenho do gráfico."""

from datetime import date, datetime

import pytest

from app import formatar_minutos, grafico_por_hora, relatorio_do_dia

DIA = date(2026, 11, 18)


def as_(hora, minuto=0, dia=DIA):
    """as_(9, 30) -> 18/11/2026 às 09:30"""
    return datetime(dia.year, dia.month, dia.day, hora, minuto)


@pytest.fixture
def dia_movimentado(criar_paciente):
    """Um dia com 4 pacientes em situações diferentes."""
    # Chegou 8:00, chamada 8:20 (espera 20), concluída 8:50 (duração 30)
    criar_paciente("Ana", status="Concluído", chegada=as_(8), chamado_em=as_(8, 20),
                   concluido_em=as_(8, 50))
    # Urgente: chegou 8:30, chamado 8:35 (espera 5), concluído 9:15 (duração 40)
    criar_paciente("Bruno", prioridade="Urgente", status="Concluído",
                   chegada=as_(8, 30), chamado_em=as_(8, 35), concluido_em=as_(9, 15))
    # Em atendimento: chegou 9:00, chamado 9:35 (espera 35)
    criar_paciente("Carla", status="Em atendimento", chegada=as_(9), chamado_em=as_(9, 35))
    # Ainda na fila
    criar_paciente("Davi", status="Aguardando", chegada=as_(14))


def test_contagens_do_dia(dia_movimentado):
    dados = relatorio_do_dia(DIA)

    assert dados["chegaram"] == 4
    assert dados["atendidos"] == 2  # só Ana e Bruno foram concluídos


def test_tempos_do_dia(dia_movimentado):
    dados = relatorio_do_dia(DIA)

    assert dados["espera_media"] == pytest.approx((20 + 5 + 35) / 3)
    assert dados["maior_espera"] == 35
    assert dados["duracao_media"] == pytest.approx((30 + 40) / 2)


def test_por_prioridade(dia_movimentado):
    linhas = {l["prioridade"]: l for l in relatorio_do_dia(DIA)["por_prioridade"]}

    assert linhas["Urgente"]["chegaram"] == 1
    assert linhas["Urgente"]["espera_media"] == 5
    assert linhas["Normal"]["chegaram"] == 3
    assert linhas["Normal"]["chamados"] == 2  # Davi ainda não foi chamado
    assert linhas["Preferencial"]["espera_media"] is None  # ninguém no dia


def test_chegadas_por_hora(dia_movimentado):
    assert relatorio_do_dia(DIA)["por_hora"] == {8: 2, 9: 1, 14: 1}


def test_outros_dias_nao_entram(criar_paciente):
    criar_paciente("Ontem", chegada=as_(10, dia=date(2026, 11, 17)))

    dados = relatorio_do_dia(DIA)

    assert dados["chegaram"] == 0
    assert dados["espera_media"] is None


def test_quem_chegou_ontem_e_foi_atendido_hoje(criar_paciente):
    """Chegou às 23h e foi atendido depois da meia-noite: a espera
    conta no dia da CHAMADA, a chegada no dia anterior."""
    criar_paciente("Noturno", status="Concluído",
                   chegada=as_(23, 30, dia=date(2026, 11, 17)),
                   chamado_em=as_(0, 10), concluido_em=as_(0, 40))

    dados = relatorio_do_dia(DIA)

    assert dados["chegaram"] == 0
    assert dados["atendidos"] == 1
    assert dados["espera_media"] == 40


def test_pacientes_antigos_sem_horario_nao_quebram(criar_paciente):
    criar_paciente("Antigo", chegada=None)

    assert relatorio_do_dia(DIA)["chegaram"] == 0


# ---------- Gráfico ----------

def test_grafico_vazio():
    assert grafico_por_hora({}) is None


def test_grafico_cobre_o_horario_comercial_e_o_que_passar_dele():
    horas = [b["hora"] for b in grafico_por_hora({6: 1, 20: 2})["barras"]]

    assert horas[0] == 6 and horas[-1] == 20
    assert horas == list(range(6, 21))  # sem buracos


def test_barra_mais_alta_encosta_no_topo_do_eixo():
    grafico = grafico_por_hora({9: 4, 10: 2})

    topo_eixo = grafico["marcas"][-1]
    assert topo_eixo["valor"] == 4
    assert topo_eixo["y"] == grafico["topo"]


@pytest.mark.parametrize("maior, ultima_marca", [(3, 3), (7, 8), (23, 25), (48, 50)])
def test_eixo_usa_numeros_redondos(maior, ultima_marca):
    marcas = [m["valor"] for m in grafico_por_hora({9: maior})["marcas"]]

    assert marcas[-1] == ultima_marca
    assert len(marcas) <= 6  # 0 + no máximo 5 marcas


def test_hora_sem_chegadas_nao_desenha_barra():
    barras = {b["hora"]: b for b in grafico_por_hora({9: 2})["barras"]}

    assert barras[9]["caminho"] is not None
    assert barras[10]["caminho"] is None


# ---------- Página ----------

def test_pagina_do_relatorio(cliente, dia_movimentado):
    html = cliente.get("/relatorio?dia=2026-11-18").get_data(as_text=True)

    assert "Chegadas por hora" in html
    assert "<svg" in html
    assert "20 min" in html  # espera média: (20 + 5 + 35) / 3


def test_dia_sem_movimento(cliente):
    html = cliente.get("/relatorio?dia=2020-01-01").get_data(as_text=True)

    assert "Nenhuma chegada registrada" in html


def test_dia_invalido_mostra_hoje(cliente):
    assert cliente.get("/relatorio?dia=banana").status_code == 200


def test_relatorio_exige_login(cliente_anonimo):
    assert cliente_anonimo.get("/relatorio").status_code == 302


def test_formatar_minutos():
    assert formatar_minutos(None) == "-"
    assert formatar_minutos(20.7) == "20 min"
    assert formatar_minutos(75) == "1h 15min"
