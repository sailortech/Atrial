"""Testes do relatório do dia: as contas e as horas do gráfico."""

from datetime import date, datetime

import pytest

from app import formatar_minutos, horas_do_grafico, relatorio_do_dia

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


# ---------- Horas do gráfico ----------
# O desenho (barras, eixo) é feito pelo React e testado lá
# (frontend/src/componentes/relatorio/escala.test.js). Aqui: QUAIS horas.

def test_dia_normal_mostra_o_horario_comercial():
    assert horas_do_grafico({9: 2, 14: 1}) == list(range(7, 19))  # 7h às 18h


def test_grafico_cobre_o_que_passar_do_horario_comercial():
    horas = horas_do_grafico({6: 1, 20: 2})

    assert horas == list(range(6, 21))  # sem buracos


def test_formatar_minutos():
    assert formatar_minutos(None) == "-"
    assert formatar_minutos(20.7) == "20 min"
    assert formatar_minutos(75) == "1h 15min"


def test_atendimentos_por_local(criar_paciente):
    criar_paciente("Ana", status="Concluído", local="Consultório 1", chegada=as_(8),
                   chamado_em=as_(8, 10), concluido_em=as_(8, 30))   # 20 min
    criar_paciente("Bruno", status="Concluído", local="Consultório 1", chegada=as_(9),
                   chamado_em=as_(9, 10), concluido_em=as_(9, 50))   # 40 min
    criar_paciente("Carla", status="Concluído", local="Triagem", chegada=as_(9),
                   chamado_em=as_(9, 5), concluido_em=as_(9, 15))    # 10 min

    linhas = {l["local"]: l for l in relatorio_do_dia(DIA)["por_local"]}

    assert linhas["Consultório 1"]["atendidos"] == 2
    assert linhas["Consultório 1"]["duracao_media"] == 30
    assert linhas["Triagem"]["atendidos"] == 1
    assert linhas["Consultório 2"]["atendidos"] == 0
    assert linhas["Consultório 2"]["duracao_media"] is None


def test_quem_nao_compareceu_nao_conta_como_atendido(criar_paciente):
    criar_paciente("Ana", status="Concluído", local="Triagem", chegada=as_(8),
                   chamado_em=as_(8, 10), concluido_em=as_(8, 30))   # 20 min
    criar_paciente("Bruno", status="Não compareceu", local="Triagem", chegada=as_(8),
                   chamado_em=as_(8, 40), concluido_em=as_(9, 40))   # "1h" sem atender

    dados = relatorio_do_dia(DIA)

    assert dados["atendidos"] == 1
    assert dados["nao_compareceram"] == 1
    assert dados["duracao_media"] == 20          # a hora do Bruno não entra
    triagem = next(l for l in dados["por_local"] if l["local"] == "Triagem")
    assert triagem["atendidos"] == 1
    # Mas a espera do Bruno (até ser chamado) conta: a clínica o fez esperar
    assert dados["espera_media"] == pytest.approx((10 + 40) / 2)


# ---------- API (React) ----------

def test_api_do_relatorio(cliente, dia_movimentado):
    dados = cliente.get("/api/relatorio?dia=2026-11-18").get_json()

    assert dados["dia"] == "2026-11-18"
    assert dados["anterior"] == "2026-11-17"
    assert dados["seguinte"] == "2026-11-19"
    assert dados["chegaram"] == 4
    assert dados["atendidos"] == 2
    assert dados["espera_media"] == "20 min"   # já formatado
    assert dados["maior_espera"] == "35 min"

    # Todas as horas do eixo (7h às 18h), inclusive as sem ninguém
    horas = {linha["hora"]: linha["total"] for linha in dados["por_hora"]}
    assert list(horas) == list(range(7, 19))
    assert horas[8] == 2 and horas[9] == 1 and horas[14] == 1
    assert horas[10] == 0

    urgente = next(l for l in dados["por_prioridade"] if l["prioridade"] == "Urgente")
    assert urgente["espera_media"] == "5 min"


def test_api_do_relatorio_dia_vazio(cliente):
    dados = cliente.get("/api/relatorio?dia=2020-01-01").get_json()

    assert dados["por_hora"] == []           # o React mostra "nenhuma chegada"
    assert dados["espera_media"] == "-"


def test_api_do_relatorio_dia_invalido_e_hoje(cliente):
    dados = cliente.get("/api/relatorio?dia=banana").get_json()
    assert dados["dia"] == dados["hoje"] == date.today().isoformat()


def test_api_do_relatorio_exige_login(cliente_anonimo):
    assert cliente_anonimo.get("/api/relatorio").status_code == 401
