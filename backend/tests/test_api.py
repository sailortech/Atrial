"""Testes da API JSON (usada pelo frontend em React)."""

from datetime import datetime, timedelta

import pytest

from app import Paciente, app as flask_app, db
from conftest import SENHA_TESTE


def chamado_ha(criar_paciente, nome, minutos, local="Triagem"):
    momento = datetime.now() - timedelta(minutes=minutos)
    return criar_paciente(nome, status="Em atendimento", local=local,
                          chegou_ha_min=minutos + 10, chamado_em=momento)


# ---------- Sessão e login ----------

def test_sessao_sem_login(cliente_anonimo):
    dados = cliente_anonimo.get("/api/sessao").get_json()

    assert dados["usuario"] is None
    assert dados["csrf"]  # o código já vem, para o React poder fazer login


def test_sessao_com_login(cliente, usuario):
    dados = cliente.get("/api/sessao").get_json()

    assert dados["usuario"] == {
        "nome": "Ana Recepção", "login": "ana", "admin": False, "trocar_senha": False,
    }


def test_login_pela_api(cliente_anonimo, usuario):
    resposta = cliente_anonimo.post("/api/login", json={"login": " ANA ", "senha": SENHA_TESTE})

    assert resposta.status_code == 200
    assert resposta.get_json()["usuario"]["nome"] == "Ana Recepção"
    assert cliente_anonimo.get("/api/pacientes").status_code == 200  # cookie valeu


@pytest.mark.parametrize("corpo", [
    {"login": "ana", "senha": "errada"},
    {"login": "ninguem", "senha": SENHA_TESTE},
    {},
])
def test_login_errado_pela_api(cliente_anonimo, usuario, corpo):
    resposta = cliente_anonimo.post("/api/login", json=corpo)

    assert resposta.status_code == 401
    assert resposta.get_json()["erro"] == "Usuário ou senha incorretos."


def test_api_de_login_tambem_bloqueia_chutes(cliente_anonimo, usuario):
    """As mesmas regras da página HTML (função autenticar)."""
    for _ in range(5):
        cliente_anonimo.post("/api/login", json={"login": "ana", "senha": "chute"})

    resposta = cliente_anonimo.post("/api/login", json={"login": "ana", "senha": SENHA_TESTE})

    assert resposta.status_code == 401
    assert "Muitas tentativas" in resposta.get_json()["erro"]


def test_logout_pela_api(cliente):
    cliente.post("/api/logout")

    assert cliente.get("/api/pacientes").status_code == 401


def test_sem_login_a_api_responde_401_em_json(cliente_anonimo):
    resposta = cliente_anonimo.get("/api/pacientes")

    assert resposta.status_code == 401
    assert resposta.is_json
    assert "login" in resposta.get_json()["erro"]


def test_senha_provisoria_bloqueia_a_api(cliente, usuario):
    usuario.trocar_senha = True
    db.session.commit()

    resposta = cliente.get("/api/pacientes")

    assert resposta.status_code == 403
    assert resposta.get_json()["trocar_senha"] is True
    # ...mas ainda dá para ver a sessão (o React precisa saber o motivo)
    assert cliente.get("/api/sessao").get_json()["usuario"]["trocar_senha"] is True


# ---------- CSRF (ligado, como no sistema de verdade) ----------

@pytest.fixture
def csrf_ligado(app):
    flask_app.config["WTF_CSRF_ENABLED"] = True


def test_post_sem_codigo_csrf_e_recusado(csrf_ligado, cliente, criar_paciente):
    criar_paciente("Ana")

    resposta = cliente.post("/api/pacientes/chamar-proximo", json={"local": "Triagem"})

    assert resposta.status_code == 400
    assert resposta.is_json  # JSON, não a página HTML de erro
    assert Paciente.query.one().status == "Aguardando"


def test_fluxo_do_react_com_csrf(csrf_ligado, cliente_anonimo, usuario, criar_paciente):
    """Exatamente o que o React faz: pega o código, faz login, chama."""
    criar_paciente("Bruno")

    codigo = cliente_anonimo.get("/api/sessao").get_json()["csrf"]
    cabecalho = {"X-CSRFToken": codigo}

    login = cliente_anonimo.post("/api/login", headers=cabecalho,
                                 json={"login": "ana", "senha": SENHA_TESTE})
    assert login.status_code == 200

    chamada = cliente_anonimo.post("/api/pacientes/chamar-proximo", headers=cabecalho,
                                   json={"local": "Triagem"})
    assert chamada.status_code == 200
    assert Paciente.query.one().status == "Em atendimento"


