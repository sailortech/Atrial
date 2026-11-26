"""Testes do limite de tentativas de login (proteção contra "chutar" senhas)."""

from datetime import datetime, timedelta

import pytest

import app as modulo_app
from app import LIMITE_DE_ERROS, TentativaLogin
from conftest import SENHA_TESTE


class Relogio:
    """Relógio de mentira: o teste decide que horas são."""

    def __init__(self):
        self.momento = datetime(2026, 11, 24, 9, 0)

    def __call__(self):
        return self.momento

    def avancar(self, minutos):
        self.momento += timedelta(minutes=minutos)


@pytest.fixture
def relogio(monkeypatch):
    relogio = Relogio()
    # Troca app.agora() pelo relógio de mentira só durante o teste
    monkeypatch.setattr(modulo_app, "agora", relogio)
    return relogio


def entrar(navegador, login="ana", senha=SENHA_TESTE):
    return navegador.post("/api/login", json={"login": login, "senha": senha})


def errar(navegador, vezes, login="ana"):
    for _ in range(vezes):
        entrar(navegador, login=login, senha="chute-errado")


def entrou(resposta):
    return resposta.status_code == 200


def erro(resposta):
    return resposta.get_json()["erro"]


# ---------- Bloqueio ----------

def test_poucos_erros_nao_bloqueiam(cliente_anonimo, usuario, relogio):
    errar(cliente_anonimo, LIMITE_DE_ERROS - 1)

    assert entrou(entrar(cliente_anonimo))


def test_muitos_erros_bloqueiam_ate_a_senha_certa(cliente_anonimo, usuario, relogio):
    errar(cliente_anonimo, LIMITE_DE_ERROS)

    resposta = entrar(cliente_anonimo)  # senha CERTA, mas está bloqueado

    assert not entrou(resposta)
    assert "Tente de novo em 15 min" in erro(resposta)


def test_bloqueio_mostra_os_minutos_que_faltam(cliente_anonimo, usuario, relogio):
    errar(cliente_anonimo, LIMITE_DE_ERROS)
    relogio.avancar(10)

    resposta = entrar(cliente_anonimo)

    assert "Tente de novo em 5 min" in erro(resposta)


def test_depois_do_bloqueio_volta_a_entrar(cliente_anonimo, usuario, relogio):
    errar(cliente_anonimo, LIMITE_DE_ERROS)
    relogio.avancar(16)

    assert entrou(entrar(cliente_anonimo))


def test_durante_o_bloqueio_a_senha_nem_e_conferida(cliente_anonimo, usuario, relogio, monkeypatch):
    """Senão daria para continuar chutando durante o bloqueio."""
    errar(cliente_anonimo, LIMITE_DE_ERROS)

    conferidas = []
    monkeypatch.setattr(type(usuario), "confere_senha",
                        lambda self, senha: conferidas.append(senha) or True)
    entrar(cliente_anonimo)

    assert conferidas == []


def test_acertar_zera_os_erros(cliente_anonimo, usuario, relogio):
    errar(cliente_anonimo, LIMITE_DE_ERROS - 1)
    entrar(cliente_anonimo)          # acertou: zera
    cliente_anonimo.post("/api/logout")

    errar(cliente_anonimo, LIMITE_DE_ERROS - 1)  # de novo 4: ainda não bloqueia

    assert entrou(entrar(cliente_anonimo))


def test_erros_antigos_vencem(cliente_anonimo, usuario, relogio):
    """5 erros espalhados ao longo do dia não devem bloquear ninguém."""
    for _ in range(LIMITE_DE_ERROS):
        errar(cliente_anonimo, 1)
        relogio.avancar(20)

    assert entrou(entrar(cliente_anonimo))


def test_bloqueio_e_por_login(cliente_anonimo, usuario, admin, relogio):
    errar(cliente_anonimo, LIMITE_DE_ERROS, login="ana")

    assert entrou(entrar(cliente_anonimo, login="bia"))  # a Bia não tem nada a ver


def test_maiusculas_contam_como_o_mesmo_login(cliente_anonimo, usuario, relogio):
    for login in ["ana", "ANA", " Ana ", "aNa", "ANA"]:
        errar(cliente_anonimo, 1, login=login)

    assert not entrou(entrar(cliente_anonimo))


# ---------- Não revelar quais logins existem ----------

def test_login_inexistente_tambem_e_bloqueado(cliente_anonimo, relogio):
    errar(cliente_anonimo, LIMITE_DE_ERROS, login="ninguem")

    resposta = entrar(cliente_anonimo, login="ninguem")

    # Mesma resposta de uma conta real bloqueada: o bloqueio não
    # serve para descobrir se o login existe
    assert "Muitas tentativas" in erro(resposta)


def test_login_inexistente_demora_o_mesmo_que_um_real(cliente_anonimo, monkeypatch, relogio):
    """Confere uma senha (lenta) mesmo quando o login não existe."""
    conferidas = []
    original = modulo_app.check_password_hash

    def espiao(hash_, senha):
        conferidas.append(senha)
        return original(hash_, senha)

    monkeypatch.setattr(modulo_app, "check_password_hash", espiao)
    entrar(cliente_anonimo, login="ninguem", senha="qualquer")

    assert conferidas == ["qualquer"]


def test_login_gigante_nao_quebra(cliente_anonimo, relogio):
    resposta = entrar(cliente_anonimo, login="a" * 10_000, senha="x")

    assert resposta.status_code == 401  # recusado normalmente, sem erro 500
    assert len(TentativaLogin.query.one().login) == 50


def test_login_vazio_nao_e_registrado(cliente_anonimo, relogio):
    entrar(cliente_anonimo, login="", senha="x")

    assert TentativaLogin.query.count() == 0
