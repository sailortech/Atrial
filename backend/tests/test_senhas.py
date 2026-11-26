"""Testes de senha: trocar a própria, redefinir (admin) e troca obrigatória."""

import pytest

from app import Usuario, db
from conftest import SENHA_TESTE, navegador_logado

NOVA = "outra-senha-456"


def trocar(cliente, atual=SENHA_TESTE, nova=NOVA, confirmacao=None):
    return cliente.post("/api/minha-senha", json={
        "atual": atual,
        "nova": nova,
        "confirmacao": nova if confirmacao is None else confirmacao,
    })


# ---------- Minha senha ----------

def test_trocar_a_propria_senha(app, cliente, usuario):
    intruso = navegador_logado(app, usuario)  # "outro computador"

    resposta = trocar(cliente)

    assert resposta.status_code == 200
    assert resposta.get_json()["mensagem"] == "Senha alterada."
    assert resposta.get_json()["usuario"]["trocar_senha"] is False
    assert usuario.confere_senha(NOVA)
    assert not usuario.confere_senha(SENHA_TESTE)
    # Este navegador continua dentro; o outro cai
    assert cliente.get("/api/pacientes").status_code == 200
    assert intruso.get("/api/pacientes").status_code == 401


@pytest.mark.parametrize("dados, campos, erro", [
    ({"atual": "errada"}, {"atual"}, "senha atual está incorreta"),
    ({"nova": "curta"}, {"nova"}, "pelo menos 8"),
    ({"confirmacao": "diferente-123"}, {"confirmacao"}, "confirmação não é igual"),
    ({"nova": SENHA_TESTE}, {"nova"}, "diferente da atual"),
    ({"atual": "errada", "nova": "curta"}, {"atual", "nova"}, "pelo menos 8"),
])
def test_troca_invalida_diz_o_campo_e_nao_muda_a_senha(cliente, usuario, dados, campos, erro):
    resposta = trocar(cliente, **dados)

    assert resposta.status_code == 422
    erros = resposta.get_json()["erros"]
    assert set(erros) == campos
    assert any(erro in mensagem for mensagem in erros.values())
    assert usuario.confere_senha(SENHA_TESTE)  # continua a mesma


def test_senhas_digitadas_nao_voltam_na_resposta(cliente):
    resposta = trocar(cliente, atual="errada-mas-secreta", nova="nova-secreta-789")

    texto = resposta.get_data(as_text=True)
    assert "errada-mas-secreta" not in texto
    assert "nova-secreta-789" not in texto


def test_trocar_senha_exige_login(cliente_anonimo):
    assert trocar(cliente_anonimo).status_code == 401


# ---------- Redefinir (administração) ----------

def test_admin_redefine_senha_de_quem_esqueceu(cliente_admin, usuario):
    cliente_admin.post(f"/api/usuarios/{usuario.id}/senha", json={"nova": "provisoria-1"})

    assert usuario.confere_senha("provisoria-1")
    assert usuario.trocar_senha  # vai ter que criar a própria


def test_redefinir_com_senha_curta(cliente_admin, usuario):
    resposta = cliente_admin.post(f"/api/usuarios/{usuario.id}/senha", json={"nova": "123"})

    assert "pelo menos 8" in resposta.get_json()["erros"]["nova"]
    assert usuario.confere_senha(SENHA_TESTE)


def test_admin_nao_redefine_a_propria_por_aqui(cliente_admin, admin):
    """Para a própria senha existe "Minha senha", que pede a atual."""
    resposta = cliente_admin.post(f"/api/usuarios/{admin.id}/senha", json={"nova": "qualquer-123"})

    assert resposta.status_code == 409
    assert "Minha senha" in resposta.get_json()["erro"]
    assert admin.confere_senha(SENHA_TESTE)


# ---------- Troca obrigatória ----------

@pytest.fixture
def com_senha_provisoria(app, usuario):
    usuario.trocar_senha = True
    db.session.commit()
    return usuario


@pytest.mark.parametrize("endereco", [
    "/api/pacientes", "/api/relatorio", "/api/pacientes/prioridades",
])
def test_senha_provisoria_so_deixa_trocar_a_senha(cliente, com_senha_provisoria, endereco):
    resposta = cliente.get(endereco)

    assert resposta.status_code == 403
    assert resposta.get_json()["trocar_senha"] is True  # o React mostra a troca


def test_senha_provisoria_ainda_ve_a_sessao(cliente, com_senha_provisoria):
    """O React precisa saber QUEM está logado para mostrar a troca."""
    assert cliente.get("/api/sessao").get_json()["usuario"]["trocar_senha"] is True


def test_senha_provisoria_nao_deixa_chamar_paciente(cliente, com_senha_provisoria, criar_paciente):
    paciente = criar_paciente("Ana")

    cliente.post("/api/pacientes/chamar-proximo", json={"local": "Triagem"})

    assert paciente.status == "Aguardando"


def test_senha_provisoria_pode_sair(cliente, com_senha_provisoria):
    assert cliente.post("/api/logout").status_code == 200


def test_depois_de_trocar_volta_ao_normal(cliente, com_senha_provisoria):
    trocar(cliente)

    assert not com_senha_provisoria.trocar_senha
    assert cliente.get("/api/pacientes").status_code == 200


def test_usuario_criado_pela_admin_troca_no_primeiro_acesso(app, cliente_admin):
    cliente_admin.post("/api/usuarios", json={
        "nome": "Carla", "login": "carla", "senha": "inicial-123",
    })
    carla = Usuario.query.filter_by(login="carla").one()
    assert carla.trocar_senha

    navegador_carla = navegador_logado(app, carla)
    assert navegador_carla.get("/api/pacientes").status_code == 403


def test_usuario_criado_pelo_comando_nao_precisa_trocar(app):
    """Quem roda o comando está escolhendo a PRÓPRIA senha."""
    app.test_cli_runner().invoke(args=[
        "criar-usuario", "dono", "--nome", "Dono", "--senha", "senha-do-dono", "--admin",
    ])

    assert not Usuario.query.filter_by(login="dono").one().trocar_senha


def test_lista_de_usuarios_mostra_senha_provisoria(cliente_admin, com_senha_provisoria):
    lista = cliente_admin.get("/api/usuarios").get_json()["usuarios"]

    ana = next(u for u in lista if u["login"] == "ana")
    assert ana["trocar_senha"] is True
