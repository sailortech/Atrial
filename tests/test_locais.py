"""Testes do cadastro de locais (/locais)."""

from datetime import date, datetime

import pytest

from app import Local, Paciente, db, nomes_dos_locais_ativos, relatorio_do_dia


def local(nome):
    return Local.query.filter_by(nome=nome).one()


# ---------- Adicionar ----------

def test_adicionar_local(cliente_admin):
    cliente_admin.post("/locais", data={"nome": "  Consultório   4 "})

    assert local("Consultório 4").ativo  # espaços sobrando foram limpos
    assert "Consultório 4" in nomes_dos_locais_ativos()


def test_novo_local_aparece_no_chamar_para(cliente_admin):
    cliente_admin.post("/locais", data={"nome": "Sala de Vacina"})

    html = cliente_admin.get("/pacientes").get_data(as_text=True)

    assert '<option value="Sala de Vacina"' in html


@pytest.mark.parametrize("nome", ["Triagem", "triagem", "CONSULTORIO 1", "consultório 1"])
def test_nao_aceita_local_repetido(cliente_admin, nome):
    resposta = cliente_admin.post("/locais", data={"nome": nome}, follow_redirects=True)

    assert "Já existe um local" in resposta.get_data(as_text=True)
    assert Local.query.count() == 4  # continua com os 4 iniciais


@pytest.mark.parametrize("nome, erro", [
    ("", "Informe o nome"),
    ("   ", "Informe o nome"),
    ("x" * 51, "no máximo 50"),
])
def test_nome_invalido(cliente_admin, nome, erro):
    resposta = cliente_admin.post("/locais", data={"nome": nome}, follow_redirects=True)

    assert erro in resposta.get_data(as_text=True)
    assert Local.query.count() == 4


# ---------- Desativar e reativar ----------

def test_desativar_tira_do_chamar_para(cliente_admin):
    cliente_admin.post(f"/locais/{local('Consultório 3').id}/alternar")

    assert not local("Consultório 3").ativo
    html = cliente_admin.get("/pacientes").get_data(as_text=True)
    assert '<option value="Consultório 3"' not in html


def test_nao_chama_para_local_desativado(cliente_admin, criar_paciente):
    paciente = criar_paciente("Ana")
    cliente_admin.post(f"/locais/{local('Consultório 3').id}/alternar")

    cliente_admin.post("/pacientes/chamar-proximo", data={"local": "Consultório 3"})

    db.session.refresh(paciente)
    assert paciente.status == "Aguardando"


def test_reativar(cliente_admin):
    id_ = local("Consultório 3").id
    cliente_admin.post(f"/locais/{id_}/alternar")  # desativa
    cliente_admin.post(f"/locais/{id_}/alternar")  # reativa

    assert local("Consultório 3").ativo


def test_nao_deixa_desativar_o_ultimo_local(cliente_admin):
    for nome in ["Consultório 1", "Consultório 2", "Consultório 3"]:
        cliente_admin.post(f"/locais/{local(nome).id}/alternar")

    resposta = cliente_admin.post(
        f"/locais/{local('Triagem').id}/alternar", follow_redirects=True
    )

    assert "pelo menos um local ativo" in resposta.get_data(as_text=True)
    assert local("Triagem").ativo


def test_historico_continua_com_o_nome_do_local_desativado(cliente_admin, criar_paciente):
    criar_paciente("Ana", status="Concluído", local="Consultório 3",
                   chamado_em=datetime.now(), concluido_em=datetime.now())

    cliente_admin.post(f"/locais/{local('Consultório 3').id}/alternar")

    html = cliente_admin.get("/pacientes").get_data(as_text=True)
    historico = html.split("Histórico de atendimentos")[1]
    assert "Consultório 3" in historico


def test_relatorio_mostra_local_desativado_nos_dias_em_que_atendeu(cliente_admin, criar_paciente):
    dia = date.today()
    criar_paciente("Ana", status="Concluído", local="Consultório 3",
                   chamado_em=datetime.now(), concluido_em=datetime.now())
    cliente_admin.post(f"/locais/{local('Consultório 3').id}/alternar")

    locais_no_relatorio = [l["local"] for l in relatorio_do_dia(dia)["por_local"]]

    assert "Consultório 3" in locais_no_relatorio  # atendeu hoje
    assert locais_no_relatorio == sorted(locais_no_relatorio)


def test_pagina_de_locais_exige_login(cliente_anonimo):
    assert cliente_anonimo.get("/locais").status_code == 302
    cliente_anonimo.post("/locais", data={"nome": "Invasor"})
    assert Local.query.filter_by(nome="Invasor").first() is None


def test_pagina_lista_ativos_e_desativados(cliente_admin):
    cliente_admin.post(f"/locais/{local('Consultório 2').id}/alternar")

    html = cliente_admin.get("/locais").get_data(as_text=True)

    assert "Desativado" in html and "Reativar" in html
    # Ativos vêm antes dos desativados (olhando só a tabela: a mensagem
    # "Local Consultório 2 desativado." aparece antes dela, no topo)
    tabela = html.split("<tbody>")[1]
    assert tabela.index("Triagem") < tabela.index("Consultório 2")
