"""Testes da proteção CSRF (com ela LIGADA, ao contrário dos outros testes)."""

import re

import pytest

from app import Paciente, app as flask_app
from conftest import SENHA_TESTE


@pytest.fixture
def csrf_ligado(app):
    flask_app.config["WTF_CSRF_ENABLED"] = True


def pegar_token(html):
    """Lê o código do campo escondido, como o navegador faria."""
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def test_formulario_sem_codigo_e_recusado(csrf_ligado, cliente, criar_paciente):
    """É isto que um site malicioso conseguiria enviar: o pedido vem
    com o cookie de login, mas sem o código, que ele não tem como saber."""
    paciente = criar_paciente("Bruno")

    resposta = cliente.post(f"/pacientes/excluir/{paciente.id}", follow_redirects=True)

    assert Paciente.query.count() == 1  # não excluiu
    assert "A página estava desatualizada" in resposta.get_data(as_text=True)


def test_formulario_com_codigo_falso_e_recusado(csrf_ligado, cliente, criar_paciente):
    paciente = criar_paciente("Bruno")

    cliente.post(f"/pacientes/excluir/{paciente.id}", data={"csrf_token": "chutei"})

    assert Paciente.query.count() == 1


def test_formulario_com_codigo_da_pagina_funciona(csrf_ligado, cliente, criar_paciente):
    paciente = criar_paciente("Bruno")
    token = pegar_token(cliente.get("/pacientes").get_data(as_text=True))

    cliente.post(f"/pacientes/excluir/{paciente.id}", data={"csrf_token": token})

    assert Paciente.query.count() == 0


def test_login_tambem_exige_o_codigo(csrf_ligado, cliente_anonimo, usuario):
    # Sem código: não entra
    cliente_anonimo.post("/login", data={"login": "ana", "senha": SENHA_TESTE})
    assert cliente_anonimo.get("/pacientes").status_code == 302

    # Com o código da tela de login: entra
    token = pegar_token(cliente_anonimo.get("/login").get_data(as_text=True))
    cliente_anonimo.post(
        "/login", data={"login": "ana", "senha": SENHA_TESTE, "csrf_token": token}
    )
    assert cliente_anonimo.get("/pacientes").status_code == 200


@pytest.mark.parametrize("pagina", [
    "/pacientes", "/pacientes?parcial=1", "/pacientes/novo", "/pacientes/editar/1",
])
def test_todo_formulario_post_tem_o_codigo(cliente, criar_paciente, pagina):
    """Rede de segurança: se alguém criar um formulário novo e esquecer
    o csrf_token, este teste avisa antes de a página quebrar de verdade."""
    paciente = criar_paciente("Bruno")
    criar_paciente("Carla", status="Em atendimento")
    criar_paciente("Davi", status="Concluído")
    assert paciente.id == 1  # a página de edição usa o id 1

    html = cliente.get(pagina).get_data(as_text=True)
    formularios = re.findall(r'<form method="POST".*?</form>', html, re.S | re.I)

    assert formularios, "a página deveria ter formulários"
    for formulario in formularios:
        assert 'name="csrf_token"' in formulario, formulario[:120]


def test_tela_de_login_tem_o_codigo(cliente_anonimo):
    assert 'name="csrf_token"' in cliente_anonimo.get("/login").get_data(as_text=True)
