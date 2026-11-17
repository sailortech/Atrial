"""Testes das funções "puras": recebem um valor e devolvem outro,
sem banco nem rotas. São os testes mais simples de escrever."""

from datetime import datetime, timedelta

import pytest

from app import (
    cpf_valido,
    somente_digitos,
    formatar_cpf,
    formatar_duracao,
    primeiro_nome_e_inicial,
)


# parametrize roda o MESMO teste uma vez para cada valor da lista
@pytest.mark.parametrize("cpf", ["52998224725", "11144477735", "39053344705"])
def test_cpf_valido_aceita_cpfs_corretos(cpf):
    assert cpf_valido(cpf)


@pytest.mark.parametrize("cpf, motivo", [
    ("52998224724", "último dígito verificador errado"),
    ("52998224715", "primeiro dígito verificador errado"),
    ("11111111111", "todos os dígitos iguais"),
    ("5299822472", "só 10 dígitos"),
    ("529982247250", "12 dígitos"),
    ("", "vazio"),
])
def test_cpf_valido_recusa_cpfs_errados(cpf, motivo):
    assert not cpf_valido(cpf), motivo


def test_somente_digitos_tira_pontos_e_traco():
    assert somente_digitos("529.982.247-25") == "52998224725"
    assert somente_digitos(" abc ") == ""


def test_formatar_cpf():
    assert formatar_cpf("52998224725") == "529.982.247-25"
    # Valor com tamanho estranho é mostrado como veio, sem quebrar
    assert formatar_cpf("123") == "123"


@pytest.mark.parametrize("minutos, esperado", [
    (0, "menos de 1 min"),
    (5, "5 min"),
    (59, "59 min"),
    (60, "1h 00min"),
    (135, "2h 15min"),
])
def test_formatar_duracao(minutos, esperado):
    inicio = datetime(2026, 1, 1, 8, 0)
    fim = inicio + timedelta(minutes=minutos)
    assert formatar_duracao(inicio, fim) == esperado


def test_formatar_duracao_sem_horario():
    # Pacientes antigos não têm horário de chegada
    assert formatar_duracao(None) == "-"


@pytest.mark.parametrize("nome, esperado", [
    ("Maria da Silva Souza", "Maria S."),
    ("João Pereira", "João P."),
    ("Cher", "Cher"),
    ("  Ana   Lima  ", "Ana L."),
])
def test_nome_abreviado_do_painel(nome, esperado):
    assert primeiro_nome_e_inicial(nome) == esperado
