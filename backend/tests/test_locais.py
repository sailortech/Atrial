"""Testes dos locais de atendimento (guichês, consultórios)."""

from datetime import date, datetime

import pytest

from app import Local, Paciente, db, nomes_dos_locais_ativos, relatorio_do_dia


def local(nome):
    return Local.query.filter_by(nome=nome).one()


def adicionar(cliente, nome):
    return cliente.post("/api/locais", json={"nome": nome})


def alternar(cliente, nome):
    return cliente.post(f"/api/locais/{local(nome).id}/alternar")


def chamar_para(cliente):
    """As opções do "Chamar para..." da tela de pacientes."""
    return cliente.get("/api/pacientes").get_json()["locais"]


# ---------- Adicionar ----------

def test_adicionar_local(cliente_admin):
    adicionar(cliente_admin, "  Consultório   4 ")

    assert local("Consultório 4").ativo  # espaços sobrando foram limpos
    assert "Consultório 4" in nomes_dos_locais_ativos()


def test_novo_local_aparece_no_chamar_para(cliente_admin):
    adicionar(cliente_admin, "Sala de Vacina")

    assert "Sala de Vacina" in chamar_para(cliente_admin)


@pytest.mark.parametrize("nome", ["Triagem", "triagem", "CONSULTORIO 1", "consultório 1"])
def test_nao_aceita_local_repetido(cliente_admin, nome):
    resposta = adicionar(cliente_admin, nome)

    assert "Já existe um local" in resposta.get_json()["erros"]["nome"]
    assert Local.query.count() == 4  # continua com os 4 iniciais


@pytest.mark.parametrize("nome, erro", [
    ("", "Informe o nome"),
    ("   ", "Informe o nome"),
    ("x" * 51, "no máximo 50"),
])
def test_nome_invalido(cliente_admin, nome, erro):
    resposta = adicionar(cliente_admin, nome)

    assert erro in resposta.get_json()["erros"]["nome"]
    assert Local.query.count() == 4


# ---------- Desativar e reativar ----------

def test_desativar_tira_do_chamar_para(cliente_admin):
    alternar(cliente_admin, "Consultório 3")

    assert not local("Consultório 3").ativo
    assert "Consultório 3" not in chamar_para(cliente_admin)


def test_nao_chama_para_local_desativado(cliente_admin, criar_paciente):
    paciente = criar_paciente("Ana")
    alternar(cliente_admin, "Consultório 3")

    cliente_admin.post("/api/pacientes/chamar-proximo", json={"local": "Consultório 3"})

    db.session.refresh(paciente)
    assert paciente.status == "Aguardando"


def test_reativar(cliente_admin):
    alternar(cliente_admin, "Consultório 3")  # desativa
    alternar(cliente_admin, "Consultório 3")  # reativa

    assert local("Consultório 3").ativo


def test_nao_deixa_desativar_o_ultimo_local(cliente_admin):
    for nome in ["Consultório 1", "Consultório 2", "Consultório 3"]:
        alternar(cliente_admin, nome)

    resposta = alternar(cliente_admin, "Triagem")

    assert resposta.status_code == 409
    assert "pelo menos um local ativo" in resposta.get_json()["erro"]
    assert local("Triagem").ativo


def test_historico_continua_com_o_nome_do_local_desativado(cliente_admin, criar_paciente):
    criar_paciente("Ana", status="Concluído", local="Consultório 3",
                   chamado_em=datetime.now(), concluido_em=datetime.now())

    alternar(cliente_admin, "Consultório 3")

    historico = cliente_admin.get("/api/pacientes").get_json()["historico"]
    assert historico[0]["local"] == "Consultório 3"


def test_relatorio_mostra_local_desativado_nos_dias_em_que_atendeu(cliente_admin, criar_paciente):
    dia = date.today()
    criar_paciente("Ana", status="Concluído", local="Consultório 3",
                   chamado_em=datetime.now(), concluido_em=datetime.now())
    alternar(cliente_admin, "Consultório 3")

    locais_no_relatorio = [l["local"] for l in relatorio_do_dia(dia)["por_local"]]

    assert "Consultório 3" in locais_no_relatorio  # atendeu hoje
    assert locais_no_relatorio == sorted(locais_no_relatorio)


def test_locais_exigem_login(cliente_anonimo):
    assert cliente_anonimo.get("/api/locais").status_code == 401
    adicionar(cliente_anonimo, "Invasor")
    assert Local.query.filter_by(nome="Invasor").first() is None


# ---------- API (React) ----------

