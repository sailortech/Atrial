"""Testes da proteção CSRF (com ela LIGADA, ao contrário dos outros testes).

No React, o código CSRF vem em /api/sessao e volta no cabeçalho
X-CSRFToken de todo pedido que muda algo (POST, PUT, DELETE).
"""

import pytest

from app import Paciente, app as flask_app
from conftest import SENHA_TESTE


@pytest.fixture
def csrf_ligado(app):
    flask_app.config["WTF_CSRF_ENABLED"] = True


def codigo(navegador):
    return navegador.get("/api/sessao").get_json()["csrf"]


def test_pedido_sem_codigo_e_recusado(csrf_ligado, cliente, criar_paciente):
    """É isto que um site malicioso conseguiria enviar: o pedido vem
    com o cookie de login, mas sem o código, que ele não tem como saber."""
    paciente = criar_paciente("Bruno")

    resposta = cliente.delete(f"/api/pacientes/{paciente.id}")

    assert resposta.status_code == 400
    assert "Recarregue a página" in resposta.get_json()["erro"]
    assert Paciente.query.count() == 1  # não excluiu


def test_pedido_com_codigo_falso_e_recusado(csrf_ligado, cliente, criar_paciente):
    paciente = criar_paciente("Bruno")

    cliente.delete(f"/api/pacientes/{paciente.id}", headers={"X-CSRFToken": "chutei"})

    assert Paciente.query.count() == 1


@pytest.mark.parametrize("metodo, endereco, corpo", [
    ("delete", "/api/pacientes/1", None),
    ("put", "/api/pacientes/1", {"nome": "X"}),
    ("post", "/api/pacientes/chamar-proximo", {"local": "Triagem"}),
])
def test_todo_metodo_que_muda_algo_exige_o_codigo(csrf_ligado, cliente, criar_paciente,
                                                   metodo, endereco, corpo):
    criar_paciente("Bruno")

    resposta = getattr(cliente, metodo)(endereco, json=corpo)

    assert resposta.status_code == 400


def test_pedido_com_o_codigo_da_sessao_funciona(csrf_ligado, cliente, criar_paciente):
    paciente = criar_paciente("Bruno")

    resposta = cliente.delete(f"/api/pacientes/{paciente.id}",
                              headers={"X-CSRFToken": codigo(cliente)})

    assert resposta.status_code == 200
    assert Paciente.query.count() == 0


def test_login_tambem_exige_o_codigo(csrf_ligado, cliente_anonimo, usuario):
    dados = {"login": "ana", "senha": SENHA_TESTE}

    # Sem código: não entra
    assert cliente_anonimo.post("/api/login", json=dados).status_code == 400

    # Com o código de /api/sessao (que é pública justamente para isso): entra
    resposta = cliente_anonimo.post("/api/login", json=dados,
                                    headers={"X-CSRFToken": codigo(cliente_anonimo)})
    assert resposta.status_code == 200


def test_leitura_nao_precisa_do_codigo(csrf_ligado, cliente):
    """GET só lê: não precisa (e o React nem manda)."""
    assert cliente.get("/api/pacientes").status_code == 200