# ---------- Listas ----------

def test_listas_de_pacientes(cliente, criar_paciente):
    criar_paciente("Normal")
    criar_paciente("Urgente", prioridade="Urgente")
    chamado_ha(criar_paciente, "Carla", 5)
    criar_paciente("Davi", status="Concluído", chamado_em=datetime.now(),
                   concluido_em=datetime.now())

    dados = cliente.get("/api/pacientes").get_json()

    assert [p["nome"] for p in dados["fila"]] == ["Urgente", "Normal"]
    assert [p["posicao"] for p in dados["fila"]] == [1, 2]
    assert [p["nome"] for p in dados["em_atendimento"]] == ["Carla"]
    assert [p["nome"] for p in dados["historico"]] == ["Davi"]
    assert dados["total_na_fila"] == 2
    assert dados["locais"] == ["Consultório 1", "Consultório 2", "Consultório 3", "Triagem"]


def test_paciente_vem_com_dados_formatados(cliente, criar_paciente):
    criar_paciente("Ana", cpf="52998224725", chegou_ha_min=12)

    paciente = cliente.get("/api/pacientes").get_json()["fila"][0]

    assert paciente["cpf"] == "529.982.247-25"
    assert paciente["esperando_ha"] == "12 min"
    assert len(paciente["chegada"]) == 5  # "14:32"


def test_busca_pela_api(cliente, criar_paciente):
    criar_paciente("João da Conceição")
    criar_paciente("Bruno")

    dados = cliente.get("/api/pacientes?q=joao").get_json()

    assert [p["nome"] for p in dados["fila"]] == ["João da Conceição"]
    # Bruno continua contando na fila COMPLETA
    assert dados["total_na_fila"] == 2


# ---------- Ações ----------

def test_chamar_proximo_pela_api(cliente, criar_paciente):
    criar_paciente("Ana")

    resposta = cliente.post("/api/pacientes/chamar-proximo", json={"local": "Consultório 2"})

    assert resposta.status_code == 200
    assert "Consultório 2" in resposta.get_json()["mensagem"]
    assert cliente.get("/api/pacientes").get_json()["ultimo_local"] == "Consultório 2"


@pytest.mark.parametrize("local, erro", [
    ("Sala Secreta", "Escolha para qual local"),
    ("", "Escolha para qual local"),
])
def test_chamar_com_local_invalido(cliente, criar_paciente, local, erro):
    criar_paciente("Ana")

    resposta = cliente.post("/api/pacientes/chamar-proximo", json={"local": local})

    assert resposta.status_code == 409
    assert erro in resposta.get_json()["erro"]


def test_chamar_com_fila_vazia(cliente):
    resposta = cliente.post("/api/pacientes/chamar-proximo", json={"local": "Triagem"})

    assert resposta.status_code == 409
    assert "Não há pacientes" in resposta.get_json()["erro"]


@pytest.mark.parametrize("acao, status_final", [
    ("concluir", "Concluído"),
    ("nao-compareceu", "Não compareceu"),
])
def test_encerrar_atendimento_pela_api(cliente, criar_paciente, acao, status_final):
    paciente = chamado_ha(criar_paciente, "Ana", 5)

    resposta = cliente.post(f"/api/pacientes/{paciente.id}/{acao}")

    assert resposta.status_code == 200
    assert paciente.status == status_final


def test_chamar_de_novo_pela_api(cliente, criar_paciente):
    paciente = chamado_ha(criar_paciente, "Ana", 5)

    cliente.post(f"/api/pacientes/{paciente.id}/chamar-de-novo")

    assert paciente.foi_rechamado
    assert cliente.get("/api/pacientes").get_json()["em_atendimento"][0]["foi_rechamado"]


def test_acao_em_quem_nao_esta_em_atendimento(cliente, criar_paciente):
    paciente = criar_paciente("Ana")  # na fila

    resposta = cliente.post(f"/api/pacientes/{paciente.id}/concluir")

    assert resposta.status_code == 409
    assert paciente.status == "Aguardando"


@pytest.mark.parametrize("endereco", ["/api/pacientes/999/concluir", "/api/pacientes/1/apagar"])
def test_paciente_ou_acao_inexistente(cliente, criar_paciente, endereco):
    criar_paciente("Ana")

    resposta = cliente.post(endereco)

    assert resposta.status_code == 404
    assert resposta.is_json


