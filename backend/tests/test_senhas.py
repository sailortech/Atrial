"""Testes de senha: trocar a própria, redefinir (admin) e troca obrigatória."""

import pytest

from app import Usuario, db
from conftest import SENHA_TESTE, navegador_logado

NOVA = "outra-senha-456"


def trocar(cliente, atual=SENHA_TESTE, nova=NOVA, confirmacao=None):
    return cliente.post("/minha-senha", data={
        "atual": atual,
        "nova": nova,
        "confirmacao": nova if confirmacao is None else confirmacao,
    }, follow_redirects=True)


# ---------- Minha senha ----------

def test_trocar_a_propria_senha(cliente, usuario):
    resposta = trocar(cliente)

    assert "Senha alterada" in resposta.get_data(as_text=True)
    assert usuario.confere_senha(NOVA)
    assert not usuario.confere_senha(SENHA_TESTE)


@pytest.mark.parametrize("dados, erro", [
    ({"atual": "errada"}, "senha atual está incorreta"),
    ({"nova": "curta"}, "pelo menos 8"),
    ({"confirmacao": "diferente-123"}, "confirmação não é igual"),
    ({"nova": SENHA_TESTE}, "diferente da atual"),
])
def test_troca_invalida_nao_muda_a_senha(cliente, usuario, dados, erro):
    resposta = trocar(cliente, **dados)

    html = resposta.get_data(as_text=True)
    assert erro in html
    assert usuario.confere_senha(SENHA_TESTE)  # continua a mesma


def test_senhas_digitadas_nao_voltam_na_pagina(cliente):
    resposta = trocar(cliente, atual="errada-mas-secreta", nova="nova-secreta-789")

    html = resposta.get_data(as_text=True)
    assert "errada-mas-secreta" not in html
    assert "nova-secreta-789" not in html


def test_nome_no_menu_leva_para_minha_senha(cliente):
    html = cliente.get("/pacientes").get_data(as_text=True)

    assert 'href="/minha-senha"' in html


# ---------- Redefinir (administração) ----------

def test_admin_redefine_senha_de_quem_esqueceu(cliente_admin, usuario):
    cliente_admin.post(f"/usuarios/{usuario.id}/senha", data={"nova": "provisoria-1"})

    assert usuario.confere_senha("provisoria-1")
    assert usuario.trocar_senha  # vai ter que criar a própria


def test_redefinir_com_senha_curta(cliente_admin, usuario):
    resposta = cliente_admin.post(f"/usuarios/{usuario.id}/senha", data={"nova": "123"})

    assert "pelo menos 8" in resposta.get_data(as_text=True)
    assert usuario.confere_senha(SENHA_TESTE)


def test_admin_nao_redefine_a_propria_por_aqui(cliente_admin, admin):
    """Para a própria senha existe "Minha senha", que pede a atual."""
    resposta = cliente_admin.post(f"/usuarios/{admin.id}/senha", data={"nova": "qualquer-123"})

    assert resposta.location == "/minha-senha"
    assert admin.confere_senha(SENHA_TESTE)


# ---------- Troca obrigatória ----------

@pytest.fixture
def com_senha_provisoria(app, usuario):
    usuario.trocar_senha = True
    db.session.commit()
    return usuario


@pytest.mark.parametrize("pagina", ["/", "/pacientes", "/relatorio", "/pacientes/novo"])
def test_senha_provisoria_so_deixa_trocar_a_senha(cliente, com_senha_provisoria, pagina):
    resposta = cliente.get(pagina)

    assert resposta.status_code == 302
    assert resposta.location == "/minha-senha"


def test_senha_provisoria_nao_deixa_chamar_paciente(cliente, com_senha_provisoria, criar_paciente):
    paciente = criar_paciente("Ana")

    cliente.post("/pacientes/chamar-proximo", data={"local": "Triagem"})

    assert paciente.status == "Aguardando"


def test_senha_provisoria_pode_sair(cliente, com_senha_provisoria):
    resposta = cliente.post("/logout")

    assert resposta.location == "/login"


def test_depois_de_trocar_volta_ao_normal(cliente, com_senha_provisoria):
    trocar(cliente)

    assert not com_senha_provisoria.trocar_senha
    assert cliente.get("/pacientes").status_code == 200


def test_usuario_criado_pela_admin_troca_no_primeiro_acesso(app, cliente_admin):
    cliente_admin.post("/usuarios", data={
        "nome": "Carla", "login": "carla", "senha": "inicial-123",
    })
    carla = Usuario.query.filter_by(login="carla").one()
    assert carla.trocar_senha

    navegador_carla = navegador_logado(app, carla)
    assert navegador_carla.get("/pacientes").location == "/minha-senha"


def test_usuario_criado_pelo_comando_nao_precisa_trocar(app):
    """Quem roda o comando está escolhendo a PRÓPRIA senha."""
    app.test_cli_runner().invoke(args=[
        "criar-usuario", "dono", "--nome", "Dono", "--senha", "senha-do-dono", "--admin",
    ])

    assert not Usuario.query.filter_by(login="dono").one().trocar_senha


def test_lista_de_usuarios_mostra_senha_provisoria(cliente_admin, com_senha_provisoria):
    html = cliente_admin.get("/usuarios").get_data(as_text=True)

    assert "senha provisória" in html
    assert "Redefinir senha" in html