def test_api_lista_ativos_primeiro(cliente_admin):
    local("Consultório 1").ativo = False
    db.session.commit()

    locais = cliente_admin.get("/api/locais").get_json()["locais"]

    assert [l["nome"] for l in locais] == [
        "Consultório 2", "Consultório 3", "Triagem", "Consultório 1",
    ]
    assert locais[-1]["ativo"] is False


def test_api_adiciona_local(cliente_admin):
    resposta = cliente_admin.post("/api/locais", json={"nome": "  Raio   X "})

    assert resposta.status_code == 201
    assert resposta.get_json()["mensagem"] == 'Local "Raio X" adicionado.'
    assert local("Raio X").ativo


@pytest.mark.parametrize("nome", ["", "consultorio 1", "x" * 51, None])
def test_api_recusa_nome_invalido(cliente_admin, nome):
    resposta = cliente_admin.post("/api/locais", json={"nome": nome})

    assert resposta.status_code == 422
    assert "nome" in resposta.get_json()["erros"]
    assert Local.query.count() == 4  # só os iniciais


def test_api_alterna_local(cliente_admin):
    id_ = local("Consultório 2").id

    resposta = cliente_admin.post(f"/api/locais/{id_}/alternar")
    assert resposta.get_json()["mensagem"] == 'Local "Consultório 2" desativado.'
    assert not local("Consultório 2").ativo

    cliente_admin.post(f"/api/locais/{id_}/alternar")
    assert local("Consultório 2").ativo


def test_api_nao_desativa_o_ultimo_local(cliente_admin):
    for nome in ["Consultório 1", "Consultório 2", "Consultório 3"]:
        cliente_admin.post(f"/api/locais/{local(nome).id}/alternar")

    resposta = cliente_admin.post(f"/api/locais/{local('Triagem').id}/alternar")

    assert resposta.status_code == 409
    assert "pelo menos um local ativo" in resposta.get_json()["erro"]
    assert local("Triagem").ativo


def test_api_local_inexistente(cliente_admin):
    assert cliente_admin.post("/api/locais/999/alternar").status_code == 404


# ---------- Renomear (API) ----------

def test_renomear_local(cliente_admin):
    id_ = local("Consultório 3").id

    resposta = cliente_admin.put(f"/api/locais/{id_}", json={"nome": "  Sala   de Vacina "})

    assert resposta.status_code == 200
    assert resposta.get_json()["mensagem"] == 'Local "Consultório 3" agora se chama "Sala de Vacina".'
    assert local("Sala de Vacina").id == id_
    assert "Sala de Vacina" in nomes_dos_locais_ativos()


def test_renomear_so_corrigindo_maiusculas_e_acentos(cliente_admin):
    """O próprio local não conta como repetido."""
    db.session.add(Local(nome="consultorio 4"))
    db.session.commit()
    id_ = local("consultorio 4").id

    resposta = cliente_admin.put(f"/api/locais/{id_}", json={"nome": "Consultório 4"})

    assert resposta.status_code == 200
    assert local("Consultório 4").id == id_


def test_renomear_mantendo_o_nome(cliente_admin):
    resposta = cliente_admin.put(f"/api/locais/{local('Triagem').id}", json={"nome": "Triagem"})

    assert resposta.status_code == 200
    assert "mesmo nome" in resposta.get_json()["mensagem"]


@pytest.mark.parametrize("nome", ["", "triagem", "x" * 51])
def test_renomear_recusa_nome_invalido_ou_de_outro_local(cliente_admin, nome):
    resposta = cliente_admin.put(f"/api/locais/{local('Consultório 1').id}", json={"nome": nome})

    assert resposta.status_code == 422
    assert "nome" in resposta.get_json()["erros"]
    assert local("Consultório 1")  # continua com o nome antigo


def test_renomear_nao_muda_o_historico(cliente_admin, criar_paciente):
    """Quem já foi chamado continua com o nome de ANTES (é o registro)."""
    paciente = criar_paciente("Ana", status="Concluído", local="Consultório 2",
                              chamado_em=datetime.now(), concluido_em=datetime.now())

    cliente_admin.put(f"/api/locais/{local('Consultório 2').id}", json={"nome": "Pediatria"})

    db.session.refresh(paciente)
    assert paciente.local == "Consultório 2"


def test_chamar_para_o_local_renomeado(cliente_admin, criar_paciente):
    criar_paciente("Bruno")
    cliente_admin.put(f"/api/locais/{local('Consultório 2').id}", json={"nome": "Pediatria"})

    resposta = cliente_admin.post("/api/pacientes/chamar-proximo", json={"local": "Pediatria"})

    assert resposta.status_code == 200
    assert Paciente.query.one().local == "Pediatria"


def test_renomear_local_inexistente(cliente_admin):
    assert cliente_admin.put("/api/locais/999", json={"nome": "X"}).status_code == 404