# ---------- Cadastro e edição de paciente ----------

NOVO_PACIENTE = {
    "nome": "  Joana Lima ",
    "nascimento": "1985-03-20",
    "cpf": "390.533.447-05",
    "prioridade": "Preferencial",
    "telefone": "(11) 99999-0000",
    "email": "joana@exemplo.com",
    "observacoes": "",
}


def test_cadastrar_paciente_pela_api(cliente):
    resposta = cliente.post("/api/pacientes", json=NOVO_PACIENTE)

    assert resposta.status_code == 201
    assert resposta.get_json()["mensagem"] == "Paciente Joana Lima cadastrado com sucesso!"

    paciente = Paciente.query.one()
    assert paciente.nome == "Joana Lima"   # espaços tirados
    assert paciente.cpf == "39053344705"   # só os dígitos
    assert paciente.status == "Aguardando"
    assert paciente.chegada is not None     # entrou na fila agora


def test_cadastro_invalido_devolve_erro_por_campo(cliente):
    resposta = cliente.post("/api/pacientes", json={
        **NOVO_PACIENTE, "nome": "", "cpf": "111.111.111-11", "prioridade": "VIP",
    })

    assert resposta.status_code == 422
    erros = resposta.get_json()["erros"]
    assert set(erros) == {"nome", "cpf", "prioridade"}  # nascimento estava certo
    assert Paciente.query.count() == 0


def test_cadastro_com_cpf_repetido(cliente, criar_paciente):
    criar_paciente("Já Existe", cpf="39053344705")

    resposta = cliente.post("/api/pacientes", json=NOVO_PACIENTE)

    assert resposta.status_code == 422
    assert "Já existe" in resposta.get_json()["erros"]["cpf"]


def test_cadastro_com_json_estranho_nao_quebra(cliente):
    # null e número no lugar de texto: tem de virar erro de validação, não 500
    resposta = cliente.post("/api/pacientes", json={"nome": None, "cpf": 123})

    assert resposta.status_code == 422


def test_ler_paciente_para_editar(cliente, criar_paciente):
    paciente = criar_paciente("Bruno", cpf="52998224725", email="b@x.com")

    dados = cliente.get(f"/api/pacientes/{paciente.id}").get_json()["paciente"]

    assert dados["nascimento"] == "1990-05-10"   # formato do <input type="date">
    assert dados["cpf"] == "529.982.247-25"
    assert dados["email"] == "b@x.com"
    assert dados["telefone"] == ""                # vazio, nunca null


def test_editar_paciente_pela_api(cliente, criar_paciente):
    paciente = criar_paciente("Bruno", cpf="52998224725", status="Em atendimento",
                              local="Triagem")

    resposta = cliente.put(f"/api/pacientes/{paciente.id}", json={
        **NOVO_PACIENTE, "nome": "Bruno Souza", "cpf": "52998224725",  # o próprio CPF pode
    })

    assert resposta.status_code == 200
    db.session.refresh(paciente)
    assert paciente.nome == "Bruno Souza"
    assert paciente.prioridade == "Preferencial"
    # Editar dados NÃO mexe no atendimento
    assert paciente.status == "Em atendimento"
    assert paciente.local == "Triagem"


def test_editar_com_cpf_de_outro_paciente(cliente, criar_paciente):
    criar_paciente("Ana", cpf="39053344705")
    bruno = criar_paciente("Bruno", cpf="52998224725")

    resposta = cliente.put(f"/api/pacientes/{bruno.id}", json=NOVO_PACIENTE)

    assert resposta.status_code == 422
    assert "cpf" in resposta.get_json()["erros"]


@pytest.mark.parametrize("metodo", ["get", "put"])
def test_paciente_inexistente(cliente, metodo):
    resposta = getattr(cliente, metodo)("/api/pacientes/999", json=NOVO_PACIENTE)
    assert resposta.status_code == 404


def test_prioridades_vem_do_servidor(cliente):
    dados = cliente.get("/api/pacientes/prioridades").get_json()
    assert dados["prioridades"] == ["Normal", "Preferencial", "Urgente"]


def test_cadastro_pela_api_exige_login(cliente_anonimo):
    assert cliente_anonimo.post("/api/pacientes", json=NOVO_PACIENTE).status_code == 401
